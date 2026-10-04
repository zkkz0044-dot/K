# Development

## Fast local validation

For ordinary development on Linux or WSL with Python and pytest:

```bash
python3 scripts/check_public_tree.py
./scripts/test_all.sh
```

The test runner disables Python bytecode and pytest cache creation so validation does not dirty the source tree.

## Clean-install release validation

The release gate must also prove that the repository does not depend on a developer's live K instance or retained runtime data:

```bash
sudo bash scripts/test_clean_install.sh
```

This script copies K, F, and FK into a disposable staging tree, supplies synthetic runtime fixtures required by integration tests, removes group/world write permission, and overlays the staged tree onto the canonical `/root/K` layout inside a private mount namespace. It never uses personal memory, live audit history, or private deployment state as test input.

The clean-install suite must pass all K, F, and FK tests before publication.

## Refactor rule

Refactors must preserve externally visible schemas and authority boundaries unless the change explicitly introduces a new schema version.

Prefer:
- small modules grouped by one responsibility;
- compatibility facades when moving existing private helpers;
- deterministic validation before side effects;
- explicit error types and bounded inputs;
- synthetic, reproducible test fixtures;
- tests that prove boundary behavior.

Avoid:
- hidden dependencies on a developer's home or live runtime tree;
- runtime data committed as source;
- API keys, tokens, device IDs, or account-specific paths;
- silent fallback that weakens a validation gate.
