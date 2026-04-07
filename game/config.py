from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = PROJECT_ROOT / "game" / "cards"
PACKS_DIR = PROJECT_ROOT / "game" / "cards_packs"
PACK_REGISTRY_PATH = PACKS_DIR / "pack_registry.json"
USER_PACKS_DIR = PROJECT_ROOT / "data" / "user_packs"
ENGINE_VERSION = "0.1.0"

DATA_DIR = PROJECT_ROOT / "data" / "saves" / "slot_001"
SAVES_DIR = PROJECT_ROOT / "data" / "saves"
ARCHIVES_DIR = PROJECT_ROOT / "data" / "archives"
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"
APP_DB_PATH = PROJECT_ROOT / "data" / "app.sqlite3"
SNAPSHOT_DIR = DATA_DIR / "state_snapshot"
RAG_DIR = DATA_DIR / "rag"
KG_DB_PATH = DATA_DIR / "kg.sqlite"
WORLD_DB_PATH = DATA_DIR / "world.sqlite"


def get_slot_paths(save_slot: str) -> dict[str, Path]:
    """返回指定存档槽位的持久化路径。"""
    data_dir = SAVES_DIR / save_slot
    return {
        "data_dir": data_dir,
        "snapshot_dir": data_dir / "state_snapshot",
        "rag_dir": data_dir / "rag",
        "kg_db_path": data_dir / "kg.sqlite",
        "world_db_path": data_dir / "world.sqlite",
        "chat_history_path": data_dir / "chat_history.json",
        "ui_panels_path": data_dir / "ui_panels.json",
        "session_meta_path": data_dir / "session_meta.json",
    }


@dataclass(frozen=True)
class Settings:
    """从环境变量派生的运行时配置。"""

    model_name: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    base_url: str = os.getenv("OPENAI_BASE_URL", "")
    storage_backend: str = os.getenv("TEXTRPG_STORAGE_BACKEND", "postgres")
    postgres_dsn: str = os.getenv("TEXTRPG_POSTGRES_DSN", "")
    pack_storage_backend: str = os.getenv("TEXTRPG_PACK_STORAGE_BACKEND", "local")
    oss_endpoint: str = os.getenv("TEXTRPG_OSS_ENDPOINT", "")
    oss_bucket: str = os.getenv("TEXTRPG_OSS_BUCKET", "")
    oss_access_key_id: str = os.getenv("TEXTRPG_OSS_ACCESS_KEY_ID", "")
    oss_access_key_secret: str = os.getenv("TEXTRPG_OSS_ACCESS_KEY_SECRET", "")
    oss_prefix: str = os.getenv("TEXTRPG_OSS_PREFIX", "textrpg")
    oss_region: str = os.getenv("TEXTRPG_OSS_REGION", "")
    ops_every_n_turns: int = int(os.getenv("TEXTRPG_OPS_EVERY_N_TURNS", "3"))
    top_k_cards: int = 6
    top_k_memories: int = 4
    max_recent_messages: int = 6
    use_mock_llm: bool = os.getenv("OPENAI_API_KEY") is None
    force_fake_embeddings: bool = (
        os.getenv("USE_FAKE_EMBEDDINGS", "").lower() in ("1", "true", "yes")
        or "deepseek" in os.getenv("OPENAI_BASE_URL", "").lower()
    )


SETTINGS = Settings()

LLM_SETTINGS_PATH = PROJECT_ROOT / "data" / "llm_settings.json"


@dataclass
class LLMSettings:
    """可持久化的 LLM 运行时配置。"""

    provider: str = "custom"
    model_name: str = SETTINGS.model_name
    embedding_model: str = SETTINGS.embedding_model
    base_url: str = SETTINGS.base_url
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    use_mock_llm: bool = SETTINGS.use_mock_llm
    force_fake_embeddings: bool = SETTINGS.force_fake_embeddings

    def to_public_dict(self) -> Dict[str, Any]:
        """返回可用于 UI 展示的配置（隐藏密钥）。"""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "embedding_model": self.embedding_model,
            "base_url": self.base_url,
            "api_key_set": bool(self.api_key),
            "use_mock_llm": self.use_mock_llm,
            "force_fake_embeddings": self.force_fake_embeddings,
        }


RUNTIME_LLM_SETTINGS = LLMSettings()
ACTIVE_LLM_SETTINGS_OVERRIDE: ContextVar[LLMSettings | None] = ContextVar(
    "ACTIVE_LLM_SETTINGS_OVERRIDE",
    default=None,
)


def normalize_llm_settings(
    payload: Dict[str, Any], current: LLMSettings | None = None
) -> LLMSettings:
    """清洗外部输入并映射成内部结构。"""
    current = current or LLMSettings()
    api_key_value = str(payload.get("api_key", "")).strip()
    return LLMSettings(
        provider=str(payload.get("provider", "custom")),
        model_name=str(payload.get("model_name", SETTINGS.model_name)).strip()
        or SETTINGS.model_name,
        embedding_model=str(
            payload.get("embedding_model", SETTINGS.embedding_model)
        ).strip()
        or SETTINGS.embedding_model,
        base_url=str(payload.get("base_url", "")).strip(),
        api_key=api_key_value or current.api_key,
        use_mock_llm=bool(payload.get("use_mock_llm", current.use_mock_llm)),
        force_fake_embeddings=bool(
            payload.get("force_fake_embeddings", current.force_fake_embeddings)
        ),
    )


@contextmanager
def activate_runtime_llm_settings(settings: LLMSettings):
    token = ACTIVE_LLM_SETTINGS_OVERRIDE.set(settings)
    try:
        yield
    finally:
        try:
            ACTIVE_LLM_SETTINGS_OVERRIDE.reset(token)
        except ValueError:
            # In streaming/request context switches, token reset may happen on a different context.
            # Ignore this cleanup error to avoid surfacing it to users.
            pass


def load_runtime_llm_settings() -> LLMSettings:
    """从磁盘加载 LLM 设置，并同步全局运行时配置。"""
    global RUNTIME_LLM_SETTINGS
    override = ACTIVE_LLM_SETTINGS_OVERRIDE.get()
    if override is not None:
        return override
    if LLM_SETTINGS_PATH.exists():
        try:
            payload = json.loads(LLM_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                RUNTIME_LLM_SETTINGS = normalize_llm_settings(
                    payload, RUNTIME_LLM_SETTINGS
                )
                return RUNTIME_LLM_SETTINGS
        except Exception:
            pass
    RUNTIME_LLM_SETTINGS = LLMSettings()
    return RUNTIME_LLM_SETTINGS


def save_runtime_llm_settings(payload: Dict[str, Any]) -> LLMSettings:
    """保存并激活新的 LLM 运行时配置。"""
    global RUNTIME_LLM_SETTINGS
    settings = normalize_llm_settings(payload, RUNTIME_LLM_SETTINGS)
    LLM_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LLM_SETTINGS_PATH.write_text(
        json.dumps(settings.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    RUNTIME_LLM_SETTINGS = settings
    return settings


# 启动时自动加载一次，确保运行期行为和磁盘配置一致。
load_runtime_llm_settings()
