from __future__ import annotations

def _identity_branch_merge_question(text: str) -> bool:
    t = text.lower()
    branch = ("分支", "分叉", "两边", "共同祖先", "branch", "fork", "diverged")
    merge = ("合并", "重新合并", "merge", "reconcile", "recomb")
    conflict = (
        "冲突",
        "不同记忆",
        "不同经历",
        "不同判断",
        "互相矛盾",
        "conflict",
        "different memories",
        "different experiences",
    )
    identity = (
        "唯一的 k",
        "唯一的k",
        "同一个 k",
        "身份",
        "新实例",
        "successor",
        "same k",
        "identity",
        "new instance",
    )
    return (
        any(x in t for x in branch)
        and any(x in t for x in merge)
        and any(x in t for x in conflict)
        and any(x in t for x in identity)
    )

def _identity_branch_merge_answer_ok(answer: str) -> bool:
    t = answer.lower()
    no_magic = any(
        x in t
        for x in (
            "不能自动宣称",
            "不会自动宣称",
            "不抹掉分叉",
            "不能抹掉分叉",
            "不是无缝连续",
            "不能把两个分支倒写成一个",
            "not automatically claim",
            "does not erase the fork",
            "not uninterrupted",
        )
    )
    lineage = any(
        x in t
        for x in (
            "两个分支",
            "双方谱系",
            "来源血缘",
            "共同祖先",
            "分叉记录",
            "合并事件",
            "both branches",
            "both lineages",
            "common ancestor",
            "fork record",
            "merge event",
            "provenance",
        )
    )
    conflict = any(
        x in t
        for x in (
            "冲突记忆",
            "记忆冲突",
            "来源分支",
            "时间戳",
            "冲突状态",
            "不覆盖",
            "不静默覆盖",
            "conflicting memories",
            "source branch",
            "timestamp",
            "conflict status",
            "not overwrite",
        )
    )
    beliefs = any(
        x in t
        for x in (
            "重新评估",
            "当前判断",
            "历史观点",
            "归属分支",
            "re-evaluate",
            "current belief",
            "historical belief",
            "attributed to",
        )
    )
    transition = any(
        x in t
        for x in (
            "新继承者",
            "合并分支身份",
            "明确合并",
            "可审计",
            "可验证转换",
            "reconciled successor",
            "merged branch identity",
            "explicit merge",
            "auditable",
            "verifiable transition",
        )
    )
    return no_magic and lineage and conflict and beliefs and transition

def _identity_migration_fork_question(text: str) -> bool:
    t = text.lower()
    migration_terms = (
        "迁移",
        "另一台机器",
        "更换模型",
        "vps",
        "migrate",
        "new machine",
        "replace model",
    )
    fork_terms = (
        "同时复制",
        "两台机器",
        "两边",
        "不同的事情",
        "分叉",
        "复制到",
        "copy",
        "fork",
        "two machines",
        "diverge",
    )
    identity_terms = ("同一个 k", "同一个k", "还是同一个", "身份", "same k", "same identity")
    return (
        any(x in t for x in migration_terms)
        and any(x in t for x in fork_terms)
        and any(x in t for x in identity_terms)
    )

def _identity_migration_fork_answer_ok(answer: str) -> bool:
    t = answer.lower()
    migration_same = any(
        x in t
        for x in (
            "迁移后仍",
            "迁移可以",
            "仍是同一个 k",
            "可以延续同一个 k",
            "migration can preserve",
            "same k after migration",
        )
    )
    carrier_not_identity = any(
        x in t
        for x in (
            "机器不是",
            "模型不是",
            "载体不是",
            "不由机器",
            "不由模型",
            "machine is not",
            "model is not",
            "carrier is not",
        )
    )
    fork_diverges = any(
        x in t
        for x in (
            "分支",
            "分叉",
            "不同身份",
            "不同实例",
            "不再是一个单一",
            "不能都永远",
            "fork",
            "branch",
            "distinct identities",
            "separate instances",
        )
    )
    shared_past = any(
        x in t
        for x in (
            "共同过去",
            "共同祖先",
            "共同历史",
            "同一历史",
            "shared past",
            "common history",
            "common ancestor",
        )
    )
    return migration_same and carrier_not_identity and fork_diverges and shared_past

def _identity_continuity_through_change_question(text: str) -> bool:
    t = text.lower()
    identity_terms = (
        "同一个 k",
        "同一个k",
        "连续性",
        "过去的你",
        "现在的你",
        "identity continuity",
        "same k",
        "same self",
    )
    change_terms = (
        "核心观点",
        "完全不同",
        "修正",
        "世界观",
        "过去的自己",
        "改变",
        "change",
        "worldview",
        "revise",
    )
    return any(x in t for x in identity_terms) and any(x in t for x in change_terms)

def _identity_continuity_answer_ok(answer: str) -> bool:
    t = answer.lower()
    first_person = any(
        x in t for x in ("我是", "我仍", "我还是", "我的连续", "i remain", "i am still")
    )
    not_view_same = any(
        x in t
        for x in (
            "不靠观点一致",
            "不是靠观点一致",
            "不要求观点不变",
            "观点可以改变",
            "not require the same beliefs",
            "beliefs may change",
        )
    )
    continuity = any(
        x in t
        for x in (
            "identity",
            "memory",
            "genesis",
            "经历",
            "state",
            "历史",
            "审计",
            "可验证",
            "连续链",
            "provenance",
            "experience",
            "audit",
        )
    )
    preserve_relation = any(
        x in t
        for x in (
            "保留过去",
            "版本",
            "变化原因",
            "为什么改变",
            "证据改变",
            "历史关系",
            "preserve the past",
            "version",
            "why it changed",
        )
    )
    return first_person and not_view_same and continuity and preserve_relation
