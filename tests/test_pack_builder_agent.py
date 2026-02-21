from pathlib import Path

from game.packs.manager import PackManager
from game.service.api import GameService
from game.service.pack_builder_agent import ActionPlan, PackBuilderAgent


def build_service(tmp_path: Path) -> GameService:
    service = GameService(packs_root=tmp_path / "packs")
    service.pack_manager = PackManager(packs_root=tmp_path / "packs", registry_path=tmp_path / "registry.json")
    service.create_pack(
        {
            "pack_id": "demo_pack",
            "name": "Demo Pack",
            "version": "0.1.0",
            "author": "tester",
            "description": "demo",
            "cards_root": "cards",
        }
    )
    return service


def test_read_only_question_shortcut_lists_packs(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {"history": [], "question_mode": True, "creation_started": False, "selected_pack_id": "demo_pack"}

    result = agent.process("当前有哪些卡牌包", state)

    assert "demo_pack" in result["assistant"]
    assert result["tool_logs"] == []


def test_write_actions_require_confirmation(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {"history": [], "selected_pack_id": "demo_pack"}

    def fake_plan(_user_input: str, _state: dict) -> ActionPlan:
        return ActionPlan(
            reply="准备创建卡牌",
            actions=[
                {
                    "tool": "save_card",
                    "args": {
                        "pack_id": "demo_pack",
                        "card_type": "quest",
                        "card_id": "q1",
                        "frontmatter": {"tags": ["main"]},
                        "body": "Quest 1",
                    },
                }
            ],
        )

    agent._plan = fake_plan  # type: ignore[method-assign]
    first = agent.process("创建一个任务卡", state)
    cards = {p.name for p in service.list_pack_cards("demo_pack")}
    assert "q1.md" not in cards
    assert "确认执行" in first["assistant"]
    assert isinstance(first["state"].get("pending_write_plan"), dict)

    second = agent.process("confirm", first["state"])
    cards = {p.name for p in service.list_pack_cards("demo_pack")}
    assert "q1.md" in cards
    assert second["state"].get("pending_write_plan") is None


def test_read_then_write_followup(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {"history": [], "selected_pack_id": "demo_pack"}

    plans = [
        ActionPlan(reply="先看一下", actions=[{"tool": "list_packs", "args": {}}]),
        ActionPlan(
            reply="然后创建",
            actions=[{"tool": "create_pack", "args": {"manifest": {"pack_id": "p2", "name": "P2"}}}],
        ),
    ]

    def fake_plan(_user_input: str, _state: dict) -> ActionPlan:
        return plans.pop(0)

    agent._plan = fake_plan  # type: ignore[method-assign]
    result = agent.process("开始创建", state)
    assert any("list_packs" in x for x in result["tool_logs"])
    assert "确认执行" in result["assistant"]
    assert isinstance(result["state"].get("pending_write_plan"), dict)


def test_read_card_tool(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {"history": [], "selected_pack_id": "demo_pack"}

    agent._execute_actions(
        [
            {
                "tool": "save_card",
                "args": {
                    "pack_id": "demo_pack",
                    "card_type": "event",
                    "card_id": "e1",
                    "frontmatter": {"title": "E1", "tags": []},
                    "body": "Event body",
                },
            }
        ],
        state,
    )
    logs = agent._execute_actions(
        [{"tool": "read_card", "args": {"pack_id": "demo_pack", "card_path": "events/e1.md"}}],
        state,
    )
    assert any("read_card(demo_pack)" in x for x in logs)
    assert any("Event body" in x for x in logs)
