# Open-source boundaries

The public source tree may contain architecture, source code, tests, specifications, deployment templates, and synthetic fixtures.

It must not contain:
- personal conversation or long-term memory contents;
- live belief/lesson/personality state derived from a user;
- runtime audit history or evidence archives;
- API keys, credentials, cookies, sessions, or device keys;
- private repository names, account identifiers, hostnames, or device bindings;
- private networking-client or interface history;
- retired provider runtimes, model weights, or provider-specific local configuration;
- local SQLite databases, sockets, PID files, generated logs, or test caches.

A deterministic synthetic test fixture is acceptable when it contains no user data and is required for a reproducible test.

Before publication run both the full tests and `scripts/check_public_tree.py`. Any finding from the hygiene check must be reviewed rather than automatically ignored.

The source scanner checks UTF-8 files and three explicitly named PNG icons, rejects
unreviewed binary/oversize files, and reports filenames without printing matched
secret values. It excludes Git internals and does not establish authorship or
redistribution rights. Publish a fresh history from this sanitized snapshot and
review the icons' provenance separately. A scan PASS is bounded evidence, not a
claim that every possible secret format is detectable.
