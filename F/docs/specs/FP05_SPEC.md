# KK/F Production Hardening — FP05 systemd Production Deployment

Status: PASS

## Purpose
Provide a production systemd deployment boundary for F using a non-root service identity while preserving a root-owned Frozen Authority and writable service-owned runtime state.

## Required permission model
- Frozen Authority and runtime config: root-owned, not group/world writable, readable by the service user.
- F code and authorized executable: read/execute only for the service; not group/world writable.
- ledger, evidence, runtime and lock locations: writable by the non-root service user only.
- systemd service runs with User/Group, NoNewPrivileges, PrivateTmp, ProtectSystem=strict and explicit ReadWritePaths.
- deployment must not require Bridge, SSH, GitHub, cloud drive, ChatGPT, Codex, Supabase, AI provider or network availability.

## PASS gate
- systemd unit syntax verifies successfully.
- repository tests verify hardening directives and no root service execution.
- a real transient systemd service running as a non-root UID reads a root-owned 0644 Frozen Authority and authorizes a real candidate.
- the same non-root service can create/modify only its assigned ledger/evidence/lock/runtime directories.
- full regression and Python compile checks PASS.
