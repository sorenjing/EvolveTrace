# Hook evidence contract

EvolveTrace records only fields delivered to its configured Codex hooks. The
configured event names are in `plugin/hooks/hooks.json`; the collector accepts
a JSON object with a nonempty `session_id` and an event name in
`hook_event_name` (or the compatibility fields `event_type` / `type`). The
synthetic `PreToolUse` example at
`backend/tests/fixtures/codex_hook_contract.json` exercises client-side
redaction before the HTTP request is constructed. It is a test fixture, not a
captured user session or proof that every Codex version emits those fields.

To inspect a real installation, compare the installed hook configuration and
the product's current hook documentation with `plugin/hooks/hooks.json`. Run a
local task containing an ordinary tool call, then check the session timeline
for the observed event names and timestamps. Record the client and plugin
versions alongside any diagnosis. An absent event can mean the hook was not
configured, did not fire, could not reach the local service, or was rejected;
the timeline alone cannot distinguish those causes.

The collector redacts common credential fields and strings before sending
them to the loopback API. The backend applies a second redaction pass before
storage. These rules are deliberately finite: a novel secret format can evade
them, so test new adapter payload shapes with synthetic positive and negative
examples before treating them as safe. Raw hook payloads and hidden model
reasoning are not stored or inferred.

For repeatable local checks:

```bash
python -m pytest backend/tests/test_hook_capture.py backend/tests/test_audit_redaction.py -q
```

The fixture checks the transport boundary; the redaction tests check the
storage boundary. Neither substitutes for a version-specific live hook check.
