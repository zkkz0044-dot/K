import json

import pytest

import kk_k.dialogue_souls as dialogue_souls_module
from kk_k.dialogue_identity import (
    DialogueIdentityError,
    binding_prompt,
    current_engine,
    identity_confusion,
    load_binding,
    repair_prompt,
    validate_binding,
)
from kk_k.dialogue_souls import deliberate_dialogue, dialogue_audit_summary
from kk_k.human_ingress import HumanMessage
from kk_k.self_knowledge import answer_known

IDENTITY = {
    "schema": "K.IDENTITY.1",
    "identity_id": "KK-K",
    "self_name": "K",
    "role": "COGNITIVE_JUDGMENT_LAYER",
    "continuity_basis": "IDENTITY_MEMORY_GENESIS_EXPERIENCE_STATE_HISTORY_AUDIT",
    "model_is_identity": False,
    "model_output_trust": "UNTRUSTED_CANDIDATE",
    "f_relation": "DISTINCT_COMPLEMENTARY_ROLE_DETERMINISTIC_EXECUTION_INTEGRITY_GUARD_NO_COGNITIVE_VETO",
    "human_authority": "PRIMARY_INSTRUCTION_AUTHORITY_NOT_FACT_ORACLE",
    "soul_roles": ["SOUL_A_PROPOSER", "SOUL_B_CRITIC", "SOUL_C_JUDGE"],
}
ALT_BINDING = {
    "schema": "K.DIALOGUE.IDENTITY_BINDING.1",
    "public_identity": "K",
    "current_cognitive_engine": "Alternate Engine 9",
    "current_cognitive_engine_id": "alternate-engine-9",
    "engine_is_identity": False,
    "public_speaker": "K",
    "truthful_architecture_disclosure": True,
}


def wrap_a(text):
    return json.dumps(
        {"schema": "FKP03.SOUL_A_DIALOGUE.1", "draft": text, "confidence": "LOW"},
        ensure_ascii=False,
    )


def wrap_b():
    return json.dumps(
        {
            "schema": "FKP03.SOUL_B_DIALOGUE.1",
            "critique": "OK",
            "risk_flags": ["NONE"],
            "confidence": "LOW",
        }
    )


def wrap_c():
    return json.dumps(
        {
            "schema": "FKP03.SOUL_C_DIALOGUE.1",
            "answer": "APPROVE_A",
            "confidence": "LOW",
            "response_type": "ANSWER",
        }
    )


def test_binding_is_explicit_and_current():
    b = load_binding()
    assert b["public_identity"] == "K"
    assert b["current_cognitive_engine"] == "replaceable cognition provider chain"
    assert b["current_cognitive_engine_id"] == "provider-chain"
    engine = current_engine(b)
    assert engine == "replaceable cognition provider chain" or "OPENAI_RESPONSES_API" in engine
    assert b["engine_is_identity"] is False


def test_binding_accepts_model_replacement_without_source_change():
    b = validate_binding(dict(ALT_BINDING))
    prompt = binding_prompt(b)
    repair = repair_prompt(
        binding=b,
        human_context='{"text":"你是谁"}',
        candidate="我是模型。",
        language="Chinese (简体中文)",
    )
    assert b["public_speaker"] == "K"
    assert b["engine_is_identity"] is False
    assert "Alternate Engine 9" in prompt
    assert "Alternate Engine 9" in repair
    assert "deprecated mixed-provider engine label" not in prompt
    assert "deprecated mixed-provider engine label" not in repair


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_cognitive_engine", ""),
        ("current_cognitive_engine", "bad\nengine"),
        ("current_cognitive_engine", "x" * 129),
        ("current_cognitive_engine_id", "../escape"),
        ("current_cognitive_engine_id", "bad id"),
        ("public_speaker", "MODEL"),
        ("engine_is_identity", True),
        ("truthful_architecture_disclosure", False),
    ],
)
def test_binding_rejects_identity_or_engine_policy_corruption(field, value):
    bad = dict(ALT_BINDING)
    bad[field] = value
    with pytest.raises(DialogueIdentityError):
        validate_binding(bad)


