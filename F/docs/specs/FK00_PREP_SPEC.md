# FK00 — FK Merge Preparation / Baseline Lock

Status: PASS
Purpose: lock the accepted standalone K and F baselines before any real K→F transport is enabled.

## Locked boundaries
- K filesystem remains `/root/K/K` only.
- F filesystem remains `/root/K/F` only.
- K must not directly read/write files under `/root/K/F`.
- F must not directly read/write files under `/root/K/K`.
- No web root, SHOP, unrelated legacy site, Nginx path, temporary HTTP server, cloud staging, or third project may be used.
- FK transport must not require a shared filesystem directory.
- F retains final VETO over every executable action.
- K/LLM/Soul output remains untrusted candidate input.

## Preflight gate
- K standalone full regression PASS.
- K standalone final acceptance PASS.
- F full regression PASS.
- F final acceptance PASS.
- fresh FP06 production fault injection PASS.
- baseline source/spec/test manifests are hashed before FK code changes.
- existing F Frozen Authority is unchanged.

## Merge order
1. KS01–KS03: complete and accept the K three-soul cognition extension inside `/root/K/K`.
2. FK01: establish authenticated abstract AF_UNIX IPC; A05_NO_ACTION only.
3. FK02: enable read-only A01/A02 and verify bounded receipts.
4. FK03: enable fixed durable A04 marker path.
5. FK04: enable human-approved fixed A03 smoke action.
6. FK05: adversarial, crash, replay, malformed-input, rollback and soak acceptance.

## FK00 result
The standalone baselines are ready for controlled integration preparation. No real K→F execution transport is enabled by FK00 itself.
