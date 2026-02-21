from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from game.packs.manager import PackManager
from game.config import save_runtime_llm_settings
from game.service.api import GameService
from game.service.pack_builder_agent import ActionPlan, PackBuilderAgent


def _build_service(packs_root: Path) -> GameService:
    service = GameService(packs_root=packs_root)
    service.pack_manager = PackManager(
        packs_root=packs_root,
        registry_path=packs_root.parent / "registry.json",
    )
    return service


def _ensure_pack(service: GameService, pack_id: str) -> None:
    existing = {p["pack_id"] for p in service.list_packs()}
    if pack_id in existing:
        return
    service.create_pack(
        {
            "pack_id": pack_id,
            "name": pack_id.replace("_", " ").title(),
            "version": "0.1.0",
            "author": "debugger",
            "description": "debug pack",
            "cards_root": "cards",
        }
    )


def _load_lines(script_file: Path) -> List[str]:
    raw = script_file.read_text(encoding="utf-8-sig")
    lines = [line.strip() for line in raw.splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def _load_mock_plan(plan_file: Path) -> ActionPlan:
    data = json.loads(plan_file.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("mock plan file must be a json object")
    reply = str(data.get("reply", "mock reply"))
    actions = data.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("mock plan 'actions' must be a list")
    return ActionPlan(reply=reply, actions=[a for a in actions if isinstance(a, dict)])


def _run_dialog(
    agent: PackBuilderAgent,
    state: Dict[str, Any],
    user_inputs: Iterable[str],
) -> Dict[str, Any]:
    for idx, user_input in enumerate(user_inputs, start=1):
        result = agent.process(user_input, state)
        print(f"\n=== TURN {idx} ===")
        print(f"user: {user_input}")
        print(f"assistant: {result.get('assistant', '')}")
        print("tool_logs:")
        for line in result.get("tool_logs", []):
            print(f"- {line}")
        state = result.get("state", state)
        print("state_snapshot:")
        print(
            json.dumps(
                {
                    "question_mode": bool(state.get("question_mode", True)),
                    "creation_started": bool(state.get("creation_started", False)),
                    "selected_pack_id": state.get("selected_pack_id", ""),
                    "history_len": len(state.get("history", [])),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug runner for PackBuilderAgent")
    parser.add_argument("--packs-root", type=Path, help="Custom packs root")
    parser.add_argument("--pack-id", default="debug_pack", help="Selected/default pack id")
    parser.add_argument("--script-file", type=Path, help="Text file with one user input per line")
    parser.add_argument("--mock-plan", type=Path, help="Optional action-plan JSON for monkey patching _plan")
    parser.add_argument("--question-mode", action="store_true", help="Start in question mode")
    parser.add_argument("--creation-started", action="store_true", help="Start with creation_started=True")
    parser.add_argument("--api-key", help="LLM API key for this project runtime config")
    parser.add_argument("--base-url", help="LLM base URL, e.g. https://api.deepseek.com/v1")
    parser.add_argument("--model", help="LLM model name, e.g. deepseek-chat")
    parser.add_argument("--embedding-model", help="Embedding model name when not using fake embeddings")
    parser.add_argument(
        "--use-fake-embeddings",
        action="store_true",
        help="Force FakeEmbeddings (recommended for DeepSeek-compatible chat-only endpoints)",
    )
    args = parser.parse_args()

    if args.packs_root:
        packs_root = args.packs_root.resolve()
    else:
        packs_root = (PROJECT_ROOT / ".debug" / "pack_builder" / "packs").resolve()

    packs_root.mkdir(parents=True, exist_ok=True)

    if args.api_key or args.base_url or args.model or args.embedding_model or args.use_fake_embeddings:
        inferred_deepseek = bool(args.base_url and "deepseek" in args.base_url.lower())
        model_name = args.model or ("deepseek-chat" if inferred_deepseek else "gpt-4o-mini")
        save_runtime_llm_settings(
            {
                "provider": "deepseek" if inferred_deepseek else "custom",
                "model_name": model_name,
                "embedding_model": args.embedding_model or "text-embedding-3-small",
                "base_url": args.base_url or "",
                "api_key": args.api_key or "",
                "use_mock_llm": False,
                "force_fake_embeddings": bool(args.use_fake_embeddings),
            }
        )

    service = _build_service(packs_root)
    _ensure_pack(service, args.pack_id)

    agent = PackBuilderAgent(service)
    if args.mock_plan:
        mock_plan = _load_mock_plan(args.mock_plan)
        agent._plan = lambda _user_input, _state: mock_plan  # type: ignore[method-assign]

    state: Dict[str, Any] = {
        "history": [],
        "question_mode": bool(args.question_mode),
        "creation_started": bool(args.creation_started),
        "selected_pack_id": args.pack_id,
    }

    if args.script_file:
        user_inputs = _load_lines(args.script_file)
        state = _run_dialog(agent, state, user_inputs)
    else:
        print("Interactive mode. Input ':q' to quit.")
        while True:
            user_input = input("\nuser> ").strip()
            if user_input in {":q", ":quit", "quit", "exit"}:
                break
            state = _run_dialog(agent, state, [user_input])

    print(f"\nPacks root: {packs_root}")
    if not args.packs_root:
        print("Using default debug directory under .debug/pack_builder")


if __name__ == "__main__":
    main()
