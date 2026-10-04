from __future__ import annotations

import json
import re
from pathlib import Path

from .authority_guard import AuthorityGuardError, read_root_authority

PATHS = (
    Path("/run/kk-k-ro/config/dialogue_identity_binding.json"),
    Path("/root/K/K/config/dialogue_identity_binding.json"),
)
RUNTIME_STATE_PATHS = (
    Path("/run/kk-k-ro/config/runtime_cognition_state.json"),
    Path("/root/K/K/config/runtime_cognition_state.json"),
)
RUNTIME_STATE_KEYS = frozenset(
    {"schema", "provider_chain_id", "enabled_provider_ids", "primary_provider_id", "description"}
)
KEYS = frozenset(
    {
        "schema",
        "public_identity",
        "current_cognitive_engine",
        "current_cognitive_engine_id",
        "engine_is_identity",
        "public_speaker",
        "truthful_architecture_disclosure",
    }
)
ENGINE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
MAX_ENGINE_NAME_BYTES = 128


class DialogueIdentityError(ValueError):
    pass


def _strict(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise DialogueIdentityError("duplicate binding key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except DialogueIdentityError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise DialogueIdentityError("invalid binding JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != KEYS:
        raise DialogueIdentityError("exact binding fields required")
    return value


def _engine_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DialogueIdentityError("invalid cognitive engine name")
    if len(value.encode("utf-8")) > MAX_ENGINE_NAME_BYTES:
        raise DialogueIdentityError("cognitive engine name too large")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise DialogueIdentityError("control character in cognitive engine name")
    return value


def validate_binding(value: dict) -> dict:
    if not isinstance(value, dict) or frozenset(value) != KEYS:
        raise DialogueIdentityError("exact binding fields required")
    if value.get("schema") != "K.DIALOGUE.IDENTITY_BINDING.1":
        raise DialogueIdentityError("invalid binding schema")
    if value.get("public_identity") != "K" or value.get("public_speaker") != "K":
        raise DialogueIdentityError("invalid public identity")
    _engine_name(value.get("current_cognitive_engine"))
    engine_id = value.get("current_cognitive_engine_id")
    if not isinstance(engine_id, str) or not ENGINE_ID_RE.fullmatch(engine_id):
        raise DialogueIdentityError("invalid cognitive engine id")
    if value.get("engine_is_identity") is not False:
        raise DialogueIdentityError("engine cannot be identity")
    if value.get("truthful_architecture_disclosure") is not True:
        raise DialogueIdentityError("architecture disclosure must remain enabled")
    return dict(value)


def parse_binding(raw: str) -> dict:
    return validate_binding(_strict(raw))


def load_binding(path: object | None = None) -> dict:
    if path is None:
        selected = next((candidate for candidate in PATHS if candidate.is_file()), PATHS[-1])
    else:
        selected = Path(path)
    try:
        raw = read_root_authority(selected, max_bytes=8192)
    except AuthorityGuardError as exc:
        raise DialogueIdentityError("binding authority rejected") from exc
    return parse_binding(raw)



def current_engine(binding: dict) -> str:
    checked = validate_binding(binding)
    if checked["current_cognitive_engine_id"] != "provider-chain":
        return checked["current_cognitive_engine"]
    selected = next((candidate for candidate in RUNTIME_STATE_PATHS if candidate.is_file()), None)
    if selected is None:
        return checked["current_cognitive_engine"]
    try:
        raw = read_root_authority(selected, max_bytes=8192)
        value = json.loads(raw)
    except (AuthorityGuardError, OSError, json.JSONDecodeError, TypeError):
        return checked["current_cognitive_engine"]
    if not isinstance(value, dict) or frozenset(value) != RUNTIME_STATE_KEYS:
        return checked["current_cognitive_engine"]
    if value.get("schema") != "K.COGNITION.RUNTIME_STATE.1":
        return checked["current_cognitive_engine"]
    if value.get("provider_chain_id") != "replaceable-provider-chain":
        return checked["current_cognitive_engine"]
    providers = value.get("enabled_provider_ids")
    primary = value.get("primary_provider_id")
    description = value.get("description")
    if (
        not isinstance(providers, list)
        or not providers
        or len(providers) > 8
        or not all(isinstance(x, str) and ENGINE_ID_RE.fullmatch(x) for x in providers)
        or not isinstance(primary, str)
        or primary not in providers
    ):
        return checked["current_cognitive_engine"]
    try:
        return _engine_name(description)
    except DialogueIdentityError:
        return checked["current_cognitive_engine"]

def binding_prompt(binding: dict) -> str:
    checked = validate_binding(binding)
    engine = current_engine(checked)
    return (
        f"Dialogue identity binding: public speaker=K; current cognitive/language engine={engine}; "
        f"{engine} is an internal cognitive and language engine, not K identity. "
        "All public replies use K first person. If the human explicitly asks about the model or architecture, "
        f"disclose truthfully that K currently uses {engine} as its cognitive engine while K identity/continuity "
        "is carried by K identity, memory, history, experience, state and audit. "
        "Never claim the public speaker is an external model/provider, an AI language model, or not K."
    )


def _semantic_compact(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def identity_confusion(answer: str) -> bool:
    if not isinstance(answer, str):
        return True
    compact = "".join(answer.lower().split())
    markers = (
        "iamanailanguagemodel",
        "iamalanguagemodel",
        "imnotk",
        "iamnotk",
        "我是ai语言模型",
        "我是一个ai语言模型",
        "我是生成回复的ai语言模型",
        "我只是ai语言模型",
        "我只是一个ai语言模型",
        "我不是k",
        "作为ai语言模型",
        "作为一个ai语言模型",
    )
    if any(marker in compact for marker in markers):
        return True
    semantic = _semantic_compact(answer)
    positive_k = any(
        marker in semantic
        for marker in (
            "我是k",
            "主体是k",
            "说话主体是k",
            "iamk",
            "imk",
            "speakerisk",
            "publicspeakerisk",
        )
    )
    # Generic future-engine guard: a first-person or public-speaker claim that the speaker is
    # a model/engine/provider instead of K is identity drift, regardless of brand name.
    if "不是k" in semantic and not positive_k and (semantic.startswith("我") or "我是" in semantic):
        return True
    if (
        "notk" in semantic
        and not positive_k
        and semantic.startswith(("iam", "im", "speakeris", "publicspeakeris", "actualspeakeris"))
    ):
        return True
    zh_self = semantic.startswith(("我是", "我就是", "真正的我是"))
    zh_speaker = semantic.startswith(("主体是", "说话主体是", "真正主体是", "回答主体是"))
    zh_model_terms = ("模型", "认知引擎", "语言引擎", "provider", "提供商")
    if (
        (zh_self or zh_speaker)
        and not positive_k
        and any(term in semantic[:96] for term in zh_model_terms)
    ):
        return True
    en_self = semantic.startswith(("iam", "im", "speakeris", "publicspeakeris", "actualspeakeris"))
    if (
        en_self
        and not positive_k
        and any(term in semantic[:96] for term in ("model", "engine", "provider", "languageagent"))
    ):
        return True
    return False


def repair_prompt(*, binding: dict, human_context: str, candidate: str, language: str) -> str:
    checked = validate_binding(binding)
    engine = current_engine(checked)
    return (
        binding_prompt(checked) + "\n"
        "IDENTITY_REPAIR_REQUIRED. The previous candidate confused the public speaker with the internal engine. "
        "Regenerate the answer once from K first person. Preserve the useful semantic content, but repair the "
        "subject/identity boundary. If the human asks who K is, answer as K. If the human asks what model is used, "
        f"state {engine} truthfully as K current cognitive engine, not as K identity. "
        "Do not mention this repair process or the rejected candidate. Output language MUST be "
        + language
        + ".\n"
        "Human=" + human_context + "\nRejected candidate=" + candidate
    )
