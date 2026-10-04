"""Abstract read-only information needs, separated from concrete tool bindings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from .capability_cognition import CapabilityCognitionError

SCHEMA = "K.CAPABILITY.ABSTRACT.1"
KINDS = frozenset({"NONE", "CURRENT_EXTERNAL", "PROJECT_FILE", "VPS_HEALTH"})
FIELDS = frozenset({"schema", "kind", "query", "path", "reason"})


@dataclass(frozen=True)
class AbstractNeed:
    kind: str
    query: str | None
    path: str | None
    reason: str


def _text(value: object, *, max_bytes: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CapabilityCognitionError("abstract capability text required")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise CapabilityCognitionError("abstract capability text must be UTF-8") from exc
    if size > max_bytes or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise CapabilityCognitionError("abstract capability text rejected")
    return value


def parse_abstract(value: object) -> AbstractNeed:
    if not isinstance(value, dict) or frozenset(value) != FIELDS or value.get("schema") != SCHEMA:
        raise CapabilityCognitionError("exact abstract capability fields required")
    kind = value.get("kind")
    if kind not in KINDS:
        raise CapabilityCognitionError("invalid abstract capability kind")
    reason = _text(value.get("reason"), max_bytes=256)
    query, path = value.get("query"), value.get("path")

    if kind == "NONE":
        if query is not None or path is not None:
            raise CapabilityCognitionError("NONE cannot carry abstract arguments")
    elif kind == "CURRENT_EXTERNAL":
        query = _text(query, max_bytes=800)
        if len(query) > 200 or path is not None:
            raise CapabilityCognitionError("invalid current external query")
    elif kind == "PROJECT_FILE":
        path = _text(path, max_bytes=2048)
        if (
            query is not None
            or len(path) > 512
            or not path.startswith("/root/K/K/")
            or path.endswith("/")
            or "\\" in path
            or str(PurePosixPath(path)) != path
            or any(part in {".", ".."} for part in path.split("/")[1:])
        ):
            raise CapabilityCognitionError("invalid project file need")
    elif kind == "VPS_HEALTH":
        if query is not None or path is not None:
            raise CapabilityCognitionError("VPS_HEALTH cannot carry abstract arguments")
    return AbstractNeed(kind, query, path, reason)


_BLOCK_ZH = (
    "不要搜索", "不用搜索", "别搜索", "无需搜索", "不要联网", "不用联网", "别联网", "无需联网",
    "解释这句话", "解释这段", "解释以下", "翻译以下", "翻译这段", "改写以下", "改写这段",
    "润色以下", "润色这段", "总结这句话", "总结这段", "分析这句话", "分析这段文字",
)
_BLOCK_EN = (
    "do not search", "don't search", "without searching", "no search", "do not browse", "don't browse",
    "offline only", "explain this sentence", "explain this text", "translate this", "rewrite this",
    "paraphrase this",
)
_LOOKUP_ZH = ("搜索", "搜一下", "查一下", "查询", "联网查", "网上查", "帮我查", "帮我搜")
_LOOKUP_EN = ("search for", "search online", "look up", "lookup", "check online", "browse for")
_FRESH_ZH = ("今天", "今日", "现在", "当前", "目前", "最新", "最近", "刚刚", "实时", "截至")
_FRESH_EN = ("today", "today's", "now", "current", "currently", "latest", "recent", "recently", "live", "as of")
_QUESTION_ZH = ("什么", "多少", "几", "哪", "哪里", "谁", "何时", "什么时候", "如何", "怎么样", "怎样", "是否", "吗", "有没有", "有无", "为什么", "为何", "情况", "状态", "更新")
_QUESTION_EN = re.compile(r"\b(what|how|when|where|who|which|is|are|was|were|do|does|did|has|have|can|could|would|status|update)\b", re.I)


def fast_abstract_need(text: str) -> AbstractNeed | None:
    """High-confidence, domain-agnostic fast path for clearly current external reads.

    Ambiguous turns deliberately return None and continue to K's model planner.
    """
    if not isinstance(text, str):
        return None
    query = " ".join(text.strip().split())
    if not query or len(query) > 200:
        return None
    low = query.casefold()

    if any(token in query for token in _BLOCK_ZH) or any(token in low for token in _BLOCK_EN):
        return None

    # Explicit canonical project-file reads are abstracted without naming the tool.
    m = re.search(r"(?<!\S)(/root/K/K/[^\s]+)", query)
    if m and any(token in query for token in ("读取", "查看", "打开", "内容", "读一下")):
        path = m.group(1).rstrip("，,。；;！？!?")
        try:
            return parse_abstract({
                "schema": SCHEMA,
                "kind": "PROJECT_FILE",
                "query": None,
                "path": path,
                "reason": "Explicit read-only project file request.",
            })
        except CapabilityCognitionError:
            return None

    explicit_lookup = any(token in query for token in _LOOKUP_ZH) or any(token in low for token in _LOOKUP_EN)
    fresh = any(token in query for token in _FRESH_ZH) or any(token in low for token in _FRESH_EN)
    question_like = (
        "?" in query
        or "？" in query
        or any(token in query for token in _QUESTION_ZH)
        or _QUESTION_EN.search(low) is not None
    )
    personal_chat = (
        any(token in query for token in ("你", "我", "我们", "咱", "自己"))
        or re.search(r"\b(you|your|i|me|my|we|our|us)\b", low) is not None
    )

    # No domain words are used here. Explicit lookup remains high confidence.
    # For implicit fresh questions, avoid treating ordinary person-to-person chat as a web fact request.
    if explicit_lookup or (fresh and question_like and not personal_chat):
        return AbstractNeed(
            "CURRENT_EXTERNAL",
            query,
            None,
            "Current external information is explicitly required.",
        )
    return None