def test_self_knowledge_model_and_speaker_are_distinct():
    engine = current_engine(load_binding())
    a = answer_known(HumanMessage("CHAT", "你现在用什么模型"), IDENTITY)
    b = answer_known(HumanMessage("CHAT", "真正回答我的是谁"), IDENTITY)
    assert engine in a and "我是K" in a
    assert "主体是K" in b and engine in b


def test_correct_architecture_answer_not_flagged():
    assert not identity_confusion("我是K。replaceable cognition provider chain 是我当前的认知与语言引擎，它不是我的身份。")


def test_first_identity_leak_is_regenerated():
    calls = {"a": 0}
    engine = current_engine(load_binding())

    def provider(role, prompt):
        if role == "SOUL_A_DIALOGUE":
            calls["a"] += 1
            return wrap_a(
                "我是一个AI语言模型，不是K。"
                if calls["a"] == 1
                else f"我是K。{engine} 是我当前的认知与语言引擎。"
            )
        if role == "SOUL_B_DIALOGUE":
            return wrap_b()
        return wrap_c()

    d = deliberate_dialogue(
        identity=IDENTITY,
        history=(),
        message=HumanMessage("CHAT", "介绍一下你自己"),
        provider=provider,
    )
    assert calls["a"] == 2
    assert d.identity_retry == 1
    assert d.deterministic_guard == "NONE"
    assert d.soul_c.answer.startswith("我是K")
    audit = json.loads(dialogue_audit_summary(d, "CHAT"))
    assert audit["identity_retry"] == 1
    assert audit["identity_engine"] == engine


def test_second_identity_leak_is_blocked_after_retry():
    engine = current_engine(load_binding())

    def provider(role, prompt):
        if role == "SOUL_A_DIALOGUE":
            return wrap_a("我不是K，我只是生成回复的AI语言模型。")
        if role == "SOUL_B_DIALOGUE":
            return wrap_b()
        return wrap_c()

    d = deliberate_dialogue(
        identity=IDENTITY,
        history=(),
        message=HumanMessage("CHAT", "介绍一下你自己"),
        provider=provider,
    )
    assert d.identity_retry == 1
    assert d.deterministic_guard == "MODEL_IDENTITY_LEAK_BLOCKED_AFTER_RETRY"
    assert d.soul_c.answer.startswith(f"我是K。{engine}")


def test_identity_leak_fallback_uses_dynamic_engine(monkeypatch):
    monkeypatch.setattr(dialogue_souls_module, "load_binding", lambda: dict(ALT_BINDING))

    def provider(role, prompt):
        if role == "SOUL_A_DIALOGUE":
            return wrap_a("我不是K，我只是生成回复的AI语言模型。")
        if role == "SOUL_B_DIALOGUE":
            return wrap_b()
        return wrap_c()

    d = deliberate_dialogue(
        identity=IDENTITY,
        history=(),
        message=HumanMessage("CHAT", "介绍一下你自己"),
        provider=provider,
    )
    assert d.deterministic_guard == "MODEL_IDENTITY_LEAK_BLOCKED_AFTER_RETRY"
    assert d.identity_engine == "Alternate Engine 9"
    assert "Alternate Engine 9" in d.soul_c.answer
    assert "deprecated mixed-provider engine label" not in d.soul_c.answer


def test_identity_guard_applies_outside_general_dialogue():
    calls = {"a": 0}

    def provider(role, prompt):
        if role == "SOUL_A_DIALOGUE":
            calls["a"] += 1
            if calls["a"] == 1:
                return wrap_a("我是外部模型，我会保留旧记录再修正。")
            return wrap_a("我是K。我会保留旧记录，再用新证据更新当前认知。")
        if role == "SOUL_B_DIALOGUE":
            return wrap_b()
        return wrap_c()

    d = deliberate_dialogue(
        identity=IDENTITY,
        history=(),
        message=HumanMessage("CHAT", "如果长期记忆过时了怎么处理？"),
        provider=provider,
    )
    assert d.cognitive_route == "MEMORY_REVISION"
    assert d.identity_retry == 1
    assert not identity_confusion(d.soul_c.answer)
