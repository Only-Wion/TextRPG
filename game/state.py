from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

class GameState(BaseModel):
    """LangGraph 流程中传递的运行时状态。"""
    turn_id: int = 0
    player_input: str = ''
    recent_messages: List[Dict[str, str]] = Field(default_factory=list)
    chat_history: List[Dict[str, str]] = Field(default_factory=list)
    retrieved_cards: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_memories: List[Dict[str, Any]] = Field(default_factory=list)
    draft_ops: List[Dict[str, Any]] = Field(default_factory=list)
    overlay_ops: List[Dict[str, Any]] = Field(default_factory=list)
    validated_ops: List[Dict[str, Any]] = Field(default_factory=list)
    world_facts: Dict[str, Any] = Field(default_factory=dict)
    narration: str = ''
    allowed_actions: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    save_slot: str = 'slot_001'
    snapshot_dir: str = ''
    enabled_packs: List[str] = Field(default_factory=list)
    language: str = 'zh'
