# Architecture

## Core separation

K and F have intentionally different authority.

**K** may reason, revise beliefs, form decisions, and maintain identity continuity. Model output is treated as an untrusted cognitive proposal rather than as K itself.

**F** may execute only bounded, validated operations. F does not decide what K should want and does not acquire K's identity or personality.

**FK** transports requests, receipts, audit state, and model-provider traffic across that boundary. Its job is to preserve the separation, not blur it.

## Main code areas

### K

`K/src/kk_k/` contains identity, cognition, dialogue, beliefs, skills, world-state interpretation, capability planning, and audit-facing clients.

Dialogue validation rules are split by concern under `dialogue_rule_sets/`; `dialogue_rules.py` remains a compatibility facade. Deterministic answer fallbacks and hard-risk completion logic live in `dialogue_guards.py`, leaving `dialogue_souls.py` focused on orchestration of proposer/critic/judge flow.

### F

`F/src/kk_f/` contains deterministic runtime logic, audit witnesses, execution gateways, supervision, release guards, and evidence handling.

Audit request parsing is isolated in `fk_audit_protocol.py`; `fk_audit_gateway.py` focuses on state projection, dispatch, peer policy, and transport. Personality, belief, and skill state machines are separated under `kk_f/cognition/`; `fk_audit_cognition.py` is retained as a compatibility facade.

### FK

`FK/model_runtime/` contains model-provider routing and relay logic.

Wire framing and model-request validation are isolated in `gateway_protocol.py`; model-role prompt/output policy is isolated in `role_policy.py`; provider selection, IPC authentication, and daemon lifecycle remain in `model_gateway_daemon.py`.

## Stability rule

Public schemas and boundary contracts should change deliberately and version explicitly. Internal module layout may evolve without changing those contracts.
