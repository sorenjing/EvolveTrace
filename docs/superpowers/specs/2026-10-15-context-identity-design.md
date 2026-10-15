# EvolveTrace Context identity

The component is part of EvolveTrace and uses one canonical identity:

| Surface | Identity |
| --- | --- |
| Display name | EvolveTrace Context |
| Python distribution | evolvetrace-context |
| Python import | evolvetrace_context |
| Standalone component plugin / MCP server | evolvetrace-context |
| Unified plugin | evolvetrace |
| CLI commands | aictx / aictx-mcp |

The old distribution and module are not retained as active aliases. Update
imports, package metadata, bundled Skill data paths, entrypoints, Hook imports,
provider examples, build/release smoke tests, tests and current documentation.
Existing .aictx.toml paths, managed markers, command names, environment variables,
ContextBundle v1, receipt schemas, stored memory and audit records are stable.

Original MIT copyright and attribution remain in LICENSE and NOTICE. Historical
design documents retain the names in use when they were written; the October 9
consolidation compatibility policy is superseded by this decision. Installation
migration instructions may name the old package solely to remove an installation
that points to this component. Do not rename or delete an independent repository
or modify an unrelated installation with the same old package name.

## Migration and validation

1. Add failing identity tests and inventory all executable and current-document
   references. Preserve the uncommitted workspace-audit changes.
2. Prepare the renamed module and update consumers. Keep the old source import
   operational until the new local distribution is installed.
3. Verify the old editable distribution points at this component before
   uninstalling that distribution, then install the new local package without
   network dependency resolution. Retain a local source backup until validation.
4. Remove the old module from the active source tree. Verify global CLI, module
   entry, Hook loading, MCP server identity, Context tests, unified plugin tests,
   wheel contents and installation into an isolated environment.
5. Rebuild local plugin archives. Publication and plugin-host trust review are
   separate from changing local source/package identity.

## Verified local result

- Context and extracted unified-plugin tests: 167 passed, 3 platform-related
  skips. The namespace/metadata tests reject the predecessor's active identity.
- Normal wheel and source distribution build from the renamed source. A fresh
  environment imports the non-editable wheel from its own site-packages and
  runs the CLI and an offline init dry-run.
- Every one of the 25 source modules matches its pre-rename version after only
  the defined identity substitutions, preserving pending workspace-audit work.
- Both verified local component installations and the existing custom aictx
  launcher use the new module. The host's existing cached SessionStart loader
  successfully returned synthetic project context and recorded a returned usage
  receipt. This demonstrates loading, not model use or task benefit.
- The unified plugin archive was rebuilt, and workspace managed-marker checks
  pass. Registry publication and plugin-marketplace replacement remain explicit
  release operations.
