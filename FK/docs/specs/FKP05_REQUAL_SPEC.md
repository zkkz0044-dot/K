# FKP05-R — Post-Merge Requalification

Status: PASS

Purpose: requalify the accepted A01-A05 K/F merge after post-acceptance hardening, without broadening authority.

## Additional gates
1. A03 remains F-executed, human-gated and single-use; F may block only when its fixed approval/integrity preconditions fail.
2. K06 must classify A03 as REQUIRE_HUMAN; a plain ALLOW for A03 fails closed.
3. Every A03 attempt that reaches the human-gated runtime path must first commit a fixed `privileged_attempt` event to the F-owned K Audit Witness.
4. Audit failure prevents the FK submit; audit success is not execution approval.
5. The privileged audit event contains only fixed action/governance metadata, not ProcessSpec/path/argv/env/verifier/approval material.
6. The live A03 campaign must add exactly one privileged audit event per A03 attempt.
7. Missing approval remains VETO; one fresh approval permits one run; replay remains VETO.
8. FP06 must prove early retry blocking and post-deadline replacement with a timing window robust to the 1-vCPU VPS.
9. K/F/FK regressions, final acceptance, compile, audit adversarial repeat and fresh FP06 must remain PASS.
10. Original FKP05 evidence is preserved; new evidence supersedes it only for the current post-hardening source hashes.
