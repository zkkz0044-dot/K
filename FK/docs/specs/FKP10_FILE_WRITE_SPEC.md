# FKP10 — Bounded File Write

Candidate tool: `files.write`.
Risk: L1.

Rules:
- F-owned execution only.
- Create-only; overwrite, append, rename and delete are denied.
- Root is fixed to `/root/K/K/workspace/`.
- Allowed extensions: `.txt`, `.md`, `.json`.
- UTF-8 text only; maximum 16 KiB.
- Hidden paths, traversal, symlink-parent escape and arbitrary paths are denied.
- Receipt contains path, byte count, SHA-256 and created=true; no shell command is accepted.

Accepted after K verifier, FK Tool Gateway integration, GPT/K DynamicUser live writes, root-direct denial, overwrite and symlink-escape veto tests, systemd single-path write confinement, and full K/F/FK regression.
