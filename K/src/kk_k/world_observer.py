"""Bounded autonomous world observer: search only, stdout only, no execution authority."""

from __future__ import annotations
from datetime import datetime, timezone
import json
from .external_tools import execute_external_tool

TOPICS = (
    ("global_affairs", "today major global political economic developments"),
    ("conflicts_emergencies", "today major wars conflicts disasters emergencies world"),
    ("economy_finance", "today major global economy central banks trade energy developments"),
    ("ai_technology", "today major AI technology cybersecurity infrastructure developments"),
    (
        "platform_infrastructure",
        "today major internet cloud platform outages infrastructure incidents",
    ),
)


def observe(*, executor=execute_external_tool) -> dict:
    today = datetime.now(timezone.utc)
    date = f"{today:%B} {today.day} {today.year}"
    queries = (
        ("global_affairs", f"Reuters AP world politics major developments {date}"),
        ("conflicts_emergencies", f"Reuters AP wars conflicts disasters emergencies {date}"),
        ("economy_finance", f"Reuters global economy central banks trade energy {date}"),
        ("ai_technology", f"Reuters AI technology cybersecurity major developments {date}"),
        (
            "platform_infrastructure",
            f"major cloud internet platform outage cybersecurity incident {date}",
        ),
    )
    items = []
    for topic, query in queries:
        try:
            r = executor(
                {
                    "schema": "K.EXTERNAL.TOOL.REQUEST.2",
                    "tool": "browser.search",
                    "args": {"query": query},
                }
            )
            items.append({"topic": topic, "query": query, "verdict": r["verdict"], "receipt": r})
        except Exception:
            items.append({"topic": topic, "query": query, "verdict": "VETO", "receipt": None})
    return {
        "schema": "K.WORLD.OBSERVATION.BATCH.1",
        "observed_at": today.isoformat(),
        "mode": "READ_ONLY_ACTIVE_OBSERVATION",
        "authority": "EVIDENCE_ONLY",
        "topics": items,
    }


def main() -> int:
    print(json.dumps(observe(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
