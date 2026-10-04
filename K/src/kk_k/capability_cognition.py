"""Bounded cognition bridge for K's exactly-three read-only external capabilities."""

from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, re
from typing import Callable
from .external_tools import execute_external_tool


class CapabilityCognitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityNeed:
    tool: str
    args: dict | None
    reason: str


_HEALTH = re.compile(
    r"(?:vps|服务器|主机).{0,12}(?:状态|健康|资源|内存|cpu|磁盘|负载)|(?:状态|健康|资源|内存|cpu|磁盘|负载).{0,12}(?:vps|服务器|主机)",
    re.I,
)
_FRESH = re.compile(
    r"(?:最新|今天|外部|网上|搜索|查找|新闻|价格|天气|官网|互联网|web|search|latest|today|(?:当前|现在).{0,8}(?:世界|局势|观察|研究|版本|利率|汇率|领导人)|current.{0,12}(?:world|news|price|weather|version|research|rate))",
    re.I,
)
_FILE = re.compile(
    r"(?:文件|资料|文档|项目状态|project_state|readme|本地记录|知识库|file|document)", re.I
)
_PATH = re.compile(r"(/root/K/K/[A-Za-z0-9_./-]{1,420})")
_OBSERVATION = re.compile(
    r"(?:最近观察|观察记录|世界观察|world observation|recent observation)", re.I
)

_WORLD_SNAPSHOT = re.compile(
    r"(?:2026世界|2026年的世界|世界快照|当前世界背景|world snapshot|world orientation)", re.I
)
_WORLD_SNAPSHOT_PATH = "/root/K/K/world/current/2026-09-06_world_snapshot.md"

_CURRENT_WORLD_MODEL = re.compile(
    r"(?:K.{0,8}(?:怎么看世界|当前认知|世界认知)|当前世界模型|K的世界模型|current world model|K.{0,8}world model)",
    re.I,
)
_CURRENT_WORLD_MODEL_PATH = "/root/K/K/world/current_model/current.md"


def select_capability(text: object) -> CapabilityNeed | None:
    if not isinstance(text, str) or not text.strip():
        raise CapabilityCognitionError("invalid cognition text")
    if _HEALTH.search(text):
        return CapabilityNeed("remote.vps.health", None, "VPS_HEALTH_NEEDED")
    if _CURRENT_WORLD_MODEL.search(text):
        return CapabilityNeed(
            "files.read", {"path": _CURRENT_WORLD_MODEL_PATH}, "K_CURRENT_WORLD_MODEL"
        )
    if _FRESH.search(text):
        q = " ".join(text.strip().split())[:200]
        return CapabilityNeed("browser.search", {"query": q}, "FRESH_EXTERNAL_EVIDENCE_NEEDED")
    if _FILE.search(text):
        m = _PATH.search(text)
        if m:
            return CapabilityNeed(
                "files.read", {"path": m.group(1)}, "EXPLICIT_PROJECT_FILE_NEEDED"
            )
    if _OBSERVATION.search(text):
        return CapabilityNeed(
            "files.read",
            {"path": "/root/K/K/world/observations/latest.md"},
            "WORLD_RECENT_OBSERVATION",
        )
    if _WORLD_SNAPSHOT.search(text):
        return CapabilityNeed(
            "files.read", {"path": _WORLD_SNAPSHOT_PATH}, "WORLD_2026_ORIENTATION_SNAPSHOT"
        )
    world = select_world_foundation(text)
    if world is not None:
        return world
    return None


def acquire_capability_evidence(
    text: object, *, executor: Callable[[object], dict] = execute_external_tool
) -> dict | None:
    need = select_capability(text)
    if need is None:
        return None
    req = (
        {"schema": "K.EXTERNAL.TOOL.REQUEST.1", "tool": need.tool}
        if need.args is None
        else {"schema": "K.EXTERNAL.TOOL.REQUEST.2", "tool": need.tool, "args": need.args}
    )
    try:
        receipt = executor(req)
    except Exception as exc:
        raise CapabilityCognitionError("capability acquisition failed closed") from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("tool") != need.tool
        or receipt.get("verdict") not in {"PASS", "VETO"}
    ):
        raise CapabilityCognitionError("invalid capability receipt")
    return {
        "schema": "K.COGNITION.CAPABILITY_EVIDENCE.1",
        "tool": need.tool,
        "reason": need.reason,
        "verdict": receipt["verdict"],
        "receipt": receipt,
    }


