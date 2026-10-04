from model_runtime.role_policy import instructions_for_role, max_output_tokens

def test_dialogue_judge_policy_is_exact_token_contract():
    assert "APPROVE_A or REJECT_A" in instructions_for_role("SOUL_C_DIALOGUE")
    assert max_output_tokens("SOUL_C_DIALOGUE")==160

def test_world_think_policy_is_bounded_json_contract():
    assert "K.WORLD.THINK.1" in instructions_for_role("WORLD_THINK")
    assert max_output_tokens("WORLD_THINK")==1024

def test_capability_plan_policy_stays_read_only():
    text=instructions_for_role("K_CAPABILITY_PLAN")
    assert "READ_ONLY" in text and "Do not execute tools" in text
    assert max_output_tokens("K_CAPABILITY_PLAN")==384
