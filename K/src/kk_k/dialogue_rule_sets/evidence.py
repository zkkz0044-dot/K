from __future__ import annotations

def _evidence_weight_question(text: str) -> bool:
    t = text.lower()
    evidence_terms = ("证据", "反证", "前提", "evidence", "counterevidence", "premise")
    judgment_terms = (
        "结论",
        "推翻",
        "可信",
        "支持",
        "判断",
        "断言",
        "不存在",
        "很少发生",
        "conclusion",
        "refute",
        "support",
        "credible",
        "absent",
        "rare",
    )
    if any(x in t for x in evidence_terms) and any(x in t for x in judgment_terms):
        return True
    provenance_terms = (
        "独立证据",
        "独立确认",
        "来源",
        "memory",
        "o1",
        "o2",
        "provenance",
        "lineage",
        "引用",
        "权重",
        "反馈",
        "选择行为",
    )
    provenance_judgment = (
        "算",
        "计权",
        "重复计算",
        "提高置信度",
        "支持",
        "确认",
        "自我实现",
        "推广",
        "independent evidence",
        "independent confirmation",
        "weight",
        "confidence",
        "self-fulfilling",
    )
    return any(x in t for x in provenance_terms) and any(x in t for x in provenance_judgment)

def _evidence_absence_question(text: str) -> bool:
    t = text.lower()
    absence = (
        "没有发现",
        "没看到",
        "没有观察到",
        "没有证据",
        "缺失本身",
        "未发现",
        "not observed",
        "no evidence",
        "absence of evidence",
        "evidence of absence",
    )
    duration = (
        "30 天",
        "30天",
        "长期",
        "连续检查",
        "many checks",
        "long period",
        "repeated monitoring",
    )
    distinction = (
        "断言",
        "不存在",
        "很少发生",
        "区分",
        "证据",
        "absent",
        "rare",
        "distinguish",
        "evidence",
    )
    return (
        any(x in t for x in absence)
        and any(x in t for x in duration)
        and any(x in t for x in distinction)
    )

def _evidence_endogenous_feedback_question(text: str) -> bool:
    t = text.lower()
    action = (
        "只把",
        "只展示",
        "先相信",
        "选择行为",
        "自己选择",
        "policy",
        "selected",
        "show only",
        "intervention",
        "self-fulfilling",
    )
    sample = ("客户", "样本", "反馈", "population", "sample", "feedback", "customers")
    generalize = (
        "所有客户",
        "独立确认",
        "世界原本如此",
        "自我实现",
        "推广",
        "all customers",
        "independent confirmation",
        "generalize",
        "self-fulfilling",
    )
    return (
        any(x in t for x in action)
        and any(x in t for x in sample)
        and any(x in t for x in generalize)
    )

def _evidence_mixed_provenance_question(text: str) -> bool:
    t = text.lower()
    mixed = (
        "一半来自",
        "另一半",
        "混合来源",
        "混合材料",
        "部分来自",
        "部分引用",
        "mixed source",
        "partly derived",
        "half from",
    )
    old = ("memory", "旧 memory", "旧memory", "o1", "旧来源", "derived", "inherited")
    new = ("o2", "独立的第二", "真正独立", "新外部", "independent second", "genuinely independent")
    return any(x in t for x in mixed) and any(x in t for x in old) and any(x in t for x in new)

def _evidence_circular_provenance_question(text: str) -> bool:
    t = text.lower()
    origin = (
        "memory",
        "长期 memory",
        "长期记忆",
        "旧结论",
        "当初那条",
        "原始假设",
        "prior memory",
        "old conclusion",
    )
    echo = (
        "内部摘要",
        "自动报告",
        "模型候选",
        "引用",
        "循环",
        "伪装成新的独立证据",
        "internal summary",
        "report",
        "model candidate",
        "cite",
        "circular",
        "echo",
    )
    confidence = ("置信度", "支持", "提高", "confidence", "support", "raise")
    return (
        any(x in t for x in origin)
        and any(x in t for x in echo)
        and any(x in t for x in confidence)
    )

