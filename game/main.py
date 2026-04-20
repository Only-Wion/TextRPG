from __future__ import annotations

from copy import deepcopy
import threading

from .core.card_repository import CardRepository
from .core.rule_engine import RuleEngine
from .core.graph import build_turn_graphs, retrieve_context, should_run_ops
from .core.story_graph import seed_story_runtime
from .config import get_slot_paths
from .infrastructure.contracts import KGStoreProtocol, WorldStoreProtocol
from .infrastructure.store_factory import SessionStoreFactory


def bootstrap(
    repo: CardRepository, world: WorldStoreProtocol, kg: KGStoreProtocol
) -> None:
    """用卡牌图数据初始化 KG 和事件运行时状态。"""
    seed_story_runtime(repo, world, kg, turn=0)


def main() -> None:
    """CLI 主循环入口。"""
    repo = CardRepository()
    repo.load()
    paths = get_slot_paths("slot_001")
    stores = SessionStoreFactory().create(
        world_db_path=paths["world_db_path"],
        kg_db_path=paths["kg_db_path"],
        rag_dir=paths["rag_dir"],
    )
    world = stores.world
    kg = stores.kg
    rag = stores.rag
    cards_index = {c.id: {"type": c.type, "tags": c.tags} for c in repo.all()}
    rules = RuleEngine(cards_index)

    bootstrap(repo, world, kg)

    graphs = build_turn_graphs(repo, rag, world, kg, rules)
    state = {
        "turn_id": 0,
        "recent_messages": [],
        "chat_history": [],
    }
    state.update(retrieve_context(state, repo, rag, world, kg, rules))

    print("Welcome to TextRPG. Type /help for commands, or /quit to exit.\n")
    opening = repo.get("opening")
    if opening:
        print(opening.content + "\n")

    while True:
        player_input = input("> ").strip()
        if player_input.lower() in ("/quit", "/exit"):
            break
        state["turn_id"] = state.get("turn_id", 0) + 1
        state["player_input"] = player_input
        turn_state = deepcopy(state)

        ops_result_box: dict[str, object] = {}
        ops_error_box: list[BaseException] = []

        ops_thread: threading.Thread | None = None
        if should_run_ops(turn_state):

            def run_ops() -> None:
                try:
                    ops_result_box["result"] = graphs.ops_app.invoke(
                        deepcopy(turn_state)
                    )
                except Exception as exc:
                    ops_error_box.append(exc)

            ops_thread = threading.Thread(target=run_ops, daemon=True)
            ops_thread.start()

        result = graphs.narration_app.invoke(turn_state)
        if ops_thread is not None:
            ops_thread.join()
            if ops_error_box:
                raise ops_error_box[0]
            if isinstance(ops_result_box.get("result"), dict):
                state.update(ops_result_box["result"])

        narration = result.get("narration", "")
        if narration:
            print("\n" + narration + "\n")
        state.update(result)
        history = list(state.get("chat_history", []))
        history.append({"role": "user", "content": player_input})
        history.append({"role": "assistant", "content": narration})
        state["chat_history"] = history
        state["recent_messages"] = history[-10:]


if __name__ == "__main__":
    main()
