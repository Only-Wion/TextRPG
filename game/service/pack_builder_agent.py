from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool

from ..llm import MockLLM, get_llm
from .api import GameService


@dataclass
class ActionPlan:
    reply: str
    actions: List[Dict[str, Any]]


class PackBuilderAgent:
    """Conversational agent for pack creation/editing."""

    START_CREATE_WORDS = {"开始创建", "开始", "start create", "create now", "开始进行创建"}
    CONFIRM_WORDS = {"确认", "同意", "继续", "执行", "yes", "y", "ok", "go", "confirm"}
    REJECT_WORDS = {"取消", "不要", "拒绝", "否", "no", "n", "cancel", "stop"}
    READ_ONLY_TOOLS = {"list_packs", "list_pack_cards", "list_pack_card_types", "read_card", "audit_pack"}
    WRITE_TOOLS = {"create_pack", "select_pack", "save_card", "batch_save_cards", "delete_card"}
    MAX_AUTORUN_STEPS = 5

    def __init__(self, service: GameService):
        self.service = service
        prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        self.system_prompt = (prompts_dir / "pack_builder_system.md").read_text(encoding="utf-8")
        self.question_prompt = (prompts_dir / "pack_builder_question_mode.md").read_text(encoding="utf-8")
        self.tool_schemas = [
            {"name": "list_packs", "args": {}},
            {"name": "create_pack", "args": {"manifest": "dict"}},
            {"name": "select_pack", "args": {"pack_id": "str"}},
            {"name": "list_pack_cards", "args": {"pack_id": "str"}},
            {"name": "list_pack_card_types", "args": {"pack_id": "str"}},
            {"name": "read_card", "args": {"pack_id": "str", "card_path": "str"}},
            {
                "name": "save_card",
                "args": {
                    "pack_id": "str",
                    "card_type": "str",
                    "card_id": "str",
                    "frontmatter": "dict",
                    "body": "str",
                },
            },
            {"name": "delete_card", "args": {"pack_id": "str", "card_path": "str"}},
            {"name": "batch_save_cards", "args": {"pack_id": "str", "cards": "list[dict]"}},
            {"name": "audit_pack", "args": {"pack_id": "str"}},
        ]

    def process(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        history = list(state.get("history", []))
        state.setdefault("question_mode", True)
        state.setdefault("creation_started", False)

        pending = state.get("pending_write_plan")
        if isinstance(pending, dict):
            confirmation_result = self._handle_pending_confirmation(user_input, state)
            if confirmation_result:
                assistant, tool_logs = confirmation_result
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": assistant})
                state["history"] = history
                state["memory"] = self._update_memory(history)
                return {"assistant": assistant, "state": state, "tool_logs": tool_logs}

        normalized = user_input.strip().lower()
        if normalized in self.START_CREATE_WORDS:
            state["creation_started"] = True
            state["question_mode"] = False

        shortcut = self._question_mode_tool_shortcut(user_input)
        if shortcut:
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": shortcut})
            state["history"] = history
            state["memory"] = self._update_memory(history)
            return {"assistant": shortcut, "state": state, "tool_logs": []}

        assistant, tool_logs = self._plan_and_run_loop(user_input, state)

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": assistant})
        state["history"] = history
        state["memory"] = self._update_memory(history)
        return {"assistant": assistant, "state": state, "tool_logs": tool_logs}

    def _handle_pending_confirmation(self, user_input: str, state: Dict[str, Any]) -> tuple[str, List[str]] | None:
        normalized = user_input.strip().lower()
        if any(word in normalized for word in self.REJECT_WORDS):
            state.pop("pending_write_plan", None)
            return "已取消本次修改计划。你可以继续提需求，我会重新规划。", []
        if not any(word in normalized for word in self.CONFIRM_WORDS):
            return "检测到有待执行的修改计划。请回复“确认执行”或“取消”。", []

        pending = state.pop("pending_write_plan", {})
        actions = list(pending.get("actions", []))
        tool_logs = self._execute_actions(actions, state)

        followup_seed = "继续基于最新执行结果推进任务，直到可以自然收束。"
        followup_reply, followup_logs = self._plan_and_run_loop(followup_seed, state)
        all_logs = tool_logs + followup_logs
        reply = "已执行你确认的修改计划。"
        if followup_reply.strip():
            reply += "\n" + followup_reply.strip()
        if all_logs:
            reply += "\n\n执行记录：\n" + "\n".join(f"- {x}" for x in all_logs)
        return reply, all_logs

    def _question_mode_tool_shortcut(self, user_input: str) -> str:
        normalized = user_input.strip().lower()
        pack_keywords = ["卡牌包", "卡包", "packs", "pack"]
        ask_list_keywords = ["哪些", "有哪些", "当前", "可用", "list", "show"]
        if any(k in normalized for k in pack_keywords) and any(k in normalized for k in ask_list_keywords):
            packs = self.service.list_packs()
            if not packs:
                return "当前没有可用卡牌包。若你愿意，我可以先为你创建一个基础卡牌包。"
            pack_ids = [str(p.get("pack_id", "")) for p in packs if p.get("pack_id")]
            return (
                f"当前可用卡牌包（{len(pack_ids)}）：{pack_ids}\n"
                "告诉我你希望基于哪个包继续，或直接描述新包需求。"
            )
        return ""

    def _plan_and_run_loop(self, seed_input: str, state: Dict[str, Any]) -> tuple[str, List[str]]:
        logs: List[str] = []
        replies: List[str] = []
        next_input = seed_input
        seen_action_signatures: set[str] = set()

        for _ in range(self.MAX_AUTORUN_STEPS):
            plan = self._plan(next_input, state)
            if plan.reply.strip():
                replies.append(plan.reply.strip())
            actions = list(plan.actions)
            if not actions:
                break

            signature = json.dumps(actions, ensure_ascii=False, sort_keys=True)
            if signature in seen_action_signatures:
                replies.append("检测到重复动作计划，已停止自动循环，避免死循环。")
                break
            seen_action_signatures.add(signature)

            if self._contains_write_actions(actions):
                state["pending_write_plan"] = {"actions": actions, "reply": plan.reply}
                confirm_msg = self._build_write_confirmation_message(plan)
                if logs:
                    confirm_msg += "\n\n已先执行只读记录：\n" + "\n".join(f"- {x}" for x in logs)
                return confirm_msg, logs

            step_logs = self._execute_actions(actions, state)
            logs.extend(step_logs)
            next_input = self._build_followup_input(seed_input, step_logs, state)

        if not replies:
            replies.append("已处理你的请求。")
        final_reply = "\n".join(replies).strip()
        if logs:
            final_reply += "\n\n执行记录：\n" + "\n".join(f"- {x}" for x in logs)
        return final_reply, logs

    def _contains_write_actions(self, actions: List[Dict[str, Any]]) -> bool:
        action_names = [str(a.get("tool", "")).strip() for a in actions]
        return any(name in self.WRITE_TOOLS for name in action_names)

    def _build_write_confirmation_message(self, plan: ActionPlan) -> str:
        action_lines = []
        for action in list(plan.actions):
            tool = str(action.get("tool", "")).strip()
            args = action.get("args", {}) or {}
            action_lines.append(f"- {tool}: {json.dumps(args, ensure_ascii=False)}")

        base = plan.reply.strip() or "已生成修改计划。"
        detail = "\n".join(action_lines) if action_lines else "- （无动作）"
        return (
            f"{base}\n\n以下动作将修改数据，请确认后执行：\n"
            f"{detail}\n\n回复“确认执行”继续，回复“取消”放弃本次修改。"
        )

    def _build_followup_input(self, original_input: str, latest_logs: List[str], state: Dict[str, Any]) -> str:
        recent_logs = latest_logs[-6:]
        return json.dumps(
            {
                "continue_from": original_input,
                "latest_tool_logs": recent_logs,
                "selected_pack_id": state.get("selected_pack_id", ""),
                "instruction": "继续规划下一步。如果目标已完成，返回空 actions。",
            },
            ensure_ascii=False,
        )

    def _build_bootstrap_input(self, state: Dict[str, Any]) -> str:
        history = list(state.get("history", []))
        user_lines: List[str] = []
        for msg in history:
            if msg.get("role") != "user":
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if content.lower() in self.START_CREATE_WORDS:
                continue
            user_lines.append(content)

        if user_lines:
            recent = "\n".join(f"- {line}" for line in user_lines[-5:])
            return "请根据以下已确认需求，开始工具规划：\n" + recent
        return "请基于当前上下文开始工具规划。"

    def _question_mode_reply(self, user_input: str, state: Dict[str, Any]) -> str:
        llm = get_llm()
        if isinstance(llm, MockLLM):
            return (
                "我会先帮你完善需求，然后进入创建。\n"
                "建议先确认：世界主题、核心循环、卡牌类型数量、首小时目标。"
            )

        messages = [
            SystemMessage(content=self.question_prompt),
            HumanMessage(content=json.dumps({"user_input": user_input, "state": state}, ensure_ascii=False)),
        ]
        try:
            resp = llm.invoke(messages)
            return str(resp.content)
        except Exception as exc:
            return f"LLM call failed in question mode: {exc}"

    def _plan(self, user_input: str, state: Dict[str, Any]) -> ActionPlan:
        llm = get_llm()
        if isinstance(llm, MockLLM):
            return ActionPlan(
                reply="当前为离线 mock 模式。请描述 pack、卡牌类型和数量。",
                actions=[],
            )

        tool_schema = {"tools": self.tool_schemas}
        messages = [
            SystemMessage(
                content=(
                    self.system_prompt
                    + '\n\nYou must output strict JSON: {"reply":"...","actions":[{"tool":"...","args":{}}]}. '
                    + "No markdown wrappers. If task done, return empty actions."
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "user_input": user_input,
                        "memory": state.get("memory", ""),
                        "selected_pack_id": state.get("selected_pack_id", ""),
                        "tool_schema": tool_schema,
                    },
                    ensure_ascii=False,
                )
            ),
        ]
        try:
            resp = llm.invoke(messages)
        except Exception as exc:
            return ActionPlan(reply=f"LLM call failed in planning: {exc}", actions=[])
        parsed = self._parse_json(str(resp.content))
        if not parsed:
            retry_messages = [
                SystemMessage(content='Return STRICT JSON only: {"reply":"...","actions":[{"tool":"...","args":{}}]}'),
                HumanMessage(content=str(resp.content)),
            ]
            try:
                retry = llm.invoke(retry_messages)
            except Exception as exc:
                return ActionPlan(reply=f"LLM retry failed in planning: {exc}", actions=[])
            parsed = self._parse_json(str(retry.content))
        if not parsed:
            return ActionPlan(reply=str(resp.content), actions=[])
        return ActionPlan(reply=str(parsed.get("reply", "")), actions=list(parsed.get("actions", [])))

    def _safe_pack_id(self, raw: str, fallback: str = "generated_pack") -> str:
        base = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(raw or "").strip()).strip("_").lower()
        return base or fallback

    def _build_manifest_with_defaults(self, manifest: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        source = dict(manifest)
        preferred = source.get("pack_id") or source.get("name") or "generated_pack"
        pack_id = self._safe_pack_id(str(preferred), fallback="generated_pack")
        return {
            "pack_id": pack_id,
            "name": str(source.get("name") or pack_id.replace("_", " ").title()),
            "version": str(source.get("version") or "0.1.0"),
            "author": str(source.get("author") or "PackBuilderAgent"),
            "description": str(source.get("description") or "Generated by Pack Builder Agent"),
            "cards_root": str(source.get("cards_root") or "cards"),
        }

    def _normalize_card_payload(self, card: Dict[str, Any], default_type: str = "card") -> Dict[str, Any]:
        data = dict(card)
        frontmatter = dict(data.get("frontmatter", {}))
        card_type = str(data.get("card_type") or frontmatter.get("type") or default_type).strip() or default_type
        card_id = str(data.get("card_id") or frontmatter.get("id") or "new_card").strip() or "new_card"

        frontmatter.setdefault("id", card_id)
        frontmatter.setdefault("type", card_type)
        tags = frontmatter.get("tags")
        if not isinstance(tags, list):
            frontmatter["tags"] = [] if tags is None else [str(tags)]

        return {
            "card_type": card_type,
            "card_id": card_id,
            "frontmatter": frontmatter,
            "body": str(data.get("body", "") or "TBD"),
        }

    def _execute_actions(self, actions: List[Dict[str, Any]], state: Dict[str, Any]) -> List[str]:
        logs: List[str] = []
        tools = self._build_runtime_tools(state)
        for action in actions:
            tool_name = str(action.get("tool", "")).strip()
            args = action.get("args", {}) or {}
            handler = tools.get(tool_name)
            if not handler:
                logs.append(f"unknown tool: {tool_name}")
                continue
            try:
                logs.append(str(handler.invoke(args)))
            except Exception as exc:
                logs.append(f"{tool_name} failed: {exc}")
        return logs

    def _build_runtime_tools(self, state: Dict[str, Any]) -> Dict[str, StructuredTool]:
        return {
            "list_packs": StructuredTool.from_function(
                name="list_packs",
                description="列出当前已注册的卡牌包。",
                func=self._tool_list_packs,
            ),
            "create_pack": StructuredTool.from_function(
                name="create_pack",
                description="创建一个新的卡牌包。",
                func=lambda manifest: self._tool_create_pack(manifest, state),
            ),
            "select_pack": StructuredTool.from_function(
                name="select_pack",
                description="选择后续操作要使用的卡牌包。",
                func=lambda pack_id: self._tool_select_pack(pack_id, state),
            ),
            "list_pack_cards": StructuredTool.from_function(
                name="list_pack_cards",
                description="列出某个卡牌包中的全部卡牌文件。",
                func=lambda pack_id="": self._tool_list_pack_cards(pack_id, state),
            ),
            "list_pack_card_types": StructuredTool.from_function(
                name="list_pack_card_types",
                description="列出某个卡牌包中已有及可用的卡牌类型。",
                func=lambda pack_id="": self._tool_list_pack_card_types(pack_id, state),
            ),
            "read_card": StructuredTool.from_function(
                name="read_card",
                description="读取卡牌文件内容（frontmatter + body）。card_path 支持相对 cards_root 路径。",
                func=lambda pack_id="", card_path="": self._tool_read_card(pack_id, card_path, state),
            ),
            "save_card": StructuredTool.from_function(
                name="save_card",
                description="保存单张卡牌。",
                func=lambda pack_id="", card_type="card", card_id="new_card", frontmatter=None, body="": self._tool_save_card(
                    {"pack_id": pack_id, "card_type": card_type, "card_id": card_id, "frontmatter": frontmatter or {}, "body": body},
                    state,
                ),
            ),
            "batch_save_cards": StructuredTool.from_function(
                name="batch_save_cards",
                description="批量保存卡牌。",
                func=lambda pack_id="", cards=None: self._tool_batch_save_cards(pack_id, cards or [], state),
            ),
            "delete_card": StructuredTool.from_function(
                name="delete_card",
                description="删除指定卡牌文件。",
                func=lambda pack_id="", card_path="": self._tool_delete_card(pack_id, card_path, state),
            ),
            "audit_pack": StructuredTool.from_function(
                name="audit_pack",
                description="审计卡牌包中的重复 ID 和解析错误。",
                func=lambda pack_id="": self._tool_audit_pack(pack_id, state),
            ),
        }

    def _resolve_pack_id(self, raw_pack_id: str, state: Dict[str, Any]) -> str:
        return self._safe_pack_id(str(raw_pack_id or state.get("selected_pack_id", "")))

    def _tool_list_packs(self) -> str:
        packs = self.service.list_packs()
        pack_ids = [str(p.get("pack_id", "")) for p in packs if p.get("pack_id")]
        return f"list_packs -> {len(pack_ids)} packs: {pack_ids}"

    def _tool_create_pack(self, manifest: Dict[str, Any], state: Dict[str, Any]) -> str:
        normalized = self._build_manifest_with_defaults(dict(manifest or {}), state)
        self.service.create_pack(normalized)
        state["selected_pack_id"] = normalized["pack_id"]
        return f'create_pack -> {normalized.get("pack_id", "")}'

    def _tool_select_pack(self, pack_id: str, state: Dict[str, Any]) -> str:
        target_pack = self._safe_pack_id(str(pack_id).strip())
        existing = {p.get("pack_id", "") for p in self.service.list_packs()}
        if target_pack in existing:
            state["selected_pack_id"] = target_pack
            return f"select_pack -> {target_pack}"
        return f"select_pack skipped: pack not found -> {target_pack}"

    def _tool_list_pack_cards(self, pack_id: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        cards = self.service.list_pack_cards(resolved)
        card_paths = []
        try:
            root = self.service._pack_cards_root(resolved)
            card_paths = [str(p.relative_to(root)).replace("\\", "/") for p in cards]
        except Exception:
            card_paths = [p.name for p in cards]
        return f"list_pack_cards({resolved}) -> {len(cards)} cards: {card_paths}"

    def _tool_list_pack_card_types(self, pack_id: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        types = self.service.list_pack_card_types(resolved)
        return f"list_pack_card_types({resolved}) -> {types}"

    def _tool_read_card(self, pack_id: str, card_path: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        root = self.service._pack_cards_root(resolved)
        path = Path(str(card_path).strip())
        target = path if path.is_absolute() else (root / path)
        if not target.exists():
            return f"read_card failed: file not found -> {card_path}"
        if not self.service._is_within(target, root):
            return "read_card failed: card path is outside pack root"
        card = self.service.load_card(target)
        payload = {
            "path": str(target.relative_to(root)).replace("\\", "/"),
            "frontmatter": card.get("frontmatter", {}),
            "body": str(card.get("body", ""))[:2000],
        }
        return f"read_card({resolved}) -> {json.dumps(payload, ensure_ascii=False)}"

    def _tool_save_card(self, args: Dict[str, Any], state: Dict[str, Any]) -> str:
        pack_id = self._resolve_pack_id(str(args.get("pack_id", "")), state)
        card_payload = self._normalize_card_payload(args)
        self.service.save_card(
            pack_id=pack_id,
            card_type=card_payload["card_type"],
            card_id=card_payload["card_id"],
            frontmatter=card_payload["frontmatter"],
            body=card_payload["body"],
        )
        return f"save_card -> {pack_id}/{card_payload['card_type']}/{card_payload['card_id']}"

    def _tool_batch_save_cards(self, pack_id: str, cards: List[Dict[str, Any]], state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        saved = 0
        for card in list(cards):
            self._tool_save_card({"pack_id": resolved, **dict(card)}, state)
            saved += 1
        return f"batch_save_cards -> {resolved}, count={saved}"

    def _tool_delete_card(self, pack_id: str, card_path: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        root = self.service._pack_cards_root(resolved)
        path = Path(str(card_path).strip())
        target = path if path.is_absolute() else (root / path)
        self.service.delete_card(resolved, target)
        return f"delete_card -> {target.name}"

    def _tool_audit_pack(self, pack_id: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        if resolved not in {p.get("pack_id", "") for p in self.service.list_packs()}:
            return f"audit_pack skipped: pack not found -> {resolved}"
        return self._audit_pack(resolved)

    def _audit_pack(self, pack_id: str) -> str:
        cards = self.service.list_pack_cards(pack_id)
        ids: Dict[str, int] = {}
        invalid = 0
        for path in cards:
            try:
                fm = self.service.load_card(path).get("frontmatter", {})
                cid = str(fm.get("id", "")).strip() or path.stem
                ids[cid] = ids.get(cid, 0) + 1
            except Exception:
                invalid += 1
        duplicated = sorted([k for k, v in ids.items() if v > 1])
        return f"audit_pack({pack_id}) -> cards={len(cards)}, duplicated_ids={duplicated}, parse_errors={invalid}"

    def _update_memory(self, history: List[Dict[str, str]]) -> str:
        recent = history[-12:]
        lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent]
        return "\n".join(lines)

    def _parse_json(self, text: str) -> Dict[str, Any] | None:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            try:
                data = json.loads(stripped)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        l = stripped.find("{")
        r = stripped.rfind("}")
        if l != -1 and r != -1 and r > l:
            snippet = stripped[l : r + 1]
            try:
                data = json.loads(snippet)
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
        return None
