from __future__ import annotations

from pathlib import Path
from typing import List, Dict
import time

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from ..config import RAG_DIR
from ..llm import get_embeddings

class RAGStore:
    """语义记忆检索的向量库封装。"""
    def __init__(self, persist_dir: Path = RAG_DIR):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.vs = Chroma(
            collection_name='memories',
            persist_directory=str(self.persist_dir),
            embedding_function=get_embeddings(),
        )

    def add_memory(self, text: str, tags: List[str]) -> None:
        """写入一条带基础元数据的记忆片段。"""
        metadata = {
            'tags': ','.join(tags),
            'ts': int(time.time()),
        }
        self.vs.add_documents([Document(page_content=text, metadata=metadata)])
        self.vs.persist()

    def search(self, query: str, k: int) -> List[Dict[str, str]]:
        """按相似度检索 top-k 记忆。"""
        if not query.strip():
            return []
        docs = self.vs.similarity_search(query, k=k)
        return [{'text': d.page_content, 'metadata': d.metadata} for d in docs]
