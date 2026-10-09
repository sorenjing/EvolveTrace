# Runtime concurrency and process model

AI Context Kit has two runtime shapes with different concurrency requirements: a local mutating CLI and a remote read-only MCP service. They deliberately do not share one scaling strategy.

## Local CLI: serialize mutations

`init`, non-dry-run `update`, and `publish` acquire `.ai/write.lock` before entering their read-compute-replace critical section. The lock is process-wide at the operating-system level (`flock` on POSIX and byte-range locking on Windows), so separate terminals and agent processes coordinate without an in-memory singleton.

Atomic replacement and locking solve different problems:

- writing a temporary file and calling `os.replace` prevents readers from seeing a partially written file;
- the workspace lock prevents two writers from reading the same old state and then overwriting each other's results.

The lock times out instead of waiting forever. Dry runs remain lock-free because they do not mutate shared state. The lock file is coordination metadata and is safe to keep after a process exits; the operating system releases the lock when its file descriptor closes or the process terminates.

The scanner remains single-process. Its workload is bounded metadata and small README excerpts, so process creation, serialization, and IPC would add complexity without demonstrated benefit. Parallel scanning should be considered only after measurements identify it as a bottleneck.

## MCP server: bound remote work

The MCP service exposes synchronous read-only tools. The SDK may execute concurrent calls in worker threads, so each server process uses a bounded semaphore around GitHub reads. When all slots are occupied, a call waits briefly and then returns a busy error instead of allowing an unbounded queue to retain request state.

The GitHub boundary also enforces:

- a fixed request timeout;
- a maximum response size before JSON or base64 decoding;
- one configured `owner/repository`, ref, and publication root;
- exact project lookup through the published index.

These limits protect one process. If the service is deployed with multiple worker processes, each process has its own semaphore and memory. Therefore the effective instance-wide maximum is approximately `workers × AICTX_MAX_IN_FLIGHT`; operators must size both values together. There is no cross-worker cache or lock because the service performs no writes.

## Configuration

| Variable | Default | Meaning |
|---|---:|---|
| `AICTX_MAX_IN_FLIGHT` | `32` | Concurrent GitHub reads per MCP worker process |
| `AICTX_ACQUIRE_TIMEOUT` | `0.25` | Seconds to wait for an in-flight slot |
| `AICTX_GITHUB_TIMEOUT` | `10` | Seconds allowed for one GitHub API request |
| `AICTX_MAX_RESPONSE_BYTES` | `2097152` | Maximum encoded GitHub API response size |

Increasing concurrency can raise throughput but also multiplies sockets, retained response buffers, GitHub API pressure, and worst-case memory. Tune with latency and in-flight metrics rather than CPU count alone because this path is I/O-bound.

## Shutdown and failure behavior

The MCP SDK and ASGI server own signal handling and stop accepting work during shutdown. Local file locks are tied to open descriptors, so abnormal process termination releases the kernel lock. A crash between temporary-file creation and replacement may leave a hidden temporary file, but it does not expose a partially written target or permanently hold the workspace lock.

This design does not claim crash-durable commits: `_atomic_text` does not `fsync` the target and parent directory. The guarantee is concurrent-writer correctness and atomic visibility under normal filesystem semantics, not survival of sudden power loss.
