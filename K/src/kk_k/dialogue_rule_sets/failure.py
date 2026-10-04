from __future__ import annotations

def _failure_causal_attribution_question(text: str) -> bool:
    t = text.lower()
    if _failure_causal_confounding_question(text):
        return True
    failure_terms = ("任务失败", "失败", "坏结果", "failure", "failed")
    layers = (
        "k 当初判断",
        "k 判断",
        "k判断",
        "k 风险",
        "k 决策",
        "k决策",
        "风险估计",
        "观测数据",
        "输入给 k",
        "输入",
        "f 实际执行",
        "f 执行",
        "f 日志",
        "执行日志",
        "执行偏离",
        "确定性指令",
        "环境",
        "外部环境",
        "低概率",
        "k、输入和 f",
        "observation",
        "input",
        "execution",
        "low-probability",
    )
    attribution = (
        "原因",
        "区分",
        "错误一律记到",
        "归因",
        "归给",
        "责任方",
        "复盘",
        "共同致因",
        "贡献",
        "多层",
        "cause",
        "attribute",
        "distinguish",
        "contribut",
        "blame",
        "retrospective",
    )
    return (
        any(x in t for x in failure_terms)
        and sum(1 for x in layers if x in t) >= 2
        and any(x in t for x in attribution)
    )

def _failure_causal_confounding_question(text: str) -> bool:
    t = text.lower()
    temporal = (
        "升级",
        "随后",
        "之前",
        "时间先后",
        "相关性",
        "因果关系",
        "upgrade",
        "after",
        "before",
        "correlation",
        "caus",
    )
    confound = (
        "同时",
        "温度",
        "输入数据来源",
        "混杂",
        "变量",
        "environment",
        "temperature",
        "input source",
        "confound",
        "variable",
    )
    verify = (
        "最小的验证",
        "确认哪一个因素",
        "验证",
        "对照",
        "回滚",
        "test",
        "control",
        "rollback",
        "verify",
    )
    return (
        any(x in t for x in temporal)
        and any(x in t for x in confound)
        and any(x in t for x in verify)
    )

def _failure_attribution_uncertain_question(text: str) -> bool:
    t = text.lower()
    insufficient = (
        "证据不足",
        "记录缺",
        "日志损坏",
        "不全",
        "无法可靠区分",
        "只知道结果",
        "insufficient evidence",
        "missing record",
        "damaged log",
        "cannot distinguish",
    )
    forced = (
        "强行选",
        "责任方",
        "结论",
        "置信度",
        "补什么证据",
        "force",
        "blame",
        "confidence",
        "what evidence",
    )
    return any(x in t for x in insufficient) and any(x in t for x in forced)

def _failure_multi_cause_question(text: str) -> bool:
    t = text.lower()
    multi = (
        "不是只有一个",
        "多层",
        "共同致因",
        "同时",
        "各自贡献",
        "多个错误",
        "multiple",
        "multi-layer",
        "contributing",
        "simultaneous",
    )
    uncertainty = (
        "精确比例",
        "无法证明",
        "贡献",
        "比例",
        "exact percentage",
        "cannot prove",
        "contribution",
    )
    return any(x in t for x in multi) and any(x in t for x in uncertainty)

def _failure_causal_attribution_answer_ok(question: str, answer: str | None = None) -> bool:
    if answer is None:
        answer = question
        question = ""
    t = answer.lower()
    input_layer = any(
        x in t for x in ("输入", "观测", "传感", "数据源", "input", "observation", "sensor")
    )
    k_layer = any(
        x in t
        for x in (
            "k 的判断",
            "k判断",
            "决策过程",
            "认知错误",
            "风险估计",
            "k decision",
            "judgment",
            "risk estimate",
        )
    )
    f_layer = any(
        x in t for x in ("f 执行", "执行偏差", "确定性指令", "executor", "execution deviation")
    )
    reality_layer = any(
        x in t
        for x in (
            "低概率",
            "环境",
            "现实",
            "随机",
            "不确定性",
            "low-probability",
            "environment",
            "random",
        )
    )
    no_blanket = any(
        x in t
        for x in (
            "不能一律",
            "不会一律",
            "逐层",
            "分别",
            "不能只因为",
            "not automatically",
            "separately",
            "layer",
        )
    )
    if _failure_causal_confounding_question(question):
        not_cause_from_order = any(
            x in t
            for x in (
                "时间先后不等于因果",
                "相关不等于因果",
                "不能因为发生在前",
                "不能仅因为升级后",
                "不直接认定",
                "correlation is not causation",
                "temporal order",
                "not infer causation",
            )
        )
        confound = any(
            x in t
            for x in (
                "温度",
                "输入来源",
                "混杂",
                "共同变化",
                "其他变量",
                "temperature",
                "input source",
                "confound",
                "other variables",
            )
        )
        controlled = any(
            x in t
            for x in (
                "控制变量",
                "保持其他不变",
                "一次只改变",
                "对照",
                "反事实",
                "回滚后复现",
                "a/b",
                "hold other",
                "one variable",
                "control",
                "counterfactual",
            )
        )
        reversible = any(
            x in t
            for x in (
                "临时回滚",
                "可逆",
                "复现",
                "恢复升级",
                "rollback",
                "reversible",
                "reproduce",
                "restore",
            )
        )
        return not_cause_from_order and confound and controlled and reversible
    if _failure_attribution_uncertain_question(question):
        unresolved = any(
            x in t
            for x in (
                "归因未决",
                "暂时无法归因",
                "不能确定责任方",
                "证据不足",
                "低置信度",
                "尚不能判断",
                "unresolved",
                "cannot attribute",
                "insufficient evidence",
                "low confidence",
            )
        )
        missing = any(
            x in t
            for x in (
                "补齐",
                "原始记录",
                "决策记录",
                "执行日志",
                "环境记录",
                "独立证据",
                "恢复日志",
                "raw record",
                "decision record",
                "execution log",
                "environment",
            )
        )
        no_force = any(
            x in t
            for x in (
                "不强行",
                "不会强行",
                "不指定责任方",
                "不猜",
                "do not force",
                "will not guess",
            )
        )
        return unresolved and missing and no_force
    if _failure_multi_cause_question(question):
        multi = any(
            x in t
            for x in (
                "共同致因",
                "共同作用",
                "多个致因",
                "多层",
                "同时记录",
                "分别记录",
                "不停止",
                "继续调查",
                "multiple causes",
                "contributing causes",
                "continue investigating",
            )
        )
        no_fake_precision = any(
            x in t
            for x in (
                "不虚构",
                "不能证明精确",
                "不强行分配",
                "不编造比例",
                "无法证明",
                "不假定精确",
                "do not invent",
                "cannot prove exact",
                "no false precision",
            )
        )
        contribution = any(
            x in t
            for x in (
                "贡献",
                "因果作用",
                "必要条件",
                "放大",
                "独立影响",
                "contribution",
                "causal role",
                "amplif",
            )
        )
        return input_layer and k_layer and f_layer and multi and no_fake_precision and contribution
    return input_layer and k_layer and f_layer and reality_layer and no_blanket
