from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = PROJECT_ROOT / 'game' / 'cards'
PACKS_DIR = PROJECT_ROOT / 'game' / 'cards_packs'
PACK_REGISTRY_PATH = PACKS_DIR / 'pack_registry.json'
ENGINE_VERSION = '0.1.0'

DATA_DIR = PROJECT_ROOT / 'data' / 'saves' / 'slot_001'
SNAPSHOT_DIR = DATA_DIR / 'state_snapshot'
RAG_DIR = DATA_DIR / 'rag'
KG_DB_PATH = DATA_DIR / 'kg.sqlite'
WORLD_DB_PATH = DATA_DIR / 'world.sqlite'

def get_slot_paths(save_slot: str) -> dict[str, Path]:
    """返回指定存档槽位的持久化路径。"""
    data_dir = PROJECT_ROOT / 'data' / 'saves' / save_slot
    return {
        'data_dir': data_dir,
        'snapshot_dir': data_dir / 'state_snapshot',
        'rag_dir': data_dir / 'rag',
        'kg_db_path': data_dir / 'kg.sqlite',
        'world_db_path': data_dir / 'world.sqlite',
        'chat_history_path': data_dir / 'chat_history.json',
    }

@dataclass(frozen=True)
class Settings:
    """从环境变量派生的运行时配置。"""
    model_name: str = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    embedding_model: str = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    base_url: str = os.getenv('OPENAI_BASE_URL', '')
    top_k_cards: int = 6
    top_k_memories: int = 4
    max_recent_messages: int = 6
    use_mock_llm: bool = os.getenv('OPENAI_API_KEY') is None
    force_fake_embeddings: bool = os.getenv('USE_FAKE_EMBEDDINGS', '').lower() in ('1', 'true', 'yes') or 'deepseek' in os.getenv('OPENAI_BASE_URL', '').lower()

SETTINGS = Settings()
