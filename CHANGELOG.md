# Changelog

## Unreleased

- Added a producer/receipt/verifier/consumer flow diagram, complete POSIX and
  PowerShell quickstarts with expected output, all eight verifier states and
  CLI exit codes, metadata badges, and inline protocol/conformance links.
- Hardened the consumer example to reconstruct current facts independently,
  hash saved result bytes, fail closed with gate exit codes, and optionally
  export current action facts without overwriting evidence. The producer now
  saves a companion result file; custom inputs and result paths are supported.
- Added regression coverage for the walkthrough, current-state and trust
  separation, result integrity, error handling, all CLI state/exit combinations,
  and README metadata/link consistency.
- Updated package and security-reporting links to the current repository owner.
  The protocol schemas, core verifier, and package version remain unchanged.

- Added an independent .NET 8 conformance consumer and required .NET CI
  coverage. This is repository-controlled cross-runtime evidence, not external
  adoption evidence.

## 0.1.0 — 2026-08-13

This release establishes Oncefold's experimental pre-1.0 protocol baseline.

- Baseline for the Oncefold Action Identity, Reuse Receipt, and
  deterministic Reuse Decision protocol.
- Added Python reference verification, JSON schemas, and a language-neutral
  60-case conformance corpus with raw-ingress fixtures.
- Added independent TypeScript and Go conformance consumers.
- Added an optional shadow-only MCP reference adapter that never suppresses the
  underlying call.
- Hardened consumer trust examples and CLI gates against receipt-derived policy
  and embedded-action reuse.
- Made dependency completeness explicit, froze Python protocol mappings, checked
  in-memory receipt keys, and aligned Unicode and dependency bounds across
  implementations.
- Documented the research conclusion that the broad standalone agent-cache
  thesis did not survive authentic V5.1 economics testing.
