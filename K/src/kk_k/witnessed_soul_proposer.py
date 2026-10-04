from __future__ import annotations

from .audit_witness import AuditWitnessError, commit_audit_head, compare_with_witness
from .soul_proposer import SoulProposer, SoulProposerError


class WitnessedSoulProposerError(RuntimeError):
    pass


class WitnessedSoulProposer:
    def __init__(self, *, proposer: SoulProposer, audit_log_path: str, witness_address: str):
        if not isinstance(proposer, SoulProposer):
            raise WitnessedSoulProposerError("invalid base soul proposer")
        if not isinstance(audit_log_path, str) or not audit_log_path:
            raise WitnessedSoulProposerError("invalid audit log path")
        if not isinstance(witness_address, str) or not witness_address.startswith("\0"):
            raise WitnessedSoulProposerError("invalid witness address")
        self._proposer = proposer
        self._audit_log_path = audit_log_path
        self._witness_address = witness_address

    def __call__(self, cycle: int) -> str:
        try:
            action = self._proposer(cycle)
            status = compare_with_witness(self._audit_log_path, address=self._witness_address)
            if status != "LOCAL_AHEAD_ONE":
                raise WitnessedSoulProposerError("audit witness mismatch: " + status)
            commit_audit_head(self._audit_log_path, address=self._witness_address)
            final = compare_with_witness(self._audit_log_path, address=self._witness_address)
            if final != "MATCH":
                raise WitnessedSoulProposerError("audit witness commit not confirmed")
            return action
        except WitnessedSoulProposerError:
            raise
        except (AuditWitnessError, SoulProposerError) as exc:
            raise WitnessedSoulProposerError("witnessed soul proposal failed") from exc
