import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_k_dialogue_binding_is_provider_decoupled_and_runtime_state_is_openai_only():
    binding = json.loads((ROOT / "K/config/dialogue_identity_binding.json").read_text())
    runtime = json.loads((ROOT / "K/config/runtime_cognition_state.json").read_text())
    providers = json.loads((ROOT / "FK/model_runtime/cognition-providers.json").read_text())

    assert binding["schema"] == "K.DIALOGUE.IDENTITY_BINDING.1"
    assert binding["public_identity"] == "K"
    assert binding["engine_is_identity"] is False
    assert binding["current_cognitive_engine"] == "replaceable cognition provider chain"
    assert binding["current_cognitive_engine_id"] == "provider-chain"

    assert runtime["schema"] == "K.COGNITION.RUNTIME_STATE.1"
    assert runtime["provider_chain_id"] == "replaceable-provider-chain"
    assert runtime["enabled_provider_ids"] == ["OPENAI_RESPONSES_API"]
    assert runtime["primary_provider_id"] == "OPENAI_RESPONSES_API"

    enabled_default = [
        providers["providers"][name]["provider_id"]
        for name in providers["routes"]["default"]
        if providers["providers"][name]["enabled"]
    ]
    assert enabled_default == ["OPENAI_RESPONSES_API"]
    assert runtime["enabled_provider_ids"] == enabled_default