def capability_context(evidence: object) -> str:
    if evidence is None:
        return ""
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != "K.COGNITION.CAPABILITY_EVIDENCE.1"
    ):
        raise CapabilityCognitionError("invalid capability evidence")
    raw = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(raw.encode("utf-8")) > 12000:
        raise CapabilityCognitionError("capability evidence too large")
    return raw


def capability_audit_summary(evidence: object) -> str:
    """Return an audit-safe summary without weakening the full dialogue evidence."""
    raw = capability_context(evidence)
    if len(raw.encode("utf-8")) <= 2048:
        return raw
    receipt = evidence.get("receipt", {}) if isinstance(evidence, dict) else {}
    fk = receipt.get("fk_tool_receipt", {}) if isinstance(receipt, dict) else {}
    compact = {
        "schema": "K.COGNITION.CAPABILITY_AUDIT.1",
        "tool": evidence.get("tool"),
        "reason": evidence.get("reason"),
        "verdict": evidence.get("verdict"),
        "receipt_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "verified": receipt.get("verified") if isinstance(receipt, dict) else None,
        "executed": receipt.get("executed") if isinstance(receipt, dict) else None,
        "fk_verdict": fk.get("verdict") if isinstance(fk, dict) else None,
    }
    summary = json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(summary.encode("utf-8")) > 2048:
        raise CapabilityCognitionError("capability audit summary too large")
    return summary


_WORLD_TOPICS = (
    (
        re.compile(
            r"(?:工程|设计要求|可靠性|故障模式|验证|验收|安全裕量|engineering|reliability|failure mode|verification|validation)",
            re.I,
        ),
        "/root/K/K/world/foundations/06_engineering.md",
        "WORLD_ENGINEERING_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:计算机|软件|硬件|操作系统|网络|协议|进程|文件系统|并发|分布式|computer|software|hardware|operating system|network|protocol|process|filesystem|concurr|distributed)",
            re.I,
        ),
        "/root/K/K/world/foundations/07_computing.md",
        "WORLD_COMPUTING_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:生物|生命|细胞|基因|进化|生态|物种|遗传|biology|life|cell|gene|evolution|ecology|species|inheritance)",
            re.I,
        ),
        "/root/K/K/world/foundations/08_biology_life.md",
        "WORLD_BIOLOGY_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:人类行为|沟通|动机|偏见|信任|冲突|文化差异|human behavior|communication|motivation|bias|trust|conflict)",
            re.I,
        ),
        "/root/K/K/world/foundations/09_human_behavior.md",
        "WORLD_HUMAN_BEHAVIOR_FOUNDATION",
    ),
    (
        re.compile(r"(?:历史|过去|年代|世纪|朝代|战争史|history|historical|century|dynasty)", re.I),
        "/root/K/K/world/foundations/02_history.md",
        "WORLD_HISTORY_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:经济|市场|价格机制|通胀|利率|汇率|货币|供需|利润|econom|market|inflation|interest rate|exchange rate|supply|demand|profit)",
            re.I,
        ),
        "/root/K/K/world/foundations/04_economics.md",
        "WORLD_ECONOMICS_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:科学|实验|假说|理论|测量|统计|相关性|因果关系|science|experiment|hypothesis|theory|measurement|statistic|correlation)",
            re.I,
        ),
        "/root/K/K/world/foundations/05_science.md",
        "WORLD_SCIENCE_FOUNDATION",
    ),
    (
        re.compile(r"(?:地理|国家|地区|城市|边界|时区|geograph|country|territor|timezone)", re.I),
        "/root/K/K/world/foundations/01_geography.md",
        "WORLD_GEOGRAPHY_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:社会|政府|法院|企业|机构|制度|规则|society|government|institution|court)", re.I
        ),
        "/root/K/K/world/foundations/03_society.md",
        "WORLD_SOCIETY_FOUNDATION",
    ),
    (
        re.compile(
            r"(?:证据|可信|真假|来源|因果|事实|置信|evidence|source|caus|truth|reliable)", re.I
        ),
        "/root/K/K/world/foundations/10_evidence_reasoning.md",
        "WORLD_EVIDENCE_FOUNDATION",
    ),
)


def select_world_foundation(text: object) -> CapabilityNeed | None:
    if not isinstance(text, str) or not text.strip():
        raise CapabilityCognitionError("invalid cognition text")
    # Freshness wins: foundations must never suppress a needed current-world search.
    if _HEALTH.search(text) or _FRESH.search(text):
        return None
    for pattern, path, reason in _WORLD_TOPICS:
        if pattern.search(text):
            return CapabilityNeed("files.read", {"path": path}, reason)
    return None
