# Security policy

## Reporting

Report vulnerabilities privately through
https://github.com/sorenjing/EvolveTrace/security/advisories/new.
Include a minimal synthetic reproduction, affected commit/version, expected
boundary and observed impact. Do not post credentials, real transcripts,
databases, private project contents or personal paths in a public issue.

## Supported deployment

EvolveTrace is an early local-first tool. Use the documented loopback-only
service. The API has no account authentication and must not be exposed as a
shared or public service. Docker support is experimental. Only the current
development line is maintained; no response-time guarantee is offered.

## Security boundaries

- Hooks redact common credential patterns before sending events; the backend
  redacts again before storage. Pattern matching cannot remove arbitrary
  personal or confidential content.
- Local evidence stores, analysis prompts and reviewed memory can contain
  sensitive project information. Review them before sharing or exporting.
- Execution reconciliation reads bounded, Hook-referenced files under the
  configured local Codex sessions directory. It checks session and call IDs,
  retains typed execution metadata and does not persist transcript messages.
- Context collection and optional GitHub-backed MCP boundaries are described
  in [context/SECURITY.md](context/SECURITY.md).
- Safety Sentinel checks a narrow set of observable commands. It is not an
  operating-system sandbox, and missing evidence does not establish safety.

Traversal outside the allowed source roots, unredacted credentials,
non-loopback API access, unexpected source upload or forged execution evidence
are examples of issues to report. No finding class is excluded by this policy.

Dependency advisory checks and the narrowly reviewed development-only finding
are documented in [docs/dependency-security.md](docs/dependency-security.md).
