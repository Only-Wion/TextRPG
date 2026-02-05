from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml

from ..ops import OpsPayload
from ..config import CARDS_DIR

@dataclass
class RuleConfig:
    """关系约束与派生规则的解析结果。"""
    relations: Dict[str, Dict[str, Any]]
    derived_rules: List[Dict[str, Any]]


def load_rule_config(path: Path) -> RuleConfig:
    """从 card_logic.md frontmatter 加载规则配置。"""
    text = path.read_text(encoding='utf-8')
    if text.startswith('---'):
        parts = text.split('---', 2)
        fm = yaml.safe_load(parts[1]) or {}
    else:
        fm = {}
    return RuleConfig(
        relations=fm.get('relations', {}),
        derived_rules=fm.get('derived_rules', []),
    )


class RuleEngine:
    """基于关系约束校验 ops，并推导可用动作。"""
    def __init__(self, cards_index: Dict[str, Any], logic_path: Path | None = None):
        logic_path = logic_path or (CARDS_DIR / 'card_logic.md')
        self.config = load_rule_config(logic_path)
        self.cards_index = cards_index

    def validate_ops(self, ops_payload: OpsPayload, edges: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """校验 ops 并自动修复冲突，返回 (valid_ops, errors)。"""
        valid_ops: List[Dict[str, Any]] = []
        errors: List[str] = []
        for op in ops_payload.ops:
            data = op.model_dump()
            op_type = data['type']
            if op_type in ('AddEdge', 'RemoveEdge'):
                if not self._entity_exists(data['subject_id']) or not self._entity_exists(data['object_id']):
                    errors.append(f'Unknown entity in {op_type}: {data}')
                    continue
                if op_type == 'AddEdge' and not self._relation_allowed(data['subject_id'], data['relation'], data['object_id']):
                    errors.append(f'Relation not allowed: {data}')
                    continue
                if op_type == 'AddEdge':
                    overflow = self._relation_overflow_edges(data['subject_id'], data['relation'], edges)
                    if overflow:
                        for e in overflow:
                            valid_ops.append({
                                'type': 'RemoveEdge',
                                'subject_id': e['subject_id'],
                                'relation': e['relation'],
                                'object_id': e['object_id'],
                                'confidence': e.get('confidence', 0.8),
                                'source': 'rule_engine'
                            })
                        errors.append(f'Auto-removed existing relation(s) to satisfy constraint: {data}')
            if op_type == 'SetAttr':
                if not self._entity_exists(data['entity_id']):
                    errors.append(f'Unknown entity in SetAttr: {data}')
                    continue
            valid_ops.append(data)
        return valid_ops, errors

    def allowed_actions(self, world_facts: Dict[str, Any]) -> List[str]:
        """根据派生规则计算允许的动作。"""
        actions: List[str] = []
        edges = world_facts.get('edges', [])
        attrs = world_facts.get('attrs', {})
        for rule in self.config.derived_rules:
            if self._rule_matches(rule, edges, attrs):
                actions.append(rule.get('allow_action'))
        return [a for a in actions if a]

    def _rule_matches(self, rule: Dict[str, Any], edges: List[Dict[str, Any]], attrs: Dict[str, Any]) -> bool:
        """判断派生规则的条件是否满足。"""
        cond = rule.get('when', {})
        required_edges = cond.get('edges', [])
        for e in required_edges:
            found = any(x['subject_id'] == e['subject_id'] and x['relation'] == e['relation'] and x['object_id'] == e['object_id'] for x in edges)
            if not found:
                return False
        required_attrs = cond.get('attrs', [])
        for a in required_attrs:
            ent = a['entity_id']
            if attrs.get(ent, {}).get(a['key']) != a['value']:
                return False
        return True

    def _entity_exists(self, entity_id: str) -> bool:
        """判断实体 id 是否存在于卡牌索引中。"""
        return entity_id in self.cards_index

    def _relation_allowed(self, subject_id: str, relation: str, object_id: str) -> bool:
        """校验关系配置与主客体类型是否匹配。"""
        config = self.config.relations.get(relation)
        if not config:
            return False
        subj_type = self.cards_index.get(subject_id, {}).get('type')
        obj_type = self.cards_index.get(object_id, {}).get('type')
        if subj_type not in config.get('subject_types', []):
            return False
        if obj_type not in config.get('object_types', []):
            return False
        return True

    def _relation_overflow_edges(self, subject_id: str, relation: str, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """当关系超过上限时，找出需要移除的边。"""
        config = self.config.relations.get(relation)
        if not config:
            return []
        limit = int(config.get('max_per_subject', 0))
        if limit <= 0:
            return []
        current = [e for e in edges if e['subject_id'] == subject_id and e['relation'] == relation]
        if len(current) >= limit:
            return current
        return []
