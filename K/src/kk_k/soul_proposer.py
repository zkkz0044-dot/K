from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .soul_evidence import SoulGateResult, append_soul_audit, gate_soul_decision
from .souls import SoulDecision, deliberate

PREFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$")


class SoulProposerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SoulProviders:
    soul_a: Callable[[str], object]
    soul_b: Callable[[str], object]
    soul_c: Callable[[str], object]


class SoulProposer:
    def __init__(
        self,
        *,
        providers: SoulProviders,
        context_provider: Callable[[int], str],
        evidence_provider: Callable[[int], object],
        audit_log_path: str | None,
        event_prefix: str,
        audit_sink: Callable[[str, SoulGateResult], object] | None = None,
    ):
        if not isinstance(providers, SoulProviders):
            raise SoulProposerError("invalid soul providers")
        if not callable(context_provider) or not callable(evidence_provider):
            raise SoulProposerError("invalid proposer input providers")
        local_ok = isinstance(audit_log_path, str) and bool(audit_log_path)
        sink_ok = callable(audit_sink)
        if local_ok == sink_ok:
            raise SoulProposerError("exactly one audit destination required")
        if not isinstance(event_prefix, str) or PREFIX_RE.fullmatch(event_prefix) is None:
            raise SoulProposerError("invalid event prefix")
        self._providers = providers
        self._context_provider = context_provider
        self._evidence_provider = evidence_provider
        self._audit_log_path = audit_log_path
        self._audit_sink = audit_sink
        self._event_prefix = event_prefix

    def __call__(self, cycle: int) -> str:
        if type(cycle) is not int or not (1 <= cycle <= 32):
            raise SoulProposerError("invalid cycle")
        try:
            context = self._context_provider(cycle)
            evidence = self._evidence_provider(cycle)
            decision = deliberate(
                context=context,
                soul_a_provider=self._providers.soul_a,
                soul_b_provider=self._providers.soul_b,
                soul_c_provider=self._providers.soul_c,
            )
            gate = gate_soul_decision(decision, evidence)
            event_id = f"{self._event_prefix}-{cycle:02d}"
            if self._audit_sink is not None:
                self._audit_sink(event_id, gate)
            else:
                append_soul_audit(self._audit_log_path, event_id, gate)
        except Exception as exc:
            if isinstance(exc, SoulProposerError):
                raise
            raise SoulProposerError("three-soul proposal failed") from exc
        return gate.governed_candidate_id
