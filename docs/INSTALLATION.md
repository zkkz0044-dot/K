# Installation convention

The current deployment templates use `/root/K` as the reference installation prefix:

```text
/root/K/K
/root/K/F
/root/K/FK
```

This path is a project layout convention. It is not a user account, device identifier, hostname, or private deployment record.

Runtime services may expose read-only bind views under `/run/kk-*`. Those paths are part of the sandbox and IPC design.

## Source development

The repository-wide test runner does not require installing the Python packages globally. It sets source paths explicitly:

```bash
./scripts/test_all.sh
```

## Release direction

Future packaging may parameterize the installation prefix. Until that work is complete, deployment templates should treat `/root/K` as the documented reference layout rather than silently inventing alternative roots.
