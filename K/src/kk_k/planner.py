from __future__ import annotations

import json
from dataclasses import dataclass
import re

from .action_registry import ALLOWED_ACTIONS

PLAN_KEYS = frozenset({"schema", "plan_id", "tasks"})
TASK_KEYS = frozenset({"task_id", "purpose", "action_id", "depends_on"})
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_TASKS = 16
MAX_DEPTH = 8
MAX_PLAN_BYTES = 16384


class PlannerError(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    task_id: str
    purpose: str
    action_id: str
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    plan_id: str
    tasks: tuple[Task, ...]


def _strict_json(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise PlannerError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except PlannerError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise PlannerError("invalid plan JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != PLAN_KEYS:
        raise PlannerError("exact plan fields required")
    return value


def parse_plan(raw: object) -> Plan:
    if not isinstance(raw, str):
        raise PlannerError("plan must be text")
    if len(raw.encode("utf-8")) > MAX_PLAN_BYTES:
        raise PlannerError("plan too large")
    v = _strict_json(raw)
    if v["schema"] != "K05.PLAN.1":
        raise PlannerError("unsupported plan schema")
    if not isinstance(v["plan_id"], str) or not ID_RE.fullmatch(v["plan_id"]):
        raise PlannerError("invalid plan_id")
    raw_tasks = v["tasks"]
    if not isinstance(raw_tasks, list) or not (1 <= len(raw_tasks) <= MAX_TASKS):
        raise PlannerError("invalid task count")
    tasks = []
    seen = set()
    for item in raw_tasks:
        if not isinstance(item, dict) or frozenset(item) != TASK_KEYS:
            raise PlannerError("exact task fields required")
        tid = item["task_id"]
        if not isinstance(tid, str) or not ID_RE.fullmatch(tid) or tid in seen:
            raise PlannerError("invalid or duplicate task_id")
        seen.add(tid)
        purpose = item["purpose"]
        if not isinstance(purpose, str) or not (1 <= len(purpose.encode("utf-8")) <= 512):
            raise PlannerError("invalid purpose")
        action_id = item["action_id"]
        if not isinstance(action_id, str) or action_id not in ALLOWED_ACTIONS:
            raise PlannerError("unknown action_id")
        deps = item["depends_on"]
        if (
            not isinstance(deps, list)
            or len(deps) > MAX_TASKS
            or any(not isinstance(x, str) for x in deps)
            or len(set(deps)) != len(deps)
        ):
            raise PlannerError("invalid dependencies")
        tasks.append(Task(tid, purpose, action_id, tuple(deps)))
    _validate_graph(tasks)
    return Plan(v["plan_id"], tuple(tasks))


def _validate_graph(tasks: list[Task]) -> None:
    ids = {t.task_id for t in tasks}
    deps = {t.task_id: t.depends_on for t in tasks}
    for task in tasks:
        if task.task_id in task.depends_on:
            raise PlannerError("self dependency")
        if any(dep not in ids for dep in task.depends_on):
            raise PlannerError("missing dependency")
    visiting = set()
    depth_cache = {}

    def depth_of(tid: str) -> int:
        if tid in depth_cache:
            return depth_cache[tid]
        if tid in visiting:
            raise PlannerError("dependency cycle")
        visiting.add(tid)
        depth = 1 if not deps[tid] else 1 + max(depth_of(dep) for dep in deps[tid])
        visiting.remove(tid)
        if depth > MAX_DEPTH:
            raise PlannerError("plan dependency depth exceeded")
        depth_cache[tid] = depth
        return depth

    for tid in ids:
        depth_of(tid)


def ready_tasks(plan: Plan, completed_ids: set[str]) -> tuple[Task, ...]:
    if not isinstance(completed_ids, set) or any(not isinstance(x, str) for x in completed_ids):
        raise PlannerError("invalid completed task set")
    known = {t.task_id for t in plan.tasks}
    if not completed_ids <= known:
        raise PlannerError("unknown completed task")
    return tuple(
        t
        for t in plan.tasks
        if t.task_id not in completed_ids and set(t.depends_on) <= completed_ids
    )
