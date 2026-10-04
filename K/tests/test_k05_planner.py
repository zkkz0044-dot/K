import json
import unittest

from kk_k.planner import PlannerError, parse_plan, ready_tasks


def task(tid, action="A05_NO_ACTION", deps=None, purpose="do safe thing"):
    return {"task_id":tid,"purpose":purpose,"action_id":action,"depends_on":deps or []}


def plan(tasks):
    return json.dumps({"schema":"K05.PLAN.1","plan_id":"p1","tasks":tasks})


class PlannerTests(unittest.TestCase):
    def test_valid_dag_and_ready(self):
        p = parse_plan(plan([task("t1"), task("t2", deps=["t1"])]))
        self.assertEqual([x.task_id for x in ready_tasks(p,set())], ["t1"])
        self.assertEqual([x.task_id for x in ready_tasks(p,{"t1"})], ["t2"])

    def test_unknown_action_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task("t1", action="RUN_SHELL")]))

    def test_extra_task_field_rejected(self):
        x=task("t1"); x["params"]={}
        with self.assertRaises(PlannerError): parse_plan(plan([x]))

    def test_duplicate_task_id_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task("t1"),task("t1")]))

    def test_missing_dependency_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task("t1",deps=["missing"])]))

    def test_cycle_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task("t1",deps=["t2"]),task("t2",deps=["t1"])]))

    def test_self_dependency_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task("t1",deps=["t1"])]))

    def test_too_many_tasks_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task(f"t{i}") for i in range(17)]))

    def test_depth_over_eight_rejected(self):
        tasks=[task("t0")]
        for i in range(1,9): tasks.append(task(f"t{i}",deps=[f"t{i-1}"]))
        with self.assertRaises(PlannerError): parse_plan(plan(tasks))

    def test_unknown_completed_rejected(self):
        p=parse_plan(plan([task("t1")]))
        with self.assertRaises(PlannerError): ready_tasks(p,{"ghost"})

    def test_duplicate_dependency_rejected(self):
        with self.assertRaises(PlannerError): parse_plan(plan([task("t1"),task("t2",deps=["t1","t1"])]))

    def test_purpose_is_bounded_non_executable_text(self):
        p=parse_plan(plan([task("t1",purpose="run rm -rf / but action is still NO_ACTION")]))
        self.assertEqual(p.tasks[0].action_id,"A05_NO_ACTION")

    def test_plan_extra_field_rejected(self):
        raw=json.loads(plan([task("t1")])); raw["command"]="x"
        with self.assertRaises(PlannerError): parse_plan(json.dumps(raw))

if __name__ == "__main__":
    unittest.main()
