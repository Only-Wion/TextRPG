from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from game.config import SETTINGS
from game.infrastructure.postgres.auth_repository import PostgresAuthRepository


def _get_repository() -> PostgresAuthRepository:
    if SETTINGS.storage_backend != "postgres":
        raise RuntimeError("PostgreSQL-only mode requires TEXTRPG_STORAGE_BACKEND=postgres")
    if not SETTINGS.postgres_dsn:
        raise RuntimeError("TEXTRPG_POSTGRES_DSN is required")
    return PostgresAuthRepository(SETTINGS.postgres_dsn)


def _plan_editor(repo: PostgresAuthRepository) -> None:
    st.subheader("模型方案管理")

    plans = repo.list_all_llm_plans()
    plan_map = {str(item.get("plan_id")): item for item in plans}
    editing_plan_id = str(st.session_state.get("editing_plan_id") or "").strip()
    editing = plan_map.get(editing_plan_id)

    active_count = sum(1 for item in plans if item.get("is_active"))
    st.caption(f"当前启用方案数: {active_count} | 总方案数: {len(plans)}")

    if plans:
        st.markdown("### 方案列表")
        for item in plans:
            current_id = str(item.get("plan_id") or "")
            is_active = bool(item.get("is_active"))
            with st.container(border=True):
                title_col, action_col = st.columns([4, 2])
                with title_col:
                    status_text = "启用" if is_active else "停用"
                    st.markdown(f"**{item.get('name') or current_id}** · {status_text}")
                    st.caption(
                        f"plan_id: {current_id} | provider: {item.get('provider')} | model: {item.get('model_name')}"
                    )
                    st.write(item.get("description") or "")
                    st.caption(
                        f"输入token/币: {item.get('input_tokens_per_coin')} | 输出token/币: {item.get('output_tokens_per_coin')} | 排序: {item.get('display_order')}"
                    )
                with action_col:
                    if st.button("编辑", key=f"edit_plan_{current_id}", use_container_width=True):
                        st.session_state["editing_plan_id"] = current_id
                        st.rerun()
                    toggle_label = "停用" if is_active else "启用"
                    if st.button(
                        toggle_label,
                        key=f"toggle_plan_{current_id}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        repo.admin_set_llm_plan_active(current_id, not is_active)
                        st.success(f"已{toggle_label}方案: {current_id}")
                        st.rerun()
    else:
        st.info("暂无方案，请先创建。")

    st.markdown("### 方案编辑")
    if editing:
        st.info(f"正在编辑: {editing_plan_id}")
    else:
        st.caption("未选择编辑项，当前为新增模式。")

    with st.form("plan_form"):
        plan_id = st.text_input(
            "plan_id",
            value=str((editing or {}).get("plan_id") or ""),
            disabled=bool(editing),
        ).strip()
        name = st.text_input("名称", value=str((editing or {}).get("name") or "")).strip()
        description = st.text_input("描述", value=str((editing or {}).get("description") or "")).strip()
        provider = (
            st.text_input("provider", value=str((editing or {}).get("provider") or "custom")).strip()
            or "custom"
        )
        model_name = st.text_input("model_name", value=str((editing or {}).get("model_name") or "")).strip()
        embedding_model = st.text_input(
            "embedding_model",
            value=str((editing or {}).get("embedding_model") or "text-embedding-3-small"),
        ).strip()
        base_url = st.text_input("base_url", value=str((editing or {}).get("base_url") or "")).strip()
        server_api_key_encrypted = st.text_input("服务器API Key", value="", type="password")
        input_tokens_per_coin = st.number_input(
            "输入 token / 1代币",
            min_value=1,
            value=int((editing or {}).get("input_tokens_per_coin") or 1200),
            step=1,
        )
        output_tokens_per_coin = st.number_input(
            "输出 token / 1代币",
            min_value=1,
            value=int((editing or {}).get("output_tokens_per_coin") or 800),
            step=1,
        )
        display_order = st.number_input(
            "排序",
            min_value=0,
            value=int((editing or {}).get("display_order") or 0),
            step=1,
        )
        is_active = st.checkbox("启用", value=bool((editing or {}).get("is_active", True)))
        save_col, cancel_col = st.columns(2)
        with save_col:
            submitted = st.form_submit_button("保存方案", use_container_width=True)
        with cancel_col:
            cancel_edit = st.form_submit_button("取消编辑", use_container_width=True)

    if cancel_edit:
        st.session_state["editing_plan_id"] = ""
        st.rerun()

    if submitted:
        repo.admin_upsert_llm_plan(
            {
                "plan_id": plan_id,
                "name": name,
                "description": description,
                "provider": provider,
                "model_name": model_name,
                "embedding_model": embedding_model,
                "base_url": base_url,
                "server_api_key_encrypted": server_api_key_encrypted,
                "input_tokens_per_coin": int(input_tokens_per_coin),
                "output_tokens_per_coin": int(output_tokens_per_coin),
                "display_order": int(display_order),
                "is_active": bool(is_active),
            }
        )
        st.success(f"模型方案已保存: {plan_id}")
        st.session_state["editing_plan_id"] = ""
        st.rerun()


def _redeem_key_editor(repo: PostgresAuthRepository) -> None:
    st.subheader("兑换密钥批次")

    with st.form("key_form"):
        tier_cny = st.selectbox("档位(元)", options=[1, 6, 18, 30], index=0)
        coins_granted = st.number_input("每个密钥发放代币", min_value=0.1, value=100.0, step=10.0)
        count = st.number_input("生成数量", min_value=1, max_value=5000, value=20, step=1)
        batch_id = st.text_input("批次号", value=f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}").strip()
        export_dir = st.text_input("导出目录", value=str((Path.cwd() / "data" / "exports").resolve())).strip()
        submitted = st.form_submit_button("生成并导出")

    if submitted:
        keys = repo.admin_generate_redeem_keys(
            tier_cny=int(tier_cny),
            coins_granted=float(coins_granted),
            count=int(count),
            batch_id=batch_id,
        )
        out_dir = Path(export_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"redeem-keys-{batch_id}.txt"
        out_file.write_text("\n".join(keys), encoding="utf-8")
        st.success(f"已生成 {len(keys)} 个密钥，并导出到: {out_file}")

    status = st.selectbox("筛选状态", options=["all", "unused", "redeemed", "revoked"], index=0)
    rows = repo.admin_list_redeem_keys(status=None if status == "all" else status, limit=200)
    st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="TextRPG Admin Billing Console", layout="wide")
    st.title("TextRPG 本地管理员控制台")
    st.caption("仅本地使用，不纳入网站。用于管理模型方案与兑换密钥池。")

    st.warning("历史 Streamlit 页面已弃用；此脚本是唯一保留的本地管理入口。")

    try:
        repo = _get_repository()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    tab_plan, tab_keys = st.tabs(["模型方案", "兑换密钥"])
    with tab_plan:
        _plan_editor(repo)
    with tab_keys:
        _redeem_key_editor(repo)


if __name__ == "__main__":
    main()
