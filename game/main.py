from __future__ import annotations

from .core.card_repository import CardRepository
from .core.rule_engine import RuleEngine
from .core.rag_store import RAGStore
from .core.kg_store import KGStore
from .core.world_store import WorldStore
from .core.graph import build_graph
from .config import DATA_DIR


def bootstrap(repo: CardRepository, world: WorldStore, kg: KGStore) -> None:
    """当 KG 为空时，用卡牌的初始关系做一次初始化。"""
    if kg.all_edges():
        return
    for card in repo.all():
        for rel in card.initial_relations:
            kg.add_edge(rel['subject_id'], rel['relation'], rel['object_id'], 0.9, 'bootstrap')


def main() -> None:
    """CLI 主循环入口。"""
    repo = CardRepository()
    repo.load()
    world = WorldStore()
    kg = KGStore()
    rag = RAGStore()
    cards_index = {c.id: {'type': c.type, 'tags': c.tags} for c in repo.all()}
    rules = RuleEngine(cards_index)

    bootstrap(repo, world, kg)

    app = build_graph(repo, rag, world, kg, rules)
    state = {
        'turn_id': 0,
        'recent_messages': [],
        'chat_history': [],
    }

    print('Welcome to TextRPG. Type /help for commands, or /quit to exit.\n')
    opening = repo.get('opening')
    if opening:
        print(opening.content + '\n')

    while True:
        player_input = input('> ').strip()
        if player_input.lower() in ('/quit', '/exit'):
            break
        state['turn_id'] = state.get('turn_id', 0) + 1
        state['player_input'] = player_input

        result = app.invoke(state)
        narration = result.get('narration', '')
        if narration:
            print('\n' + narration + '\n')
        state.update(result)
        history = list(state.get('chat_history', []))
        history.append({'role': 'user', 'content': player_input})
        history.append({'role': 'assistant', 'content': narration})
        state['chat_history'] = history
        state['recent_messages'] = history[-10:]


if __name__ == '__main__':
    main()
