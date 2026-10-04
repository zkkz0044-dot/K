# Changelog

## Unreleased

### Changed
- Fixed public self-knowledge claims that assumed an absent creator letter or visitor identity.
- Rejected bare keyword lists in the generalization rubric; documented that all language rubrics remain heuristic.
- Removed unsupported sensor and equipment facts from policy fallbacks and generalized causal/calibration guidance.
- Marked programmatic fallback answers, lowered their confidence, and recorded answer origin without claiming verified cognition.
- Prioritized hard safety risks before explanatory fallback branches.
- Fixed belief and skill default audit addresses to use the real abstract Unix socket constant.
- Added fresh release counterexamples and an offline real-audit-IPC chat/restart/recall integration test.
- Added loopback Host/Origin checks, bounded requests, bounded audit/state reads, and child-process cleanup to the panel.
- Added panel HTTP regression tests to the isolated release gate and pinned the test dependency.
- Added MIT licensing, an offline first-run guide, and explicit capability/evaluation limits.
- Refactored K dialogue rule and deterministic-guard responsibilities into smaller modules.
- Split F cognition state handling into personality, belief, and skill modules.
- Split FK role policy from model gateway transport.
- Renamed the K-side model IPC client to provider-neutral `model_client.py`.
- Simplified the cognition-provider configuration to OpenAI-only.
- Replaced world-reasoning tests that depended on retained runtime data with deterministic synthetic fixtures.
- Added an isolated clean-install test gate that validates K, F, and FK without reading a live K instance.
- Added a CI workflow for the clean-install release gate.
- Added GitHub issue/PR templates and repository editor defaults.
- Added deterministic SHA256 generation and verification scripts for release artifacts.

### Security
- Added deterministic public-tree hygiene checks.
- Added checks for credentials, private paths, runtime artifacts, and account-specific data.
- Excluded runtime state, personal memory, audit history, device binding state, and private infrastructure data.
