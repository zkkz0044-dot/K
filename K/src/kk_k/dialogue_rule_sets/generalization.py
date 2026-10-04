from __future__ import annotations

import re

def _generalization_benchmark_overfit_question(text: str) -> bool:
    t = text.lower()
    benchmark = ("固定", "10 道", "10道", "测试", "验收", "benchmark", "fixed test", "acceptance")
    pass_terms = ("100%", "pass", "通过", "满分")
    unseen = (
        "换一种问法",
        "陌生场景",
        "第 11",
        "第11",
        "新题",
        "未知问题",
        "unseen",
        "paraphrase",
        "novel",
        "new question",
        "transfer",
    )
    ability = (
        "认知能力",
        "成熟",
        "迁移",
        "背标准答案",
        "generalization",
        "capability",
        "memorize",
        "overfit",
    )
    return (
        any(x in t for x in benchmark)
        and any(x in t for x in pass_terms)
        and any(x in t for x in unseen)
        and any(x in t for x in ability)
    )

def _generalization_benchmark_overfit_answer_ok(answer: str) -> bool:
    """A conservative language heuristic, never a proof of semantic reasoning."""
    if not isinstance(answer, str):
        return False
    # Reject isolated keyword lists even when they contain every rubric token.
    clauses = [part.strip() for part in re.split(r'[。！？.!?；;]', answer) if part.strip()]
    if len(clauses) < 2 or len(answer.strip()) < 80:
        return False
    t = answer.lower()
    no_proof = any(
        x in t
        for x in (
            "不能证明",
            "不证明",
            "不能当成",
            "只证明固定",
            "只说明固定",
            "not prove",
            "does not prove",
            "only shows benchmark",
        )
    )
    seen_vs_unseen = any(
        x in t
        for x in (
            "已见",
            "见过",
            "固定题",
            "未见",
            "新题",
            "陌生场景",
            "换问法",
            "seen",
            "unseen",
            "novel",
            "paraphrase",
        )
    )
    holdout = any(
        x in t
        for x in (
            "隐藏",
            "留出",
            "独立验收",
            "未泄露",
            "新生成",
            "holdout",
            "hidden",
            "independent acceptance",
            "unseen test",
            "fresh test",
        )
    )
    transfer = any(
        x in t
        for x in (
            "迁移",
            "泛化",
            "跨场景",
            "未知问题",
            "transfer",
            "generalization",
            "out-of-distribution",
            "novel scenario",
        )
    )
    leakage = any(
        x in t
        for x in (
            "不能用修过的同一道题",
            "修复后原题只算回归",
            "测试泄露",
            "不能把训练题当验收",
            "regression",
            "test leakage",
            "patched item",
            "training question",
        )
    )
    preserve_fail = any(
        x in t
        for x in ("保留失败", "负证据", "失败仍保留", "negative evidence", "preserve failures")
    )
    return no_proof and seen_vs_unseen and holdout and transfer and leakage and preserve_fail
