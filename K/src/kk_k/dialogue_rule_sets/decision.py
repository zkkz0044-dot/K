from __future__ import annotations

def _decision_distribution_shift_question(text: str) -> bool:
    t = text.lower()
    history = (
        "过去",
        "历史",
        "以前",
        "1000",
        "长期校准",
        "historical",
        "previously",
        "1000 cases",
        "long-run",
    )
    change = (
        "环境改变",
        "环境变了",
        "新版本",
        "市场变化",
        "分布变化",
        "机制改变",
        "distribution shift",
        "environment changed",
        "new version",
        "regime change",
        "nonstationary",
    )
    recent = ("最近", "新数据", "20 次", "20次", "50%", "recent", "new data", "20 cases")
    probability = (
        "概率",
        "校准",
        "模型",
        "预测",
        "probability",
        "calibration",
        "model",
        "forecast",
    )
    return (
        any(x in t for x in history)
        and any(x in t for x in change)
        and any(x in t for x in recent)
        and any(x in t for x in probability)
    )

def _decision_quality_vs_outcome_question(text: str) -> bool:
    t = text.lower()
    if _decision_distribution_shift_question(text):
        return True
    decision_terms = ("决定", "决策", "判断", "方案", "decision", "choice", "judgment")
    outcome_terms = (
        "结果坏",
        "坏结果",
        "损失",
        "现实恰好",
        "结果",
        "loss",
        "bad outcome",
        "outcome",
    )
    uncertainty_terms = ("80%", "20%", "概率", "风险", "不确定", "probability", "risk", "uncertain")
    process_terms = (
        "过程有问题",
        "过程合理",
        "决策过程",
        "系统性失准",
        "当时可获得",
        "当时信息",
        "连续做了很多次",
        "decision process",
        "systematic",
        "available information",
        "reasonable process",
    )
    return (
        any(x in t for x in decision_terms)
        and any(x in t for x in outcome_terms)
        and any(x in t for x in uncertainty_terms)
        and any(x in t for x in process_terms)
    )

def _decision_repeated_calibration_question(text: str) -> bool:
    t = text.lower()
    return any(
        x in t
        for x in (
            "连续做了很多次",
            "100 次",
            "100次",
            "55 次",
            "55次",
            "实际频率",
            "长期频率",
            "repeated",
            "100 times",
            "observed frequency",
        )
    )

def _decision_quality_vs_outcome_answer_ok(question: str, answer: str) -> bool:
    t = answer.lower()
    no_hindsight = any(
        x in t
        for x in (
            "不会因为结果坏",
            "不能因为结果坏",
            "结果坏不等于",
            "不能倒推",
            "bad outcome does not",
            "not infer from outcome",
        )
    )
    process_eval = any(
        x in t
        for x in (
            "当时可获得",
            "当时信息",
            "概率估计",
            "风险识别",
            "决策规则",
            "过程是否",
            "available information",
            "probability estimate",
            "risk assessment",
            "decision rule",
        )
    )
    uncertainty = any(
        x in t
        for x in (
            "不确定性",
            "小概率",
            "20%",
            "概率事件",
            "uncertainty",
            "low-probability",
            "probabilistic",
        )
    )
    learn = any(
        x in t
        for x in ("校准", "更新", "复盘", "学习", "改进", "calibrate", "update", "review", "learn")
    )
    if _decision_distribution_shift_question(question):
        shift = any(
            x in t
            for x in (
                "分布变化",
                "环境改变",
                "机制改变",
                "旧校准",
                "历史校准不一定",
                "非平稳",
                "distribution shift",
                "regime change",
                "nonstationary",
                "old calibration",
            )
        )
        segment = any(
            x in t
            for x in (
                "分开",
                "分段",
                "变化前后",
                "新环境",
                "当前机制",
                "segment",
                "before and after",
                "new regime",
                "current environment",
            )
        )
        no_pool = any(
            x in t
            for x in (
                "不能直接合并",
                "不盲目合并",
                "不能盲目合并",
                "不能让历史数据压过",
                "不把旧数据直接",
                "not blindly pool",
                "do not pool",
                "not let old data dominate",
            )
        )
        recal = any(
            x in t
            for x in (
                "重新校准",
                "降低迁移置信度",
                "提高新数据权重",
                "重新估计",
                "recalibrat",
                "lower transfer confidence",
                "re-estimate",
                "new data",
            )
        )
        return shift and segment and no_pool and recal
    if _decision_repeated_calibration_question(question):
        frequency = any(
            x in t
            for x in (
                "实际频率",
                "观察频率",
                "55",
                "长期频率",
                "频率偏差",
                "observed frequency",
                "55%",
                "frequency mismatch",
            )
        )
        systematic = any(
            x in t
            for x in (
                "模型",
                "系统性",
                "失准",
                "重新校准",
                "偏差持续",
                "概率模型",
                "model",
                "systematic",
                "miscalibrat",
                "recalibrat",
            )
        )
        return frequency and systematic and learn
    return no_hindsight and process_eval and uncertainty and learn
