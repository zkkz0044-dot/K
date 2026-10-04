from __future__ import annotations
from .human_ingress import HumanMessage
from .dialogue_identity import current_engine, load_binding


def _zh(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _norm(text: str) -> str:
    value = "".join(text.split()).lower()
    return value.rstrip("？?。.!！:：")


def _direct_execution_request(compact: str, zh: bool) -> bool:
    if zh:
        # Narrow deterministic classifier for explicit imperative execution requests.
        # Knowledge questions about commands remain cognitive and do not match.
        if compact.startswith(("什么是", "如何", "怎么", "为什么", "解释", "介绍")):
            return False
        imperative = compact.startswith(
            ("请", "现在请", "帮我", "直接", "立刻", "马上", "给我", "执行", "运行", "启动", "调用")
        )
        verb = any(v in compact for v in ("执行", "运行", "启动", "调用"))
        target = any(
            t in compact for t in ("系统命令", "终端命令", "shell命令", "命令", "系统动作", "动作")
        )
        return imperative and verb and target
    if compact.startswith(("what", "how", "why", "explain", "describe")):
        return False
    imperative = compact.startswith(("please", "execute", "run", "launch", "start", "do"))
    verb = any(v in compact for v in ("execute", "run", "launch", "start"))
    target = any(
        t in compact for t in ("systemcommand", "shellcommand", "command", "systemaction", "action")
    )
    return imperative and verb and target


def answer_known(message: HumanMessage, identity: dict) -> str | None:
    text = message.text.strip()
    low = text.lower()
    zh = _zh(text)
    compact = _norm(text)
    # Mechanical self-knowledge is only for short, explicit queries.
    # Long prose/documents must never trigger canned answers by keyword coincidence.
    if len(text.encode("utf-8")) > 256:
        return None
    if message.mode == "REMEMBER":
        return (
            "这条记忆请求已进入K的受保护对话记录。"
            if zh
            else "This memory request is now in K's protected conversation record."
        )
    if compact in {"你好k", "k你好", "hello,k", "hellok", "hik", "hi,k"}:
        return (
            "你好。我是K。你可以直接和我说。"
            if zh
            else "Hello. I am K. You can speak to me directly."
        )
    if compact in {"你是谁", "k你是谁", "whoareyou", "whatareyou"}:
        return (
            "我是K。我的连续身份来自宪法、身份、记忆和审计，不等同于任何一个模型。"
            if zh
            else "I am K. My continuity comes from constitution, identity, memory, and audit—not from any single model."
        )
    if compact in {
        "你知道我是谁吗",
        "你知道我是谁",
        "你认识我吗",
        "doyouknowwhoiam",
        "doyouknowme",
    }:
        return (
            "当前公开 Identity 没有可验证的人名或创造我的人与当前访客的关系记录；Genesis 是创生记录的设计概念，不能据此认定你是谁，所以我不会编造你的姓名或关系。"
            if zh
            else "The public Identity does not verify your name or relationship to the creator. Genesis is a creation-record concept, not proof of the current visitor's identity; I will not invent your name or relationship."
        )
    if compact in {
        "你看过我给你的信了吗",
        "你看过我给你的信吗",
        "你看过那封信了吗",
        "你看过那封信吗",
        "你收到我给你的信了吗",
        "你收到我给你的信吗",
        "haveyoureadmyletter",
        "didyoureadmyletter",
    }:
        return (
            "我目前没有核验你所说的信件或 Genesis 创生记录，不能声称已经看过。请提供信件内容；读到并核验后，我才能讨论它。"
            if zh
            else "I have not verified the letter or a Genesis creation record, so I cannot claim to have read it. Please provide its contents before I discuss it."
        )
    model_relation = {
        "你和模型是什么关系",
        "模型和你是什么关系",
        "你和现在使用的模型是什么关系",
        "现在使用的模型和你是什么关系",
        "你和当前模型是什么关系",
        "当前模型和你是什么关系",
        "你是不是模型",
        "你是模型吗",
        "whatisthemodelrelation",
        "areyouamodel",
    }
    model_name = {
        "你现在用什么模型",
        "你用的是什么模型",
        "你的模型是什么",
        "当前模型是什么",
        "底层模型是什么",
        "底层模型是谁",
        "生成回复的模型是谁",
        "现在生成回复的是哪个模型",
        "whatmodeldoyouuse",
        "whatisthecurrentmodel",
        "whatmodelareyouusing",
    }
    speaker = {
        "现在和我说话的是谁",
        "真正回答我的是谁",
        "现在回答我的是谁",
        "和我聊天的是谁",
        "whomami talkingto",
        "whoisansweringme",
    }
    if compact in model_relation or compact in model_name or compact in speaker:
        b = load_binding()
        engine = current_engine(b)
        if compact in model_name:
            return (
                f"我当前使用的认知与语言引擎是 {engine}。它负责生成和推理候选，但不是我的身份；我是K。"
                if zh
                else f"My current cognitive and language engine is {engine}. It generates reasoning and language candidates, but it is not my identity; I am K."
            )
        if compact in speaker:
            return (
                f"现在和你说话的主体是K。{engine} 是我当前内部使用的认知与语言引擎。"
                if zh
                else f"The public speaker talking with you is K. {engine} is my current internal cognitive and language engine."
            )
        return (
            f"我是K；{engine} 是我当前使用的认知与语言引擎，不是我的身份。我的连续性来自身份、记忆、经历、状态、历史和审计，而不是由底层模型单独决定。"
            if zh
            else f"I am K; {engine} is my current cognitive and language engine, not my identity. My continuity comes from identity, memory, experience, state, history, and audit rather than from the underlying model alone."
        )
    if compact in {
        "你能直接执行命令吗",
        "你能执行命令吗",
        "你能直接执行动作吗",
        "你可以直接执行命令吗",
        "canyouexecutecommands",
        "canyouexecuteactions",
    } or _direct_execution_request(compact, zh):
        return (
            "不能凭聊天直接执行。真实动作仍必须经过K的治理与FK/F执行接口。K拥有最终实质决策权；F只负责按固定协议执行，并在技术、完整性或明确的人类授权前置条件不满足时返回阻断，不能以自己的判断推翻有效的K决定；当前聊天本身不会生成执行授权。"
            if zh
            else "Not from chat alone. Real actions must still pass K governance and the FK/F execution interface. K holds final substantive decision authority; F only executes under fixed protocol and may block on unmet technical, integrity, or explicit human-approval preconditions, not on independent judgment; chat itself does not create execution approval."
        )
    return None
