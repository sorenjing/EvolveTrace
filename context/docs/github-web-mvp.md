# GitHub-backed web MVP

This mode gives ChatGPT and other remote MCP clients read-only access to context that a user explicitly exports and commits. It does not expose a local workspace, push files, or read arbitrary repository paths.

## Data flow

1. `aictx` observes the bounded local inputs documented in each project memory.
2. `aictx publish github <project>` writes a reviewable publication tree under `.ai/published`.
3. The user reviews and commits that directory as `.ai-context` in a dedicated GitHub repository or branch.
4. The MCP service reads `index.json`, then only the bundle path declared for the requested project.
5. ChatGPT calls `list_projects`, `get_context`, or `get_freshness` through the deployed streamable HTTP endpoint.

The publication tree uses ordinary JSON:

```text
.ai-context/
  index.json
  projects/
    my-project.json
```

## Publish a bundle

```bash
aictx update my-project
aictx check
aictx publish github my-project
```

Review `.ai/published/index.json` and `.ai/published/projects/my-project.json`. Copy or commit the contents of `.ai/published` to `.ai-context` in the selected GitHub repository only after checking for private or identifying content. Re-running the command replaces that project's entry while preserving other valid index entries.

The command performs no network request and never runs `git commit` or `git push`.

## Run the MCP server

Install the server extra and configure its one allowed repository:

```bash
pip install ".[server]"
export AICTX_GITHUB_REPOSITORY="owner/context-repository"
export AICTX_GITHUB_REF="main"
export AICTX_GITHUB_PATH=".ai-context"
aictx-mcp
```

For a private repository, set `GITHUB_TOKEN` through the deployment platform's secret manager. Use a fine-grained, read-only token limited to the context repository. Public repositories do not require a token. The service sends the token only to `api.github.com` and does not include it in results.

Environment variables:

| Name | Required | Default | Purpose |
|---|---:|---|---|
| `AICTX_GITHUB_REPOSITORY` | yes | none | Exact `owner/name` repository |
| `AICTX_GITHUB_REF` | no | `main` | Branch, tag, or commit ref |
| `AICTX_GITHUB_PATH` | no | `.ai-context` | Fixed publication directory |
| `GITHUB_TOKEN` | private repos only | none | Read-only GitHub credential |
| `AICTX_GITHUB_TIMEOUT` | no | `10` | GitHub request timeout in seconds |
| `AICTX_MAX_RESPONSE_BYTES` | no | `2097152` | Maximum encoded GitHub response body |
| `AICTX_MAX_IN_FLIGHT` | no | `32` | Concurrent GitHub reads per worker process |
| `AICTX_ACQUIRE_TIMEOUT` | no | `0.25` | Wait for a request slot before returning busy |
| `HOST` | no | `127.0.0.1` | Bind address; container sets `0.0.0.0` |
| `PORT` | no | `8000` | HTTP port |

## Deploy and connect ChatGPT

Build `Dockerfile` on a platform that supports streaming HTTP and secret management. The stable HTTPS endpoint must expose `/mcp`. After deployment:

1. Inspect the endpoint with MCP Inspector and call all three tools with valid and invalid project names.
2. Enable ChatGPT developer mode and register the stable HTTPS MCP URL.
3. Copy the resulting `plugin_asdk_app...` technical ID.
4. Add `.app.json` mapping that registered ID and reference it from the OpenAI plugin extension before distribution.
5. Replace `mcp.example.json` with root `mcp.json` containing the real stable URL before public packaging.

Root `mcp.json` and `.app.json` are deployment-specific files. Add them after the MCP service has a stable HTTPS endpoint, domain verification is complete, and ChatGPT has issued the technical ID; until then, use `mcp.example.json` as the configuration reference.

## Tool contract

| Tool | Reads | Does not do |
|---|---|---|
| `list_projects` | Published index metadata | Discover arbitrary repositories |
| `get_context` | One indexed `ContextBundle v1` | Read source files or accept a path |
| `get_freshness` | Bundle timestamp, label, and observed scope | Claim source code is fully current |

All tools are read-only. Project lookup is exact, bundle paths must live below `projects/`, and the bundle identity must match the requested project.

See [Runtime concurrency and process model](runtime-concurrency.md) before changing worker count or concurrency limits.
