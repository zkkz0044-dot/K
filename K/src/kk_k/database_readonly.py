"""Fail-closed read-only database contract for FKP08."""

from __future__ import annotations
from dataclasses import dataclass
import re

SCHEMA = "K.DB.READ.REQUEST.1"
RECEIPT_SCHEMA = "K.DB.READ.RECEIPT.1"
MAX_LIMIT = 100
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


class DatabaseReadError(ValueError):
    pass


@dataclass(frozen=True)
class DatabaseReadRequest:
    dataset: str
    view: str
    filters: dict
    limit: int


def parse_request(value: object) -> DatabaseReadRequest:
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "dataset",
        "view",
        "filters",
        "limit",
    }:
        raise DatabaseReadError("exact database request fields required")
    if value.get("schema") != SCHEMA:
        raise DatabaseReadError("invalid database request schema")
    dataset = value["dataset"]
    view = value["view"]
    filters = value["filters"]
    limit = value["limit"]
    if not isinstance(dataset, str) or _NAME.fullmatch(dataset) is None:
        raise DatabaseReadError("invalid dataset")
    if not isinstance(view, str) or _NAME.fullmatch(view) is None:
        raise DatabaseReadError("invalid view")
    if not isinstance(filters, dict) or len(filters) > 8:
        raise DatabaseReadError("invalid filters")
    if type(limit) is not int or not (1 <= limit <= MAX_LIMIT):
        raise DatabaseReadError("invalid limit")
    clean = {}
    for k, v in filters.items():
        if not isinstance(k, str) or _NAME.fullmatch(k) is None:
            raise DatabaseReadError("invalid filter key")
        if not isinstance(v, (str, int, float, bool)) and v is not None:
            raise DatabaseReadError("invalid filter value")
        if isinstance(v, str) and len(v) > 200:
            raise DatabaseReadError("filter value too long")
        clean[k] = v
    return DatabaseReadRequest(dataset, view, clean, limit)


def reject_raw_sql(value: object) -> None:
    """Explicit guard: no SQL text is ever part of the contract."""
    if isinstance(value, str):
        raise DatabaseReadError("raw SQL is forbidden")
    if isinstance(value, dict) and any(
        str(k).lower() in {"sql", "query", "statement"} for k in value
    ):
        raise DatabaseReadError("raw SQL field is forbidden")


def backend_unavailable_receipt(req: DatabaseReadRequest) -> dict:
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "VETO",
        "dataset": req.dataset,
        "view": req.view,
        "reason_code": "DATABASE_BACKEND_UNBOUND",
        "rows": [],
    }
