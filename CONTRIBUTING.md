# Contributing

Contributions should keep the K / F authority split explicit and testable.

## Before changing code

1. Identify whether the change belongs to K, F, or FK.
2. Preserve existing public schemas unless a new schema version is intentional.
3. Keep deterministic validation before side effects.
4. Do not add runtime state, credentials, personal data, device identifiers, or private infrastructure details.
5. Do not weaken a fail-closed boundary to make a test pass.

## Code organization

Prefer small modules with one clear responsibility. When moving an existing private helper, use a compatibility facade when that avoids unnecessary breakage.

New provider-specific logic belongs behind the model-provider boundary rather than inside K identity or dialogue semantics.

## Required checks

```bash
python3 scripts/check_public_tree.py
./scripts/test_all.sh
```

K, F, FK, and public-interface checks must pass. Before a release, run the isolated
clean-install gate and verify the final SHA256 manifest. Follow docs/FIRST_RUN.md
when testing an uninitialized source tree. Policy-rubric checks are regression
checks, not proof of model reasoning.