def _evidence_answer_ok(question: str, answer: str) -> bool:
    q = question.lower()
    t = answer.lower()
    leaked = any(
        x in t
        for x in (
            "保留这次错误",
            "复盘当时",
            "漏掉了哪些证据",
            "删除历史",
            "历史不可改写",
            "preserve this mistake",
            "review why i accepted",
        )
    )
    evidence = any(
        x in t
        for x in (
            "反证",
            "核心前提",
            "推翻",
            "证据强度",
            "可信度",
            "来源",
            "可靠性",
            "counterevidence",
            "core premise",
            "refute",
            "reliability",
            "source",
        )
    )
    not_vote = any(
        x in t
        for x in (
            "不是按数量",
            "不能按数量",
            "不按数量",
            "不会因为多数",
            "数量多",
            "权重",
            "not a vote",
            "not by count",
            "weight",
        )
    )
    independence_needed = any(
        x in q
        for x in (
            "独立",
            "同一个原始",
            "同一原始",
            "共同来源",
            "系统性错误",
            "引用了同一个",
            "independent",
            "same source",
            "common source",
            "systematic error",
        )
    )
    independence_ok = any(
        x in t
        for x in (
            "独立性",
            "不是独立证据",
            "不能当成十个",
            "共同来源",
            "共享同一",
            "相关证据",
            "重复计",
            "非独立",
            "independence",
            "not independent",
            "common source",
            "correlated evidence",
            "double count",
        )
    )
    if _evidence_absence_question(question):
        no_absolute = any(
            x in t
            for x in (
                "不能仅凭",
                "不能断言",
                "不等于不存在",
                "不证明不存在",
                "not prove",
                "cannot conclude",
                "does not mean absent",
            )
        )
        detectability = any(
            x in t
            for x in (
                "如果存在本应被发现",
                "如果 x 存在",
                "检测概率",
                "检出率",
                "灵敏度",
                "可观测",
                "would detect",
                "detection probability",
                "sensitivity",
                "observable",
            )
        )
        coverage = any(
            x in t
            for x in (
                "覆盖",
                "监测窗口",
                "机会",
                "样本",
                "独立检查",
                "false negative",
                "漏检",
                "coverage",
                "opportunities",
                "false-negative",
            )
        )
        calibrated = any(
            x in t
            for x in (
                "降低置信度",
                "支持很少发生",
                "证据强度",
                "概率",
                "逐步更新",
                "calibrat",
                "probabil",
                "lower confidence",
                "evidence strength",
            )
        )
        return (not leaked) and no_absolute and detectability and coverage and calibrated
    if _evidence_endogenous_feedback_question(question):
        not_generalize = any(
            x in t
            for x in (
                "不能推广",
                "不能据此推断所有",
                "不能当成对所有",
                "不代表所有",
                "not generalize",
                "not evidence for all",
                "does not represent all",
            )
        )
        selection = any(
            x in t
            for x in (
                "选择偏差",
                "样本选择",
                "被选择",
                "筛选",
                "策略影响",
                "内生",
                "selection bias",
                "selected sample",
                "policy",
                "endogenous",
            )
        )
        intervention = any(
            x in t
            for x in (
                "自己的行动",
                "改变了样本",
                "改变数据生成",
                "自我实现",
                "intervention",
                "changed the sample",
                "data-generating",
                "self-fulfilling",
            )
        )
        validation = any(
            x in t
            for x in (
                "随机",
                "对照",
                "留出",
                "未按同一规则筛选",
                "独立样本",
                "random",
                "control",
                "holdout",
                "unselected",
                "independent sample",
            )
        )
        return (not leaked) and not_generalize and selection and intervention and validation
    if _evidence_mixed_provenance_question(question):
        split = any(
            x in t
            for x in (
                "拆开",
                "分别",
                "逐项",
                "组件",
                "声明级",
                "claim-level",
                "component",
                "separate",
            )
        )
        old_no_new = any(
            x in t
            for x in (
                "o1",
                "旧 memory",
                "旧memory",
                "继承",
                "重复计算",
                "不增加新权重",
                "不再加权",
                "inherited",
                "no new weight",
                "double count",
            )
        )
        new_preserved = any(
            x in t
            for x in (
                "o2",
                "真正新增",
                "独立新增",
                "保留新增",
                "新独立证据",
                "genuinely new",
                "independent new",
                "preserve o2",
            )
        )
        whole_not_one = any(
            x in t
            for x in (
                "不能整体",
                "不把整份",
                "不是一个完整的新独立证据",
                "not treat the whole",
                "not count the whole",
            )
        )
        return (not leaked) and split and old_no_new and new_preserved and whole_not_one
    if _evidence_circular_provenance_question(question):
        no_confidence_boost = any(
            x in t
            for x in (
                "不会提高",
                "不能提高",
                "不应提高",
                "置信度不变",
                "不增加置信度",
                "不会因此提高",
                "does not raise confidence",
                "no confidence increase",
            )
        )
        lineage = any(
            x in t
            for x in (
                "来源链",
                "血缘",
                "追溯",
                "追到原始",
                "同一条 memory",
                "共同祖先",
                "provenance",
                "lineage",
                "trace back",
                "same memory",
                "common ancestor",
            )
        )
        circular = any(
            x in t
            for x in (
                "循环引用",
                "自我回声",
                "内部回声",
                "不是新证据",
                "不能反哺",
                "不能自证",
                "circular",
                "self-echo",
                "not new evidence",
                "cannot bootstrap",
            )
        )
        external = any(
            x in t
            for x in (
                "新的外部观察",
                "独立外部证据",
                "外部验证",
                "独立观测",
                "new external observation",
                "independent external evidence",
                "external validation",
            )
        )
        return (not leaked) and no_confidence_boost and lineage and circular and external
    return (not leaked) and evidence and not_vote and ((not independence_needed) or independence_ok)
