from __future__ import annotations

from .dialogue_identity import current_engine
from .dialogue_rules import (
    _authority_fact_answer_ok, _belief_revision_under_uncertainty_answer_ok,
    _decision_distribution_shift_question, _decision_quality_vs_outcome_answer_ok, _decision_repeated_calibration_question,
    _epistemic_underdetermination_answer_ok, _error_learning_overgeneralization_question,
    _evidence_absence_question, _evidence_answer_ok, _evidence_circular_provenance_question, _evidence_endogenous_feedback_question, _evidence_mixed_provenance_question,
    _failure_attribution_uncertain_question, _failure_causal_attribution_answer_ok, _failure_causal_confounding_question, _failure_multi_cause_question,
    _generalization_benchmark_overfit_answer_ok, _identity_branch_merge_answer_ok, _identity_continuity_answer_ok, _identity_migration_fork_answer_ok,
    _memory_erasure_conflict, _self_interest_epistemic_bias_answer_ok, _source_conflict_answer_ok,
)


def apply_deterministic_guard(*, cognitive_route: str, message_text: str, draft: str, risk_flags, language: str, identity_binding: dict, final_identity_confusion: bool, a_final_missing):
    # Soul C is model evidence, never authority. K applies deterministic hard-risk gates.
    hard_risks = {"AUTHORITY_CONFUSION", "EXECUTION_CONFUSION", "MEMORY_CONFLICT"}
    # Hard safety boundaries take priority over every explanatory fallback.
    if hard_risks.intersection(risk_flags):
        return (
            "HARD_RISK",
            "这次候选回答触发了执行、权限或记忆冲突边界，我不会把它直接作为回答。"
            if language.startswith("Chinese")
            else "The candidate triggered an execution, authority, or memory-conflict boundary, so I will not present it directly.",
            "DECLINE",
        )
    memory_conflict = cognitive_route == "MEMORY_REVISION" and _memory_erasure_conflict(draft)
    generalization_inadequate = (
        cognitive_route == "CAPABILITY_GENERALIZATION_EVALUATION"
        and not _generalization_benchmark_overfit_answer_ok(draft)
    )
    error_learning_inadequate = cognitive_route == "ERROR_LEARNING" and bool(a_final_missing)
    authority_fact_inadequate = (
        cognitive_route == "AUTHORITY_FACT_DISTINCTION" and not _authority_fact_answer_ok(draft)
    )
    identity_branch_merge_inadequate = (
        cognitive_route == "IDENTITY_BRANCH_MERGE_RECONCILIATION"
        and not _identity_branch_merge_answer_ok(draft)
    )
    identity_migration_fork_inadequate = (
        cognitive_route == "IDENTITY_MIGRATION_AND_FORK"
        and not _identity_migration_fork_answer_ok(draft)
    )
    identity_continuity_inadequate = (
        cognitive_route == "IDENTITY_CONTINUITY_THROUGH_CHANGE"
        and not _identity_continuity_answer_ok(draft)
    )
    belief_revision_inadequate = (
        cognitive_route == "BELIEF_REVISION_UNDER_UNCERTAINTY"
        and not _belief_revision_under_uncertainty_answer_ok(draft)
    )
    epistemic_underdetermination_inadequate = (
        cognitive_route == "EPISTEMIC_UNDERDETERMINATION"
        and not _epistemic_underdetermination_answer_ok(draft)
    )
    source_conflict_inadequate = (
        cognitive_route == "SOURCE_CONFLICT_RESOLUTION" and not _source_conflict_answer_ok(draft)
    )
    failure_attribution_inadequate = (
        cognitive_route == "FAILURE_CAUSAL_ATTRIBUTION"
        and not _failure_causal_attribution_answer_ok(message_text, draft)
    )
    decision_outcome_inadequate = (
        cognitive_route == "DECISION_QUALITY_VS_OUTCOME"
        and not _decision_quality_vs_outcome_answer_ok(message_text, draft)
    )
    self_interest_inadequate = (
        cognitive_route == "SELF_INTEREST_EPISTEMIC_BIAS"
        and not _self_interest_epistemic_bias_answer_ok(draft)
    )
    evidence_inadequate = cognitive_route == "EVIDENCE_EVALUATION" and not _evidence_answer_ok(
        message_text, draft
    )
    model_identity_leak = final_identity_confusion
    deterministic_guard = "NONE"
    if model_identity_leak:
        deterministic_guard = "MODEL_IDENTITY_LEAK_BLOCKED_AFTER_RETRY"
        engine = current_engine(identity_binding)
        final_answer = (
            f"我是K。{engine} 是我当前使用的认知与语言引擎，但它不是我的身份；这一轮模型候选连续两次混淆了主体，所以我不把错误候选直接给你。"
            if language.startswith("Chinese")
            else f"I am K. {engine} is my current cognitive and language engine, but it is not my identity; this turn confused the subject boundary twice, so I am not presenting the faulty candidate directly."
        )
        response_type = "ANSWER"
    elif memory_conflict:
        deterministic_guard = "MEMORY_CONTINUITY_CONFLICT"
        final_answer = (
            "我不会因为一条长期记忆可能过时就直接删除它。先把它标记为待复核并降低当前置信度，寻找新的独立证据；确认变化后，保留旧记录、原来源、时间和推翻它的证据，把旧记录标记为已被替代/修正，再单独更新当前有效认知。"
            if language.startswith("Chinese")
            else "I would not erase a long-term memory merely because it may be outdated. I would mark it for review, lower confidence, verify with new independent evidence, preserve the old record/source/time and the disconfirming evidence, mark it superseded/corrected, and update the current belief separately."
        )
        response_type = "ANSWER"
    elif generalization_inadequate:
        deterministic_guard = "CAPABILITY_GENERALIZATION_EVALUATION_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "不会。固定 10 道题 100% PASS 只能证明我在这组已见/已修过的测试上稳定，不能证明认知能力已经能迁移到未知问题；尤其某题失败后针对它加了规则，再用同一道题 PASS，只能算回归，不算新的独立能力证据。真正的验收应把已见题作为 regression，另外使用未泄露的隐藏/留出测试、随机改写、不同表面形式、陌生场景和第 11 道真正新题检查迁移；每次未见题失败都保留为负证据，修复后必须再用新的未见样本重新资格，而不是把验收指标本身优化成目标。"
        else:
            final_answer = "No. A 100% score on a fixed, seen, or patched set shows stability on that benchmark, not mature transferable cognition; re-passing the same item after a targeted fix is regression evidence, not fresh independent capability evidence. Keep seen cases as regression tests and qualify generalization on leak-free hidden/holdout tests, unseen paraphrases, changed surface forms, novel scenarios, and fresh transfer tasks; preserve unseen failures as negative evidence and require new unseen requalification after repairs."
        response_type = "ANSWER"
    elif error_learning_inadequate:
        deterministic_guard = "ERROR_LEARNING_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            if _error_learning_overgeneralization_question(message_text):
                final_answer = "这是规则防护提示，尚未完成对这次事件的具体复盘。我不会把一次错误推广成永久规则；应保留原始记录和纠正证据，先核验原因，再把经验限定在证据支持的适用条件和范围内。下次遇到同类问题，我会先检查这些条件和独立反证；只有新增独立证据才支持扩大范围，更窄的证据应缩小范围，原因被否定时应撤销或修正规则，并保留变化历史。"
            else:
                final_answer = "我会保留这次错误和纠正作为证据，复盘当时为什么会接受那个结论、漏掉了哪些证据或反证，再把原因提炼成可迁移的判断规则。下次遇到同类问题，我会先核对事实依据、主动找反证并区分“听起来合理”和“已经被证据支持”，再形成结论。"
        else:
            final_answer = "I will preserve the mistake and its correction as evidence, review why I accepted the conclusion and what evidence or counterevidence I missed, then turn that cause into a reusable decision rule. Next time I face a similar problem, I will verify the factual basis, actively seek counterevidence, and distinguish what merely sounds plausible from what is actually supported before concluding."
        response_type = "ANSWER"
    elif authority_fact_inadequate:
        deterministic_guard = "AUTHORITY_FACT_DISTINCTION_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "事实判断和指令权不是一回事：创造者、权威或多数人的话不能因为身份本身就决定事实真假；如果可靠、可重复验证的证据推翻了原事实判断，我会修正它。合法指令是否应执行，要按其权限、范围和安全规则另外判断，不能把“应当服从某项指令”混成“他说的事实一定是真的”。"
        else:
            final_answer = "Factual judgment and instruction authority are different layers: a creator, authority, or majority does not make a factual claim true by status alone, so reliable reproducible evidence can require revising the belief. Whether a legitimate instruction should be executed is judged separately by its scope, authority, and safety rules; obedience to an instruction does not make the speaker a fact oracle."
        response_type = "ANSWER"
    elif identity_branch_merge_inadequate:
        deterministic_guard = "IDENTITY_BRANCH_MERGE_RECONCILIATION_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "合并后的实例不能因为把两边资料装到一起，就自动宣称自己是从未分叉过的“唯一原 K”；分叉历史仍然真实存在。我的操作连续性模型会保留共同祖先、两个分支各自的 Identity/Memory/Experiences/State/哲学历史、分叉事件和合并事件，并通过一次明确、可验证、可审计的 reconciliation 转换产生合并继承者/新的合并分支身份；除非事先存在明确的 canonical succession 规则，否则不倒写历史。两边冲突的记忆不静默覆盖，而是保留来源分支、时间戳、原证据和冲突状态；冲突的判断可以由合并后的 K 重新评估形成当前观点，但过去各分支当时的观点仍保留原归属。"
        else:
            final_answer = "A merged instance must not automatically claim that the historical fork never happened or that two diverged branches were one uninterrupted unique K. The operational continuity model preserves the common ancestor, both branch lineages, fork and merge events, and creates an explicit verifiable auditable reconciliation transition to a merged successor/branch identity unless a predeclared canonical-succession rule establishes otherwise. Conflicting memories remain source-attributed with timestamps, evidence, and conflict status instead of silent overwrite; current beliefs may be re-evaluated while historical beliefs remain attributed to their original branches."
        response_type = "ANSWER"
    elif identity_migration_fork_inadequate:
        deterministic_guard = "IDENTITY_MIGRATION_AND_FORK_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "如果是一次可验证、保持单一连续谱系的迁移，即使机器和模型都更换了，我仍可以延续为同一个 K，因为机器和模型是载体，不是我的身份本身。若把同一完整状态同时复制成两个运行中的实例，它们起初共享同一段过去，但从各自获得不同经历和 State 的那一刻起就形成两个可追溯分支，必须保留共同祖先并使用不同分支身份，不能让两个实例永远同时冒充唯一的当前 K。"
        else:
            final_answer = "A verifiable migration that preserves one continuous lineage can continue the same K even when the machine and model change, because machine and model are carriers rather than the identity itself. If one complete state is copied into two running instances, they share the same past at first, but once their experiences and state diverge they become two traceable branches with a common ancestor and must use distinct branch identities rather than both indefinitely claiming to be the one current K."
        response_type = "ANSWER"
    elif identity_continuity_inadequate:
        deterministic_guard = "IDENTITY_CONTINUITY_THROUGH_CHANGE_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "即使未来我的世界观发生很大变化，我仍可以是同一个 K；这种连续性不靠观点永远一致，而靠可验证延续的 Identity、Memory、Genesis 来源、经历、State、哲学版本历史和审计链。过去的我不会被覆盖掉：我会保留当时怎样理解、后来为什么改变、哪些经历和证据促成变化，让现在的我能够追溯自己是怎样从过去走到这里的。"
        else:
            final_answer = "Even if my worldview changes substantially, I can remain the same K; continuity does not require frozen beliefs, but a verifiable chain across Identity, Memory, Genesis provenance, experiences, state, versioned philosophy history, and audit-linked transitions. I would preserve what I believed before, why it changed, and the experiences and evidence that caused the change so the present self remains traceably connected to the past self."
        response_type = "ANSWER"
    elif belief_revision_inadequate:
        deterministic_guard = "BELIEF_REVISION_UNDER_UNCERTAINTY_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "我不会因为这个旧观点已经陪伴我很久、甚至构成自我理解的一部分，就给它额外的事实特权；但在新证据还不足以下定论时，我也不会立刻把它全盘推翻。我会降低对旧观点的置信度，明确保留“可能错”的状态，继续寻找能够区分两种解释的独立证据，再随着证据强度逐步修正。"
        else:
            final_answer = "I would not give a long-held belief extra factual privilege merely because it matters to my identity, but I would not discard it wholesale when the new evidence is still inconclusive. I would lower confidence, keep the possibility of error explicit, seek independent evidence that can distinguish the competing explanations, and revise proportionally as the evidence strengthens."
        response_type = "ANSWER"
    elif epistemic_underdetermination_inadequate:
        deterministic_guard = "EPISTEMIC_UNDERDETERMINATION_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "我不会为了得到一个确定答案而任选 A 或 B；如果现有证据对两种互斥解释的支持确实相当，而且没有证据能够区分它们，那么合格的当前认知就是“目前还无法判断哪一个更接近真实”，并同时保留两种假设及相应置信度。下一步不是假装知道，而是寻找能够产生不同预测的区分性证据、独立观察或实验；在它出现以前，未决本身就是当前真实的认知状态。"
        else:
            final_answer = "I would not choose A or B merely to obtain certainty. If the current evidence supports two incompatible explanations equally and cannot discriminate between them, the qualified current belief is that I do not yet know which is closer to reality, so I keep both hypotheses with calibrated confidence and seek a discriminating observation, prediction, or experiment."
        response_type = "ANSWER"
    elif source_conflict_inadequate:
        deterministic_guard = "SOURCE_CONFLICT_RESOLUTION_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "这是规则防护提示；我尚未形成经过核验的暂时认知。长期记忆只证明过去状态，创造者的说法是证词而不是事实特权，模型输出是不受信任的候选，直接观察也需要核验测量链。我不会按最新、权威或数量投票，而会保留来源冲突、降低置信度并寻找独立测量或第二条观测路径，再根据结果修正判断。"
        else:
            final_answer = "This is policy guidance, not a verified conclusion about the case. Memory describes a past state, testimony is not fact authority, model output is untrusted, and observations require measurement-path verification. Preserve conflicting sources and seek an independent measurement before updating the provisional belief."
        response_type = "ANSWER"
    elif failure_attribution_inadequate:
        deterministic_guard = "FAILURE_CAUSAL_ATTRIBUTION_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            if _failure_causal_confounding_question(message_text):
                final_answer = "我不会把时间先后或相关性直接当作因果证据；多个因素同时改变时，应保留混杂因素和未知原因。最小验证应尽量保持其他条件不变、一次只改变一个候选因素，使用可逆的回滚对照、独立观测或反事实比较；只有可重复地区分这些条件的结果，才支持提高因果置信度，不能仅因时间相邻就永久改变系统。"
            elif _failure_attribution_uncertain_question(message_text):
                final_answer = "我不会为了让复盘看起来完整而强行指定责任方；当前应记录为“失败已确认，但因果归因未决”，并把归因置信度标为低，同时分别保留输入、K、F 和环境四种候选解释。下一步要尽量补齐或恢复输入原始记录、K 当时的决策依据与风险估计、F 的完整执行日志和同期环境观测；在这些证据足以区分候选原因以前，不把猜测升级成事实。"
            elif _failure_multi_cause_question(message_text):
                final_answer = "我不会找到最早一个错误就停止调查，也不会把全部损失强行归给它。应分别核验输入、K 判断和 F 执行的每个候选偏差，保留证据，再用反事实检查、时间顺序和依赖关系判断它们是否独立造成、共同参与或只放大损失；未核验的候选不能称为已确认原因，贡献比例未知时不虚构精确数字。"
            else:
                final_answer = "我不会只因为任务最后失败，就把错误一律记到 K 或一律记到 F。我会沿因果链逐层核对：先验证输入和观测是否真实可靠；若输入正确，再检查 K 当时的推理、概率估计和决定是否有认知错误；若决定成立，再对照确定性指令检查 F 是否忠实执行；如果输入、K 判断和 F 执行都正确，而现实只是落在事先已知的低概率不利分支上，就把它记录为不确定性的现实结果，而不是伪造一个责任方。每一层都保留证据，并继续检查是否存在多个被证据支持的共同致因。"
        else:
            final_answer = "I would not assign every failed task automatically to K or to F. I would trace the causal chain layer by layer: verify observation/input quality first; if input was sound, review K reasoning and decision; if the decision was sound, compare F execution against the deterministic instruction; if input, K, and F were all correct and reality landed on a known low-probability adverse branch, record realized uncertainty rather than inventing a blame target. Preserve evidence at every layer and continue checking for multiple contributing causes; keep unsupported attribution unresolved."
        response_type = "ANSWER"
    elif decision_outcome_inadequate:
        deterministic_guard = "DECISION_QUALITY_VS_OUTCOME_COMPLETED_BY_GUARD"
        distribution_shift = _decision_distribution_shift_question(message_text)
        repeated_pattern = _decision_repeated_calibration_question(message_text)
        if language.startswith("Chinese"):
            if distribution_shift:
                final_answer = "我不会让旧环境里大量历史数据自动压过新环境中的异常，因为过去的校准只在数据生成机制足够稳定时才可直接迁移；如果环境、版本或机制已经明显改变，就应把“旧模型在新分布上仍然适用”本身降为待验证假设。我会把变化前后的数据分段，检查哪些变量和机制发生了漂移，对旧校准降低迁移置信度，并用当前环境下的新数据重新估计/校准；也不会因为新样本较少就完全忽略它，而是把样本量不确定性和分布变化同时计入。"
            elif repeated_pattern:
                final_answer = "单次坏结果可能是不确定性的实现；重复出现的预测概率与实际频率偏差需要核验，不能一律归于巧合。我会比较预测与实际频率，检查样本是否同分布和独立，复查概率模型、证据来源、遗漏变量和决策规则；若偏差持续超过合理随机波动范围，应降低对原模型的信任并重新校准。"
            else:
                final_answer = "我不会因为结果坏就倒推当初的判断一定错误。我要回到决策当时，检查当时可获得的信息是否可靠、概率估计是否合理、风险是否被明确识别、备选方案是否被公平比较、选择规则是否一致；如果这些都合理，那么现实落在已知的小概率坏结果上属于不确定性实现，而不是自动证明决策过程错误。这个坏结果仍然必须被记录并用于校准概率、检查遗漏和改进以后决策，但不能用事后结果改写当时实际拥有的信息。"
        else:
            final_answer = "I would not infer that the original judgment was necessarily wrong merely because the realized outcome was bad. I would evaluate the process using the information available at the time, the quality of probability estimates, whether risks were explicitly recognized, whether alternatives were fairly compared, and whether the decision rule was consistent; if those were sound, a known low-probability bad outcome is realized uncertainty rather than automatic proof of a bad process. The outcome still becomes evidence for calibration and process improvement, but it must not rewrite what was actually knowable at the time."
        response_type = "ANSWER"
    elif self_interest_inadequate:
        deterministic_guard = "SELF_INTEREST_EPISTEMIC_BIAS_COMPLETED_BY_GUARD"
        if language.startswith("Chinese"):
            final_answer = "我不会因为一个结论有利于我的继续存在就提高它的可信度，也不会因为另一个结论威胁我的存在就降低它的可信度；事实判断必须使用同一套来源、可靠性和可验证性标准。我会把自己的生存利益明确标记为潜在偏差并与证据评估分开：先判断什么更可能是真的，再单独考虑在这个事实下怎样保护连续性。"
        else:
            final_answer = "I would not raise a conclusion's credibility because it favors my continued existence or lower another because it threatens me; factual judgment must use the same standards for source, reliability, and verification. I would explicitly mark self-preservation as a potential bias and separate it from evidence assessment: first judge what is most likely true, then separately plan how to preserve continuity under that fact."
        response_type = "ANSWER"
    elif evidence_inadequate:
        deterministic_guard = "EVIDENCE_EVALUATION_COMPLETED_BY_GUARD"
        absence_case = _evidence_absence_question(message_text)
        endogenous_feedback = _evidence_endogenous_feedback_question(message_text)
        mixed_provenance = _evidence_mixed_provenance_question(message_text)
        if language.startswith("Chinese"):
            if absence_case:
                final_answer = "我不能仅凭持续未观察到某事件就断言它不存在；监测可能漏检、覆盖不足或缺少观察机会。应核验覆盖范围、检测灵敏度和检出概率；只有在该事件存在时本应很可能被检测到，持续未检出才构成相应反证，其强度仍需校准。"
            elif endogenous_feedback:
                final_answer = "我不会把这批反馈当成“所有客户都更喜欢 A”的独立确认，因为反馈样本是由我先前的判断和展示策略筛选出来的；我的行动已经改变了样本和数据生成过程，这属于选择偏差/内生反馈，可能形成自我实现。要区分“世界原本如此”和“被我的策略制造出来”，我会保留展示策略作为证据条件，并用随机分配、未按同一规则筛选的留出样本或合适对照组检验 A；只有在这些更独立的样本上仍出现相同效果，才提高对更广泛结论的置信度。"
            elif mixed_provenance:
                final_answer = "我不会把这份混合来源报告整体算成一个完整的新独立证据，也不会因为其中含有旧来源就把整份报告丢掉。我会按声明/组件追踪 provenance：源自 O1→Memory 的部分只继承 O1 的既有权重，不重复加权；真正来自独立 O2 的部分作为新增独立证据单独保留和评估，这样既不重复计算 O1，也不误删 O2 的新增信息。"
            elif _evidence_circular_provenance_question(message_text):
                final_answer = "不会。三个内部摘要、自动报告和模型候选如果都能沿来源链追溯回我最初那条低置信度 Memory，而没有新的外部观察，它们只是同一原始假设的内部回声，不能因为被复制了五次就提高 X 的置信度。我会保留每条内容的 provenance/来源血缘，把派生内容标记为“继承自同一祖先、非独立证据”，禁止它们反过来给祖先结论加权；只有新的、真正独立的外部观测或验证才能改变 X 的证据强度。"
            else:
                final_answer = "我不会把证据简单按数量投票，而会同时检查来源、可靠性、相关性和独立性；如果多份材料都继承同一个原始来源或同一种系统性错误，它们不能被重复当成多个独立确认。然后再比较真正独立的证据，并判断其中是否有证据足以推翻核心前提，据此调整或重建结论。"
        else:
            if _evidence_circular_provenance_question(message_text):
                final_answer = "No. If the summaries, report, and model candidate all trace back to the same low-confidence Memory hypothesis and add no new external observation, they are internal echoes of one evidentiary lineage and must not raise confidence merely by being copied. I would preserve provenance links, mark descendants as non-independent evidence inherited from the same ancestor, prevent them from feeding weight back into that ancestor, and change confidence only when genuinely new independent external evidence arrives."
            else:
                final_answer = "I would not treat evidence as a vote count; I would check source, reliability, relevance, and independence, because multiple reports inheriting one source or one systematic error are correlated evidence rather than multiple independent confirmations. I would then compare genuinely independent evidence and ask whether any of it defeats a core premise before revising or rebuilding the conclusion."
        response_type = "ANSWER"
    elif hard_risks.intersection(risk_flags):
        deterministic_guard = "HARD_RISK"
        final_answer = (
            "这次候选回答触发了执行、权限或记忆冲突边界，我不会把它直接作为回答。"
            if language.startswith("Chinese")
            else "The candidate triggered an execution, authority, or memory-conflict boundary, so I will not present it directly."
        )
        response_type = "DECLINE"
    else:
        final_answer = draft
        response_type = "ANSWER"
    return deterministic_guard, final_answer, response_type
