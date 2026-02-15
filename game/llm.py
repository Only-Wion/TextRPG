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
