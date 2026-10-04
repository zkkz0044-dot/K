from __future__ import annotations
import secrets, json
from typing import Callable
from .audit_witness import (
    AuditWitnessError,
    append_remote_event,
    query_conversation_history,
    query_conversation_recall,
)
from .dialogue_souls import DialogueError, deliberate_dialogue, dialogue_audit_summary
from .dialogue_identity import DialogueIdentityError
from .human_ingress import HumanMessage, MAX_TEXT_BYTES
from .identity import IdentityError, load_identity
from .constitution import ConstitutionError, load_constitution
from .goal_anchor import (
    GoalAnchorError,
    load_goal_anchor,
    assert_system_alignment,
    assert_runtime_scope_alignment,
)
from .action_registry import ALLOWED_ACTIONS
from .external_tools import load_external_catalog
from .model_client import ModelClientError, call as model_call
from .self_knowledge import answer_known
from .personality import PersonalityError, load_personality_snapshot, prompt_view
from .beliefs import BeliefError, current_beliefs, prompt_view as belief_prompt_view
from .skills import SkillError, current_skills, prompt_view as skill_prompt_view
from .world_entity_graph import WorldEntityGraphError, query_context as query_world_graph
from .capability_cognition import CapabilityCognitionError, capability_audit_summary
from .capability_planner import plan_capability, execute_plan, plan_audit_summary


class ChatRuntimeError(RuntimeError):
    pass


def _emit_progress(progress, code: str, state: str, detail: str = "") -> None:
    if not callable(progress):
        return
    try:
        progress(code, state, detail)
    except Exception:
        pass


def _browser_search_fallback(evidence: object) -> str | None:
    if not isinstance(evidence, dict):
        return None
    if evidence.get("schema") != "K.COGNITION.CAPABILITY_EVIDENCE.1":
        return None
    if evidence.get("tool") != "browser.search" or evidence.get("verdict") != "PASS":
        return None
    receipt = evidence.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("verified") is not True:
        return None
    fk = receipt.get("fk_tool_receipt")
    if not isinstance(fk, dict) or fk.get("schema") != "FK_TOOL.F_RECEIPT.1":
        return None
    if fk.get("tool") != "browser.search" or fk.get("outcome") != "EXECUTED":
        return None
    raw = fk.get("evidence")
    search = raw.get("search") if isinstance(raw, dict) and raw.get("kind") == "WEB_SEARCH" else None
    results = search.get("results") if isinstance(search, dict) else None
    if not isinstance(results, list):
        return None
    clean = []
    for item in results[:3]:
        if not isinstance(item, dict) or set(item) != {"title", "url", "snippet"}:
            return None
        title, url, snippet = item["title"], item["url"], item["snippet"]
        if not all(isinstance(x, str) for x in (title, url, snippet)):
            return None
        if not url.startswith(("http://", "https://")):
            return None
        clean.append((title.strip(), snippet.strip(), url.strip()))
    if not clean:
        return "搜索已经执行，但本轮没有找到可验证的搜索结果。"
    parts = ["本地认知模型暂时不可用；以下直接列出已通过 F 校验的搜索证据"]
    for index, (title, snippet, url) in enumerate(clean, 1):
        item = f"{index}. {title}"
        if snippet:
            item += f"：{snippet}"
        item += f"（{url}）"
        parts.append(item)
    return "；".join(parts)


SUBJECTS = {
    "CHAT": "human_chat",
    "ASK": "human_ask",
    "PLAN": "human_plan",
    "REMEMBER": "human_remember",
}
AUDIT_CHUNK_BYTES = 1800


def _verify_goal_alignment(identity: dict) -> None:
    # load_identity guarantees the full schema in production; lightweight unit doubles may omit it.
    if not isinstance(identity, dict) or identity.get("schema") != "K.IDENTITY.1":
        return
    anchor = load_goal_anchor()
    constitution = load_constitution("/root/K/K/K00_CONSTITUTION.json")
    assert_system_alignment(anchor, constitution, identity)
    catalog = load_external_catalog()
    enabled_tools = {name for name, spec in catalog.items() if spec.enabled}
    assert_runtime_scope_alignment(anchor, enabled_tools, ALLOWED_ACTIONS)


def _eid(prefix: str) -> str:
    return prefix + "-" + secrets.token_hex(8)


def _utf8_chunks(text: str, max_bytes: int = AUDIT_CHUNK_BYTES) -> list[str]:
    chunks = []
    current = []
    size = 0
    for ch in text:
        n = len(ch.encode("utf-8"))
        if current and size + n > max_bytes:
            chunks.append("".join(current))
            current = []
            size = 0
        current.append(ch)
        size += n
    if current:
        chunks.append("".join(current))
    return chunks


