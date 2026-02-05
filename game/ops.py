from __future__ import annotations

from typing import List, Literal, Union
from pydantic import BaseModel, Field

class AddEdge(BaseModel):
    """向知识图谱添加一条关系边。"""
    type: Literal['AddEdge'] = 'AddEdge'
    subject_id: str
    relation: str
    object_id: str
    confidence: float = 0.8
    source: str = 'llm'

class RemoveEdge(BaseModel):
    """从知识图谱移除一条关系边。"""
    type: Literal['RemoveEdge'] = 'RemoveEdge'
    subject_id: str
    relation: str
    object_id: str
    confidence: float = 0.8
    source: str = 'llm'

class SetAttr(BaseModel):
    """设置实体的动态属性。"""
    type: Literal['SetAttr'] = 'SetAttr'
    entity_id: str
    key: str
    value: str
    source: str = 'llm'

class LogMemory(BaseModel):
    """将语义记忆片段写入向量库。"""
    type: Literal['LogMemory'] = 'LogMemory'
    text: str
    tags: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    source: str = 'llm'

Op = Union[AddEdge, RemoveEdge, SetAttr, LogMemory]

class OpsPayload(BaseModel):
    """用于承载 LLM/管理员/覆盖层产生的一批 ops。"""
    ops: List[Op] = Field(default_factory=list)
