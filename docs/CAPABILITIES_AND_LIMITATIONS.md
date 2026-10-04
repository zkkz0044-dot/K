# Capabilities and limitations

This snapshot implements a bounded K cognition layer with a separate F execution
and audit layer, connected through FK. It is an early experimental framework.

## Implemented contracts

- Strict schemas for model proposals, action selection, and execution receipts.
- Fixed action and read-only tool allowlists with separate mechanical validation.
- Conversation audit persistence and evidence-linked revision records for beliefs,
  personality, and skills. A record is not proof that the underlying claim is true.
- A/B/C proposal, critique, and advisory judgment around replaceable model output.
- Linux authority-file checks and role-bounded local IPC.

## Explicit limits

- The bundled model provider is OpenAI only. There is no local inference provider.
- Topic selection and answer rubric checks include keyword heuristics. These may
  miss paraphrases or accept superficially compliant prose. They are policy checks,
  never a semantic verifier or a generalization benchmark.
- Some inadequate answers are replaced with programmatic policy guidance. The
  user-visible answer marks that origin, confidence is LOW, and dialogue audit
  records distinguish MODEL_CANDIDATE from PROGRAMMATIC_GUARD. Neither path is
  certified cognition: cognition_verified is false.
- C's verdict is advisory. K's deterministic safety rules remain authoritative.
  UNSUPPORTED_FACT is an advisory model flag, not a completed fact-check.
- Identity continuity is a software data and lineage convention. It does not
  establish consciousness or prove a philosophical claim about personal identity.
- This public snapshot contains no creator's private letter, private history, or
  verified visitor identity. It must not claim to remember those absent records.
- A long paste above 32768 UTF-8 bytes is accepted into the audit and acknowledged;
  that turn does not run the full dialogue reasoning path. Later recall is bounded
  and may not reproduce every part of a long document.
- Several capability references name world-runtime files that are deliberately
  absent from the distribution. Missing runtime observations are not evidence;
  do not restore private data to make an example pass.
- The panel and mobile gateway are for loopback access on a trusted local system.
  They do not supply user authentication, TLS, or a multi-user deployment model.
  Do not expose them through a public reverse proxy. Host/Origin checks and request
  limits reduce local browser and resource risks, but are not user authentication.
- Full systemd service installation and paid model connectivity require separate
  runtime acceptance. Passing the source gate does not mean those gates passed.

## How to evaluate cognition

Keep known regression questions separate from unseen evaluation tasks. Report the
raw model proposal, any retry, the final answer origin, and actual correctness
against independent evidence. Do not count programmatic guidance as successful
model reasoning. Preserve unseen failures and use fresh samples after repairs.