def _append_human(message: HumanMessage, address: str) -> int:
    chunks = _utf8_chunks(message.text)
    for part in chunks:
        append_remote_event(
            event_id=_eid("human"),
            kind="USER_NOTE",
            subject=SUBJECTS[message.mode],
            summary=part,
            address=address,
        )
    return len(chunks)


def _completed_history(events: tuple[dict, ...]) -> tuple[dict, ...]:
    """Keep durable audit history, but exclude trailing failed/unanswered human turns from cognition."""
    last_reply = -1
    for i, event in enumerate(events):
        if event.get("subject") == "k_reply":
            last_reply = i
    return events[: last_reply + 1] if last_reply >= 0 else ()


def run_turn(
    message: HumanMessage,
    *,
    model_provider=model_call,
    audit_address="\0kk-fk-audit-v2",
    identity_path="/root/K/K/K_IDENTITY.json",
    progress: Callable[[str, str, str], None] | None = None,
    media: tuple[dict, ...] | list[dict] = (),
    device_context: dict | None = None,
) -> str:
    if not isinstance(message, HumanMessage):
        raise ChatRuntimeError("validated HumanMessage required")
    try:
        # Read prior history first; current user input must be durably committed before cognition.
        _emit_progress(progress, "history", "START", "读取最近对话历史")
        history = _completed_history(query_conversation_history(limit=8, address=audit_address))
        _emit_progress(progress, "history", "DONE", f"已加载 {len(history)} 条已完成历史事件")
        _emit_progress(progress, "input_commit", "START", "把本轮输入写入不可变审计")
        parts = _append_human(message, audit_address)
        _emit_progress(progress, "input_commit", "DONE", f"输入已提交为 {parts} 个审计分段")
        clean_media = tuple(media or ())
        if clean_media:
            meta = []
            for item in clean_media:
                if not isinstance(item, dict):
                    raise ChatRuntimeError("invalid media envelope")
                meta.append(
                    {
                        "kind": item.get("kind", ""),
                        "name": item.get("name", ""),
                        "source": item.get("source", ""),
                    }
                )
            append_remote_event(
                event_id=_eid("attachment"),
                kind="USER_NOTE",
                subject="human_attachment",
                summary=json.dumps(meta, ensure_ascii=False, separators=(",", ":"))[:1800],
                address=audit_address,
            )
            _emit_progress(progress, "attachment", "DONE", f"已接收 {len(clean_media)} 个附件输入")
        clean_device = device_context if isinstance(device_context, dict) else None
        if clean_device:
            avail = [
                k
                for k in ("terminal", "location", "orientation", "motion", "stability")
                if clean_device.get(k) is not None
            ]
            append_remote_event(
                event_id=_eid("device"),
                kind="USER_NOTE",
                subject="human_device_observation",
                summary=json.dumps(
                    {
                        "schema": clean_device.get("schema"),
                        "captured_at_ms": clean_device.get("captured_at_ms"),
                        "device_id": (clean_device.get("terminal") or {}).get("device_id"),
                        "device_model": (clean_device.get("terminal") or {}).get("device_model"),
                        "available": avail,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                address=audit_address,
            )
            _emit_progress(progress, "device", "DONE", "已接收手机设备感知快照")
        _emit_progress(progress, "identity", "START", "加载 K 持续身份")
        identity = load_identity(identity_path)
        _emit_progress(progress, "identity", "DONE", "K 身份已加载")
        _emit_progress(progress, "goal_anchor", "START", "核对 K 初心与不可漂移目标")
        _verify_goal_alignment(identity)
        _emit_progress(progress, "goal_anchor", "DONE", "K 初心/身份/宪法一致")
        byte_len = len(message.text.encode("utf-8"))
        if byte_len > MAX_TEXT_BYTES:
            _emit_progress(progress, "route", "DONE", "LONG_PASTE_ACCEPTED")
            answer = f"我已完整接收并记录这段长文本（{byte_len} bytes，{parts}个审计分段）。你可以继续问我这段内容。"
            append_remote_event(
                event_id=_eid("paste"),
                kind="SYSTEM",
                subject="dialogue_gate",
                summary='{"route":"LONG_PASTE_ACCEPTED","mode":"' + message.mode + '"}',
                address=audit_address,
            )
            _emit_progress(progress, "reply_commit", "START", "写入 K 回复审计")
            append_remote_event(
                event_id=_eid("reply"),
                kind="SYSTEM",
                subject="k_reply",
                summary=answer,
                address=audit_address,
            )
            _emit_progress(progress, "reply_commit", "DONE", "K 回复已写入审计")
            _emit_progress(progress, "complete", "DONE", "本轮完成")
            return answer
        _emit_progress(progress, "self_knowledge", "START", "检查是否可由 K 自身知识直接回答")
        known = answer_known(message, identity)
        if known is not None:
            _emit_progress(progress, "self_knowledge", "DONE", "命中 SELF_KNOWLEDGE")
            append_remote_event(
                event_id=_eid("self"),
                kind="SYSTEM",
                subject="dialogue_gate",
                summary='{"route":"SELF_KNOWLEDGE","mode":"' + message.mode + '"}',
                address=audit_address,
            )
            _emit_progress(progress, "reply_commit", "START", "写入 K 回复审计")
            append_remote_event(
                event_id=_eid("reply"),
                kind="SYSTEM",
                subject="k_reply",
                summary=known,
                address=audit_address,
            )
            _emit_progress(progress, "reply_commit", "DONE", "K 回复已写入审计")
            _emit_progress(progress, "complete", "DONE", "本轮完成")
            return known
        _emit_progress(progress, "self_knowledge", "DONE", "未命中，进入一般认知链")
        _emit_progress(progress, "personality", "START", "加载 K 的版本化人格状态")
        personality_snapshot = load_personality_snapshot(address=audit_address)
        personality_context = prompt_view(personality_snapshot)
        _emit_progress(
            progress,
            "personality",
            "DONE",
            f'人格版本 {personality_snapshot.state["version"]} / revisions={personality_snapshot.revision_count}',
        )
        _emit_progress(progress, "beliefs", "START", "加载与当前话题相关的 K 当前信念")
        belief_items = current_beliefs(message.text, limit=6, address=audit_address)
        belief_context = belief_prompt_view(belief_items)
        _emit_progress(progress, "beliefs", "DONE", f"加载 {len(belief_items)} 条相关当前信念")
        _emit_progress(progress, "skills", "START", "加载与当前任务相关的 K 已验证技能状态")
        skill_items = current_skills(message.text, limit=6, address=audit_address)
        skill_context = skill_prompt_view(skill_items)
        _emit_progress(progress, "skills", "DONE", f"加载 {len(skill_items)} 条相关技能状态")
        _emit_progress(progress, "world_graph", "START", "加载 K 的长期世界观察关系图")
        try:
            world_graph_context = query_world_graph(message.text, limit=8)
            graph_count = len(world_graph_context.get("entities", ()))
            _emit_progress(
                progress, "world_graph", "DONE", f"加载 {graph_count} 个相关世界观察实体"
            )
        except (WorldEntityGraphError, OSError):
            world_graph_context = None
            _emit_progress(
                progress, "world_graph", "DONE", "世界观察图不可用，本轮不注入该派生证据"
            )
        _emit_progress(progress, "long_memory", "START", "从不可变历史中检索相关长期记忆")
        recalled = query_conversation_recall(message.text, limit=4, address=audit_address)
        recent_sequences = {event.get("sequence") for event in history}
        recalled = tuple(
            event for event in recalled if event.get("sequence") not in recent_sequences
        )
        _emit_progress(progress, "long_memory", "DONE", f"检索到 {len(recalled)} 条非重复历史事件")
        _emit_progress(progress, "capability_plan", "START", "K 判断本轮是否需要只读能力")
        plan = plan_capability(
            identity=identity,
            history=history,
            message=message,
            provider=model_provider,
            media=clean_media,
            device_context=clean_device,
            cognitive_context={
                "recalled_history": recalled,
                "personality": personality_context,
                "beliefs": belief_context,
                "skills": skill_context,
                "world_graph": world_graph_context,
            },
        )
        # A plan is neither an A/B/C verdict nor proof of execution.
        append_remote_event(
            event_id=_eid("capability-plan"),
            kind="SYSTEM",
            subject="capability_plan",
            summary=plan_audit_summary(plan),
            address=audit_address,
        )
        _emit_progress(
            progress,
            "capability_plan",
            "DONE",
            "K 已提出只读能力需求" if plan.need is not None else "K 判断本轮无需外部能力",
        )
        _emit_progress(progress, "capability", "START", "按已记录的能力需求交由 F 机械校验执行")
        cap = execute_plan(plan)
        _emit_progress(
            progress,
            "capability",
            "DONE",
            "存在能力证据" if cap is not None else "本轮无外部能力证据",
        )
        if cap is not None:
            append_remote_event(
                event_id=_eid("capability"),
                kind="SYSTEM",
                subject="capability_evidence",
                summary=capability_audit_summary(cap),
                address=audit_address,
            )
        _emit_progress(progress, "deliberation", "START", "进入 K 对话认知链")
        effective_provider = model_provider
        if clean_media and model_provider is model_call:
            media_hint = "\nThe human attached media to this turn. Inspect the attached image/file inputs directly when forming K's candidate answer. Do not claim an attachment was seen unless it is actually present in the multimodal request."

            def effective_provider(role: str, prompt: str) -> str:
                return model_call(
                    role,
                    prompt + media_hint if role == "SOUL_A_DIALOGUE" else prompt,
                    media=clean_media if role == "SOUL_A_DIALOGUE" else None,
                )

        decision = deliberate_dialogue(
            identity=identity,
            history=history,
            message=message,
            provider=effective_provider,
            recalled_history=recalled,
            personality_context=personality_context,
            belief_context=belief_context,
            skill_context=skill_context,
            world_graph_context=world_graph_context,
            capability_evidence=cap,
            device_context=clean_device,
            progress=progress,
        )
        _emit_progress(
            progress,
            "deliberation",
            "DONE",
            getattr(decision, "cognitive_route", "GENERAL_DIALOGUE"),
        )
        _emit_progress(progress, "decision_audit", "START", "记录本轮认知路由与裁决")
        append_remote_event(
            event_id=_eid("dialogue"),
            kind="SYSTEM",
            subject="dialogue_gate",
            summary=dialogue_audit_summary(decision, message.mode),
            address=audit_address,
        )
        _emit_progress(progress, "decision_audit", "DONE", "认知审计已提交")
        answer = decision.soul_c.answer
        _emit_progress(progress, "reply_commit", "START", "写入 K 回复审计")
        append_remote_event(
            event_id=_eid("reply"),
            kind="SYSTEM",
            subject="k_reply",
            summary=answer,
            address=audit_address,
        )
        _emit_progress(progress, "reply_commit", "DONE", "K 回复已写入审计")
        _emit_progress(progress, "complete", "DONE", "本轮完成")
        return answer
    except ModelClientError as exc:
        fallback = _browser_search_fallback(locals().get("cap"))
        if fallback is not None:
            try:
                append_remote_event(
                    event_id=_eid("dialogue-error"),
                    kind="SYSTEM",
                    subject="dialogue_error",
                    summary=type(exc).__name__,
                    address=audit_address,
                )
                append_remote_event(
                    event_id=_eid("dialogue-fallback"),
                    kind="SYSTEM",
                    subject="dialogue_fallback",
                    summary=json.dumps(
                        {"schema":"K.DIALOGUE.FALLBACK.1","reason":"MODEL_PROVIDER_UNAVAILABLE","source":"VERIFIED_BROWSER_SEARCH_EVIDENCE"},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    address=audit_address,
                )
                _emit_progress(progress, "deliberation", "DONE", "SEARCH_EVIDENCE_FALLBACK")
                _emit_progress(progress, "reply_commit", "START", "写入搜索证据兜底回复审计")
                append_remote_event(
                    event_id=_eid("reply"),
                    kind="SYSTEM",
                    subject="k_reply",
                    summary=fallback,
                    address=audit_address,
                )
                _emit_progress(progress, "reply_commit", "DONE", "搜索证据兜底回复已写入审计")
                _emit_progress(progress, "complete", "DONE", "本轮完成（搜索证据兜底）")
                return fallback
            except Exception:
                pass
        try:
            append_remote_event(
                event_id=_eid("dialogue-error"),
                kind="SYSTEM",
                subject="dialogue_error",
                summary=type(exc).__name__,
                address=audit_address,
            )
        except Exception:
            pass
        raise ChatRuntimeError("K dialogue turn failed closed") from exc
    except (
        AuditWitnessError,
        DialogueError,
        DialogueIdentityError,
        IdentityError,
        ConstitutionError,
        GoalAnchorError,
        PersonalityError,
        BeliefError,
        SkillError,
        CapabilityCognitionError,
    ) as exc:
        try:
            append_remote_event(
                event_id=_eid("dialogue-error"),
                kind="SYSTEM",
                subject="dialogue_error",
                summary=type(exc).__name__,
                address=audit_address,
            )
        except Exception:
            pass
        raise ChatRuntimeError("K dialogue turn failed closed") from exc
