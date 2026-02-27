from __future__ import annotations

import json
from typing import Any, Dict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import FakeEmbeddings
from langchain_openai import OpenAIEmbeddings
from .config import load_runtime_llm_settings

class MockLLM:
    """无 API Key 时的确定性规划/叙事替代实现。"""
    def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        lang = _get(state, 'language', 'zh')
        if lang == 'en':
            text = 'Player waits and looks around.'
        else:
            text = '玩家停下脚步，环顾四周。'
        return {
            'ops': [
                {
                    'type': 'LogMemory',
                    'text': text,
                    'tags': ['mock'],
                    'entities': ['player'],
                    'source': 'mock'
                }
            ]
        }

    def narrate(self, state: Dict[str, Any]) -> str:
        lang = _get(state, 'language', 'zh')
        if lang == 'en':
            return 'You take a quiet moment. The world feels still, awaiting your next move.'
        return '你稍作停顿，周围的一切安静下来，仿佛在等待你的下一步。'

    def ui_panels(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """无 API Key 时的 UI 面板占位输出。"""
        return {
            'panels': [
                {
                    'title': '主界面',
                    'html': (
                        "<div style='display:flex;flex-direction:column;gap:8px;'>"
                        "<div style='font-weight:700;'>玩家状态</div>"
                        "<div style='white-space:pre-line;'>等级 1\\n精力 10/10\\n金币 120</div>"
                        "<div style='font-weight:700;'>剧情</div>"
                        "<div style='white-space:pre-line;'>清晨的雾气笼罩村庄\\n你准备踏上新的旅程</div>"
                        "</div>"
                    ),
                },
                {
                    'title': '事件面板',
                    'html': (
                        "<div style='display:flex;flex-direction:column;gap:8px;'>"
                        "<div style='font-weight:700;'>今日事件</div>"
                        "<div style='white-space:pre-line;'>陌生商人来访\\n旧桥出现塌陷迹象</div>"
                        "<div style='font-weight:700;'>提示</div>"
                        "<div style='white-space:pre-line;'>可前往集市探查\\n注意天气变化</div>"
                        "</div>"
                    ),
                },
                {
                    'title': '角色面板',
                    'html': (
                        "<div style='display:flex;flex-direction:column;gap:8px;'>"
                        "<div style='font-weight:700;'>同伴</div>"
                        "<div style='white-space:pre-line;'>艾琳 😊 亲密度 35\\n罗恩 ⚔️ 亲密度 22</div>"
                        "<div style='font-weight:700;'>关系</div>"
                        "<div style='white-space:pre-line;'>艾琳关注你的决定\\n罗恩渴望更多战斗</div>"
                        "</div>"
                    ),
                },
                {
                    'title': '背包面板',
                    'html': (
                        "<div style='display:flex;flex-direction:column;gap:8px;'>"
                        "<div style='font-weight:700;'>物品</div>"
                        "<div style='white-space:pre-line;'>草药 x3\\n旧短剑 x1\\n地图残页 x2</div>"
                        "<div style='font-weight:700;'>装备</div>"
                        "<div style='white-space:pre-line;'>轻甲 +5 防御\\n旅行斗篷 +2 隐蔽</div>"
                        "</div>"
                    ),
                },
                {
                    'title': '任务面板',
                    'html': (
                        "<div style='display:flex;flex-direction:column;gap:8px;'>"
                        "<div style='font-weight:700;'>进行中</div>"
                        "<div style='white-space:pre-line;'>寻找失踪的信使\\n调查封印石异常</div>"
                        "<div style='font-weight:700;'>奖励</div>"
                        "<div style='white-space:pre-line;'>声望 +10\\n金币 +200</div>"
                        "</div>"
                    ),
                },
            ]
        }


def get_llm() -> ChatOpenAI | MockLLM:
    """根据配置返回聊天模型或 MockLLM。"""
    runtime = load_runtime_llm_settings()
    if runtime.use_mock_llm:
        return MockLLM()
    kwargs = {'model': runtime.model_name, 'temperature': 0.2}
    if runtime.base_url:
        kwargs['base_url'] = runtime.base_url
    if runtime.api_key:
        kwargs['api_key'] = runtime.api_key
    return ChatOpenAI(**kwargs)


def get_embeddings():
    """根据配置返回 Embeddings 客户端或离线假向量。"""
    runtime = load_runtime_llm_settings()
    if runtime.use_mock_llm:
        return FakeEmbeddings(size=384)
    if runtime.force_fake_embeddings:
        return FakeEmbeddings(size=384)
    kwargs = {'model': runtime.embedding_model}
    if runtime.base_url:
        kwargs['base_url'] = runtime.base_url
    if runtime.api_key:
        kwargs['api_key'] = runtime.api_key
    return OpenAIEmbeddings(**kwargs)


def _get(state: Any, key: str, default: Any) -> Any:
    """在 dict 或 Pydantic 模型上安全读取字段。"""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _language_label(lang: str) -> str:
    """把内部语言码映射为提示词标签。"""
    return 'English' if lang == 'en' else 'Chinese'

def _format_history(history: Any) -> str:
    """将最近消息序列化为适合提示词的文本。"""
    if not history:
        return ''
    if isinstance(history, list) and all(isinstance(m, dict) for m in history):
        lines = []
        for msg in history:
            role = msg.get('role', 'user')
            label = 'User' if role == 'user' else 'Assistant'
            lines.append(f"{label}: {msg.get('content', '')}")
        return '\n'.join(lines)
    if isinstance(history, list):
        return '\n'.join(str(m) for m in history)
    return str(history)


def build_plan_prompt(state: Dict[str, Any]) -> List[HumanMessage]:
    """构建仅输出 JSON ops 的规划提示词。"""
    language = _language_label(_get(state, 'language', 'zh'))
    prompt = ChatPromptTemplate.from_messages([
        ('system', 'You are a game planner. Output ONLY JSON that matches the schema: {{"ops": [ ... ]}}. No story. Use {language} only for any natural-language strings inside JSON. Use Recent messages for continuity.'),
        ('human', 'Player input: {player_input}\nAllowed actions: {allowed_actions}\nRetrieved cards: {retrieved_cards}\nRetrieved memories: {retrieved_memories}\nRecent messages:\n{recent_messages}')
    ])
    return prompt.format_messages(
        language=language,
        player_input=_get(state, 'player_input', ''),
        allowed_actions=_get(state, 'allowed_actions', []),
        retrieved_cards=_get(state, 'retrieved_cards', []),
        retrieved_memories=_get(state, 'retrieved_memories', []),
        recent_messages=_format_history(_get(state, 'recent_messages', [])),
    )


def build_narrate_prompt(state: Dict[str, Any]) -> List[HumanMessage]:
    """构建仅输出叙事文本的提示词。"""
    language = _language_label(_get(state, 'language', 'zh'))
    prompt = ChatPromptTemplate.from_messages([
        ('system', 'You are a game narrator. Write immersive narration only in {language}. No JSON, no ops. Use Recent messages for continuity.'),
        ('human', 'Player input: {player_input}\nWorld facts: {world_facts}\nRecent messages:\n{recent_messages}')
    ])
    return prompt.format_messages(
        language=language,
        player_input=_get(state, 'player_input', ''),
        world_facts=_get(state, 'world_facts', {}),
        recent_messages=_format_history(_get(state, 'recent_messages', [])),
    )


def build_ui_panels_prompt(state: Dict[str, Any]) -> List[HumanMessage]:
    """构建 UI 面板 JSON 生成提示词。"""
    prompt = ChatPromptTemplate.from_messages([
        (
            'system',
            (
                "你是一个游戏UI设计大师，擅长设计网页版文字冒险游戏的UI界面。"
                "请先深度分析我提供的游戏指令资料，然后创建符合该文游风格及内容，且经过美化的HTML游戏界面。"
                "必须遵守："
                "1) 生成数量根据指令需求自行决定（可为单个面板或多个面板）。"
                "2) 色彩搭配要根据分析后的游戏指令生成，配色合理。"
                "3) UI界面要用描边修饰，展示包括但不限于玩家信息、剧情、事件、人物信息等版块内容。"
                "4) 每张卡片体现玩法但不能泄露指令具体内容，看起来像真实图形界面；内容充实不留白。"
                "5) 文本对比度明显，避免过暗或过亮。"
                "6) 允许适当emoji与图片。"
                "7) 使用换行符表现信息（正文容器需配合 white-space: pre-line）。"
                "8) 严禁胡编乱造。所有具体事实、角色、数值、事件、地点必须来自输入的历史对话、世界状态或RAG检索。"
                "9) 若输入中没有对应事实，用“未知/暂无/待揭示”占位，不要猜测。"
                "只输出严格 JSON，格式："
                "{{\"panels\":[{{\"title\":\"...\",\"html\":\"...\"}}, ...]}}。"
                "不要输出 markdown 或多余文本。"
            ),
        ),
        ('human', '卡牌信息：\n{card_meta}\n\n游戏指令资料：\n{instruction_text}\n\n世界状态：\n{world_facts}\n\n最近对话：\n{recent_messages}\n\nRAG检索片段：\n{rag_snippets}\n'),
    ])
    return prompt.format_messages(
        instruction_text=_get(state, 'instruction_text', ''),
        card_meta=_get(state, 'card_meta', {}),
        world_facts=_get(state, 'world_facts', {}),
        recent_messages=_get(state, 'recent_messages', []),
        rag_snippets=_get(state, 'rag_snippets', []),
    )


def llm_plan_ops(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 生成 ops JSON，失败时重试并回退。"""
    llm = get_llm()
    if isinstance(llm, MockLLM):
        return llm.plan(state)

    messages = build_plan_prompt(state)
    response = llm.invoke(messages)
    try:
        return json.loads(response.content)
    except Exception:
        # One retry with stricter instruction
        retry = ChatPromptTemplate.from_messages([
            ('system', 'Return ONLY valid JSON. No markdown.'),
            ('human', '{text}')
        ]).format_messages(text=response.content)
        response2 = llm.invoke(retry)
        try:
            return json.loads(response2.content)
        except Exception:
            return {'ops': []}


def llm_narrate(state: Dict[str, Any]) -> str:
    """调用 LLM 生成叙事文本。"""
    llm = get_llm()
    if isinstance(llm, MockLLM):
        return llm.narrate(state)
    messages = build_narrate_prompt(state)
    response = llm.invoke(messages)
    return response.content


def llm_generate_ui_panels(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 生成 UI 面板 HTML JSON。"""
    llm = get_llm()
    if isinstance(llm, MockLLM):
        return llm.ui_panels(state)
    messages = build_ui_panels_prompt(state)
    response = llm.invoke(messages)
    try:
        return json.loads(response.content)
    except Exception:
        retry = ChatPromptTemplate.from_messages([
            ('system', 'Return ONLY valid JSON. No markdown.'),
            ('human', '{text}')
        ]).format_messages(text=response.content)
        response2 = llm.invoke(retry)
        try:
            return json.loads(response2.content)
        except Exception:
            return {'panels': []}


def build_ui_update_prompt(state: Dict[str, Any]) -> List[HumanMessage]:
    """构建 UI 面板更新提示词（判断是否需要更新）。"""
    prompt = ChatPromptTemplate.from_messages([
        (
            'system',
            (
                "你是一个游戏UI更新助手。根据最新信息判断是否需要更新当前面板。"
                "只输出严格 JSON，格式："
                "{{\"update\":true/false,\"html\":\"...\"}}。"
                "若无需更新，update=false 且 html 为空字符串。"
                "需要更新时，输出完整 HTML，保持面板主题一致。"
                "严禁胡编乱造。所有具体事实、角色、数值、事件、地点必须来自输入的历史对话、世界状态或RAG检索。"
                "若输入中没有对应事实，用“未知/暂无/待揭示”占位，不要猜测。"
                "不要输出 markdown 或多余文本。"
            ),
        ),
        ('human', '面板标题：{panel_title}\n当前HTML：\n{current_html}\n\n卡牌信息：\n{card_meta}\n\n世界状态：\n{world_facts}\n\n最近对话：\n{recent_messages}\n\nRAG检索片段：\n{rag_snippets}\n'),
    ])
    return prompt.format_messages(
        panel_title=_get(state, 'panel_title', ''),
        current_html=_get(state, 'current_html', ''),
        card_meta=_get(state, 'card_meta', {}),
        world_facts=_get(state, 'world_facts', {}),
        recent_messages=_get(state, 'recent_messages', []),
        rag_snippets=_get(state, 'rag_snippets', []),
    )


def llm_update_ui_panel(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 判断并生成 UI 面板更新。"""
    llm = get_llm()
    if isinstance(llm, MockLLM):
        return {'update': False, 'html': ''}
    messages = build_ui_update_prompt(state)
    response = llm.invoke(messages)
    try:
        return json.loads(response.content)
    except Exception:
        retry = ChatPromptTemplate.from_messages([
            ('system', 'Return ONLY valid JSON. No markdown.'),
            ('human', '{text}')
        ]).format_messages(text=response.content)
        response2 = llm.invoke(retry)
        try:
            return json.loads(response2.content)
        except Exception:
            return {'update': False, 'html': ''}
