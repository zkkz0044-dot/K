# First run: offline source validation

Use a disposable Linux VM or WSL distribution. The source gate does not require
an API key or install/start persistent services. Its synthetic runtime state is
for tests only; never copy those acceptance labels into a real deployment.

## Requirements

- Linux with Python 3.13 and pytest 8.3.5.
- bash, util-linux (unshare/mount), and sudo/root for the private mount namespace.
- A readable clone or extracted source tree. Avoid a developer's live installation.

For Debian/Ubuntu, install Python and pytest using your distribution or a dedicated
virtual environment. CI installs the pinned test dependency automatically.

## Verify and test

From the repository root:

```bash
python3 scripts/check_public_tree.py
python3 scripts/verify_sha256.py
sudo env "PATH=$PATH" bash scripts/test_clean_install.sh
```

The gate creates temporary source copies, overlays their reference `/root/K`
layout inside a private mount namespace, and removes them on exit. It runs K, F,
FK, public interface tests, and an offline chat integration test. The integration
test uses real local audit IPC and persisted synthetic conversation data, restarts
the audit server, and checks history and recall. Its model is a synthetic test
provider. It performs no paid inference or external tool request.

Expected final line: `CLEAN_INSTALL_TESTS_PASS`. If any step fails, keep the full
failure output and environment version; do not replace FAIL with an old manifest's
PASS or disable a safety check.

## Executable entry points

Web uploads and some ZIP tools discard executable file modes. Before using CLI
entry points directly in a Linux checkout, restore the bundled shebang scripts:

```bash
python3 scripts/restore_executable_modes.py
```

The offline gate restores these modes only in its disposable staging copy.
The GitHub release ZIP also preserves the Unix executable modes.

## Runtime exploration

The existing systemd templates document the reference `/root/K` installation,
root-owned authority files, F-owned audit state, and isolated K process. They are
not a verified one-command installation product. Review them in a disposable VM
before installing services; the source gate does not start those services.

Credentials are local runtime files under FK/secrets, excluded from source. Model
selection is configured through FK/tools, and external calls need separate runtime
acceptance. `tools/activate_openai.sh` starts services and enables a provider; it
is not an offline validation command. Do not run it merely to test the source tree.

The console and panel require running audit and model IPC dependencies. Report
missing dependencies as unavailable; do not claim a successful model connection
from a configured provider name. For this candidate, full first-run systemd and
real-provider acceptance remain separate from the verified offline source gate.
