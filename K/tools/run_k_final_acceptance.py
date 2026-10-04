from __future__ import annotations

import json
from pathlib import Path
import tempfile

from kk_k.test_support import project_tempdir
from kk_k.constitution import load_constitution
from kk_k.critic import evaluate
from kk_k.governance import govern, load_policy
from kk_k.kernel import run_once
from kk_k.loop import run_bounded_loop
from kk_k.memory import append_event, verify_event_log, write_goal_atomic
from kk_k.model_interface import call_model_once
from kk_k.planner import parse_plan, ready_tasks
from kk_k.world_state import build_snapshot, lookup

ROOT = Path('/root/K/K')
checks = []

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

constitution = load_constitution(str(ROOT/'K00_CONSTITUTION.json'))
check('K00 constitution', constitution['k_f_boundary'] == 'K_FINAL_DECISION_F_EXECUTION_GUARD')

with project_tempdir() as td:
    td = Path(td)
    goal_path = td/'goal.json'
    events_path = td/'events.jsonl'
    world_path = td/'world.json'
    dlog = td/'decision.jsonl'
    elog = td/'execution.jsonl'
    goal = {'schema':'K02.GOAL.1','goal_id':'acceptance','text':'perform standalone K acceptance','status':'ACTIVE'}
    write_goal_atomic(str(goal_path), goal)
    append_event(str(events_path),event_id='e1',kind='SYSTEM',subject='acceptance',summary='started')
    check('K02 memory', len(verify_event_log(str(events_path))) == 1)

    fact = {'schema':'K03.FACT.1','key':'f.status','value':'ACCEPTED','source_id':'MOCK_F','observed_at':100,'ttl_seconds':60}
    snapshot = build_snapshot([fact], 120)
    world_path.write_text(json.dumps(snapshot),encoding='utf-8')
    check('K03 world state', lookup(snapshot,'f.status')['state'] == 'KNOWN')

    model_raw = json.dumps({'schema':'K04.DELIBERATION.1','assessment':'No external action needed','confidence':'HIGH','candidate_actions':['A05_NO_ACTION']})
    deliberation = call_model_once(lambda _prompt:model_raw, 'standalone acceptance')
    check('K04 model interface', deliberation.candidate_actions == ('A05_NO_ACTION',))

    plan_raw = json.dumps({'schema':'K05.PLAN.1','plan_id':'acceptance','tasks':[{'task_id':'t1','purpose':'stop safely','action_id':'A05_NO_ACTION','depends_on':[]}]})
    plan = parse_plan(plan_raw)
    check('K05 planner', ready_tasks(plan,set())[0].action_id == 'A05_NO_ACTION')

    policy = load_policy(str(ROOT/'K06_POLICY.json'))
    gov = govern('A05_NO_ACTION',policy,[])
    check('K06 governance', gov.outcome == 'ALLOW')
    decision_raw = json.dumps({'schema':'K01.DECISION.1','action_id':'A05_NO_ACTION'})
    no_action_receipt = {
        'schema':'K01.F_RECEIPT.1',
        'action_id':'A05_NO_ACTION',
        'outcome':'EXECUTED',
        'evidence':{'kind':'NO_ACTION','process_started':False},
    }
    k01 = run_once(
        constitution_path=str(ROOT/'K00_CONSTITUTION.json'),
        goal_path=str(goal_path),
        world_state_path=str(world_path),
        decision_log_path=str(dlog),
        execution_log_path=str(elog),
        llm_call=lambda _prompt: decision_raw,
        f_submit=lambda action_id: dict(no_action_receipt),
    )
    check('K01 kernel', k01['status'] == 'PASS' and k01['action_id'] == 'A05_NO_ACTION')

    critic = evaluate('A05_NO_ACTION',no_action_receipt,'mechanical no-op')
    check('K07 critic', critic['mechanical_verdict'] == 'PASS')

    loop = run_bounded_loop(
        policy=policy,
        proposer=lambda _cycle:'A05_NO_ACTION',
        executor=lambda action_id:{'action_id':action_id,'mechanical_verdict':'PASS'},
        log_path=str(td/'loop.jsonl'),
        max_cycles=8,
    )
    check('K08 loop', loop['status'] == 'NO_ACTION' and loop['executor_calls'] == 1)

    append_event(str(events_path),event_id='e2',kind='SYSTEM',subject='acceptance',summary='completed')
    check('K02 final chain', len(verify_event_log(str(events_path))) == 2)

for name in checks:
    print('PASS', name)
print('K_FINAL_ACCEPTANCE=PASS')
print('checks=', len(checks))
