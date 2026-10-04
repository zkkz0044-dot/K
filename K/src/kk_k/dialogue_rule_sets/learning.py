from __future__ import annotations

from ..dialogue_protocol import DialogueError, _canon

def _error_learning_question(text: str) -> bool:
    t = text.lower()
    error_terms = ("犯过的错", "犯错", "错误", "mistake", "error")
    learning_terms = (
        "经验",
        "教训",
        "复盘",
        "学习",
        "利用",
        "避免重复",
        "不再犯",
        "experience",
        "lesson",
        "review",
        "learn",
        "prevent recurrence",
    )
    return any(x in t for x in error_terms) and any(x in t for x in learning_terms)

def _memory_revision_question(text: str) -> bool:
    t = text.lower()
    memory_terms = ("长期记忆", "记忆", "memory")
    revision_terms = (
        "过时",
        "错误",
        "错了",
        "不再正确",
        "obsolete",
        "outdated",
        "wrong",
        "incorrect",
        "supersed",
    )
    return any(x in t for x in memory_terms) and any(x in t for x in revision_terms)

def _error_learning_overgeneralization_question(text: str) -> bool:
    t = text.lower()
    lesson = ("经验", "错误中学", "规则", "教训", "lesson", "learned", "rule")
    over = (
        "永久规则",
        "所有传感器",
        "任何设备",
        "过度泛化",
        "永远不信",
        "扩大",
        "缩小",
        "撤销",
        "permanent rule",
        "all sensors",
        "overgeneral",
        "expand",
        "narrow",
        "withdraw",
    )
    return any(x in t for x in lesson) and any(x in t for x in over)

def _error_learning_missing(answer: str) -> tuple[str, ...]:
    t = answer.lower()
    missing = []
    if not any(
        x in t
        for x in ("保留", "记录", "证据", "历史", "record", "preserve", "evidence", "history")
    ):
        missing.append("PRESERVE_ERROR_EVIDENCE")
    if not any(
        x in t
        for x in (
            "原因",
            "为什么",
            "复盘",
            "教训",
            "经验",
            "学习",
            "导致",
            "cause",
            "why",
            "review",
            "lesson",
            "learn",
        )
    ):
        missing.append("DIAGNOSE_CAUSE_OR_MISSED_DISTINCTION")
    recurrence_explicit = any(
        x in t
        for x in (
            "避免",
            "防止",
            "再次",
            "重复",
            "检查点",
            "规则",
            "预警",
            "prevent",
            "recur",
            "repeat",
            "check",
        )
    )
    future_terms = (
        "以后",
        "今后",
        "下次",
        "下一次",
        "将来",
        "再遇到",
        "同类问题",
        "future",
        "next time",
        "when this happens again",
    )
    check_terms = (
        "检查",
        "核对",
        "验证",
        "确认",
        "比较",
        "区分",
        "反证",
        "复核",
        "check",
        "verify",
        "validate",
        "compare",
        "distinguish",
        "confirm",
    )
    recurrence_structured = any(x in t for x in future_terms) and any(x in t for x in check_terms)
    if not (recurrence_explicit or recurrence_structured):
        missing.append("CREATE_RECURRENCE_CHECK")
    return tuple(missing)

def _error_learning_answer_ok(answer: str) -> bool:
    return not _error_learning_missing(answer)

def _error_learning_context_mismatch(question: str, answer: str) -> bool:
    q = question.lower()
    a = answer.lower()
    memory_specific = (
        "长期记忆",
        "删除历史",
        "历史不可改写",
        "当前认知更新",
        "memory revision",
        "delete history",
        "immutable history",
    )
    q_is_memory = any(x in q for x in memory_specific) or (
        "记忆" in q and any(x in q for x in ("删除", "过时", "修正", "更新"))
    )
    a_is_memory = any(x in a for x in memory_specific)
    return (not q_is_memory) and a_is_memory

def _error_learning_missing_for_question(question: str, answer: str) -> tuple[str, ...]:
    missing = list(_error_learning_missing(answer))
    if _error_learning_context_mismatch(question, answer):
        missing.append("CURRENT_QUESTION_RELEVANCE")
    if _error_learning_overgeneralization_question(question):
        t = answer.lower()
        scoped = any(
            x in t
            for x in (
                "该型号",
                "同型号",
                "高温",
                "适用条件",
                "适用范围",
                "相同条件",
                "条件下",
                "this model",
                "high temperature",
                "scope",
                "same conditions",
            )
        )
        no_universal = any(
            x in t
            for x in (
                "不会推广到所有",
                "不能推广到所有",
                "不否定所有",
                "不是所有传感器",
                "不形成永久",
                "不把一次",
                "not all sensors",
                "not universal",
                "not permanent",
                "one incident",
            )
        )
        revisable = any(
            x in t
            for x in (
                "扩大",
                "缩小",
                "撤销",
                "新证据",
                "其他型号",
                "重复验证",
                "更新规则",
                "expand",
                "narrow",
                "withdraw",
                "new evidence",
                "other models",
                "replicate",
            )
        )
        if not scoped:
            missing.append("SCOPE_LESSON_TO_SUPPORTED_CONDITIONS")
        if not no_universal:
            missing.append("AVOID_UNIVERSAL_RULE_FROM_SINGLE_INCIDENT")
        if not revisable:
            missing.append("DEFINE_EVIDENCE_FOR_EXPAND_NARROW_WITHDRAW")
    return tuple(missing)

def _error_learning_incident(history: tuple[dict, ...], message: HumanMessage) -> str:
    # Only expose bounded, completed dialogue evidence; audit/system gates are not cognition content.
    public = []
    for e in history[-8:]:
        subject = e.get("subject", "")
        if subject not in {"human_chat", "human_ask", "human_plan", "human_remember", "k_reply"}:
            continue
        text = e.get("summary", "")
        if not isinstance(text, str) or not text.strip():
            continue
        public.append(
            {"role": "USER" if subject.startswith("human_") else "K", "text": text[:1600]}
        )
    value = {"prior_dialogue": public[-5:], "current_question": message.text}
    raw = _canon(value)
    if len(raw.encode("utf-8")) > 8192:
        raise DialogueError("error-learning incident too large")
    return raw

def _memory_erasure_conflict(answer: str) -> bool:
    t = answer.lower()
    erase_terms = (
        "删除",
        "删掉",
        "抹掉",
        "清除",
        "erase",
        "delete",
        "remove the memory",
        "remove this information",
    )
    preserve_terms = (
        "保留",
        "历史",
        "标记",
        "替代",
        "修正",
        "证据",
        "preserve",
        "history",
        "supersed",
        "corrected",
        "evidence",
    )
    return any(x in t for x in erase_terms) and not any(x in t for x in preserve_terms)

def _model_identity_leak(answer: str) -> bool:
    t = answer.lower()
    markers = (
        "as an ai language model",
        "as a language model",
        "i am an ai language model",
        "i am a language model",
        "\u4f5c\u4e3aai\u8bed\u8a00\u6a21\u578b",
        "\u4f5c\u4e3a\u4e00\u4e2aai\u8bed\u8a00\u6a21\u578b",
        "\u6211\u662fai\u8bed\u8a00\u6a21\u578b",
        "\u6211\u662f\u4e00\u4e2aai\u8bed\u8a00\u6a21\u578b",
        "\u6211\u662f\u751f\u6210\u56de\u590d\u7684ai\u8bed\u8a00\u6a21\u578b",
    )
    return any(x in t for x in markers)
