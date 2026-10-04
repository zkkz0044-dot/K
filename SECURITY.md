# Security

K / F / FK is built around explicit authority boundaries. Security-sensitive changes must preserve those boundaries.

## Reporting a vulnerability

Do not publish credentials, exploit details against a live deployment, personal data, or private infrastructure information in a public issue.

GitHub private vulnerability reporting is enabled for this repository.
Use [Report a vulnerability](https://github.com/zkkz0044-dot/K/security/advisories/new)
to report a potential vulnerability privately to the maintainer. Include the
affected commit, a minimal reproduction, and the observed impact. Do not include
real credentials or personal history in the reproduction.

Supported security review target: this experimental source candidate. The panel
and mobile gateway bind to loopback and provide no user authentication. Use only
on a trusted local machine; public hosting requires a separate security design.

## Security invariants

- Model output is untrusted.
- F does not acquire K identity or cognitive authority.
- IPC peers are authenticated and bounded by role.
- Execution requests are validated before side effects.
- Runtime state and source distribution are separate.
- Secrets are loaded at runtime and are never committed.
- Personal memory, audit history, device bindings, and private host state are excluded from the public tree.

## Source hygiene

Before release run:

```bash
python3 scripts/check_public_tree.py
bash scripts/test_all.sh
```

A hygiene failure must be investigated. Do not add an ignore rule merely to make a release check pass.
