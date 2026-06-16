from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile

import requests
import yaml

from ..config import ENGINE_VERSION, PACKS_DIR, PACK_REGISTRY_PATH, SETTINGS
from ..core.card_repository import CardSourceDocument, CanvasStateDocument
from .card_editor import parse_card
from .registry import PackRecord, PackRegistry
from .storage import OssPackStorage, PackStorageProtocol
from .validator import PACK_ID_RE, SEMVER_RE, validate_manifest

MAX_ZIP_BYTES = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


class PackManager:
    """在磁盘上安装、移除并管理卡包。"""

    def __init__(
        self,
        packs_root: Path = PACKS_DIR,
        registry_path: Path = PACK_REGISTRY_PATH,
        storage: PackStorageProtocol | None = None,
        user_namespace: str | None = None,
    ):
        if storage is not None:
            self.storage = storage
        else:
            if SETTINGS.pack_storage_backend != "oss":
                raise ValueError(
                    "Pack storage is OSS-only. Set TEXTRPG_PACK_STORAGE_BACKEND=oss"
                )
            self.storage = OssPackStorage(packs_root, user_namespace=user_namespace)
        self.packs_root = self.storage.packs_root
        self.registry = PackRegistry(registry_path)

    def list_packs(self) -> List[PackRecord]:
        """从注册表返回卡包记录。"""
        return self.registry.list()

    def install_pack_from_url(self, url: str) -> PackRecord:
        """从 URL 下载并安装卡包 zip。"""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "pack.zip"
            self._download(url, tmp)
            return self.install_pack_from_zip(tmp, source=url)

    def install_pack_from_zip(
        self, zip_path: Path, source: str | None = None
    ) -> PackRecord:
        """从 zip 文件安装卡包。"""
        if zip_path.stat().st_size > MAX_ZIP_BYTES:
            raise ValueError("zip too large")
        manifest = self._read_manifest_from_zip(zip_path)
        manifest = {
            **manifest,
            "cards_root": str(manifest.get("cards_root") or "cards"),
        }
        validate_manifest(manifest)
        self._validate_requires(manifest)
        pack_id = str(manifest["pack_id"])
        version = str(manifest["version"])
        if not PACK_ID_RE.match(pack_id) or not SEMVER_RE.match(version):
            raise ValueError("invalid pack_id or version")
        if "sha256" in manifest:
            digest = self._sha256(zip_path)
            if digest != str(manifest["sha256"]):
                raise ValueError("sha256 mismatch")

        dest_root = self.storage.get_pack_dir(pack_id, version)
        if dest_root.exists():
            raise ValueError("pack version already installed")
        self.storage.install_pack_from_zip(
            zip_path,
            pack_id,
            version,
            str(manifest["cards_root"]),
        )

        record = PackRecord(
            pack_id=pack_id,
            name=str(manifest["name"]),
            version=version,
            author=str(manifest["author"]),
            description=str(manifest["description"]),
            cards_root=str(manifest["cards_root"]),
            enabled=False,
            source=source or str(zip_path),
        )
        self.registry.upsert(record)
        return record

    def remove_pack(self, pack_id: str) -> None:
        """移除卡包文件与注册表条目。"""
        record = self.registry.get(pack_id)
        if not record:
            return
        self.storage.remove_pack(pack_id, record.version)
        self.registry.remove(pack_id)

    def enable_pack(self, pack_id: str, enabled: bool = True) -> None:
        """在注册表中启用或禁用卡包。"""
        self.registry.set_enabled(pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        """将卡包目录打包为 zip 文件。"""
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        self.storage.export_pack(pack_id, record.version, output_path)

    def get_enabled_cards_roots(self) -> List[Path]:
        """返回所有已启用卡包的 cards 根目录。"""
        roots: List[Path] = []
        for record in self.registry.list():
            if not record.enabled:
                continue
            root = self.storage.get_pack_cards_root(
                record.pack_id, record.version, record.cards_root
            )
            if root.exists():
                roots.append(root)
        return roots

    def list_enabled_card_documents(self) -> List[CardSourceDocument]:
        documents: List[CardSourceDocument] = []
        for record in self.registry.list():
            if not record.enabled:
                continue
            if isinstance(self.storage, OssPackStorage):
                paths = self.storage.list_card_paths(
                    record.pack_id, record.version, record.cards_root
                )
                logger.warning(
                    "oss-cards enabled pack=%s version=%s cards_root=%s object_cards=%d",
                    record.pack_id,
                    record.version,
                    record.cards_root,
                    len(paths),
                )
                for path in paths:
                    documents.append(
                        CardSourceDocument(
                            path=path,
                            text=self.storage.read_card_text(path),
                        )
                    )
                continue

            root = self.storage.get_pack_cards_root(
                record.pack_id, record.version, record.cards_root
            )
            paths = list(root.rglob("*.md"))
            logger.warning(
                "local-cards enabled pack=%s version=%s cards_root=%s file_cards=%d",
                record.pack_id,
                record.version,
                record.cards_root,
                len(paths),
            )
            for path in paths:
                documents.append(
                    CardSourceDocument(
                        path=path,
                        text=path.read_text(encoding="utf-8"),
                    )
                )
        return documents

    def list_enabled_canvas_state_documents(self) -> List[CanvasStateDocument]:
        documents: List[CanvasStateDocument] = []
        for record in self.registry.list():
            if not record.enabled:
                continue
            payload = self.storage.read_pack_json(
                record.pack_id,
                record.version,
                "canvas_state.json",
                default=None,
            )
            logger.warning(
                "oss-canvas enabled pack=%s version=%s found=%s",
                record.pack_id,
                record.version,
                isinstance(payload, dict),
            )
            if isinstance(payload, dict):
                documents.append(CanvasStateDocument(payload=payload))
        return documents

    def get_pack_dir(self, pack_id: str, version: str | None = None) -> Path:
        """返回指定卡包的版本目录。"""
        record = self.registry.get(pack_id)
        resolved_version = version or (record.version if record else "")
        if not resolved_version:
            raise ValueError("pack not found")
        return self.storage.get_pack_dir(pack_id, resolved_version)

    def get_pack_cards_root(self, pack_id: str) -> Path:
        """返回指定卡包当前版本的 cards 根目录。"""
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        return self.storage.get_pack_cards_root(
            pack_id, record.version, record.cards_root
        )

    def create_pack(self, manifest: Dict[str, Any]) -> PackRecord:
        normalized_manifest = dict(manifest)
        normalized_manifest["cards_root"] = str(
            normalized_manifest.get("cards_root") or "cards"
        )
        validate_manifest(normalized_manifest)
        pack_id = str(normalized_manifest["pack_id"])
        version = str(normalized_manifest["version"])
        if self.registry.get(pack_id):
            raise ValueError("pack already exists")

        if isinstance(self.storage, OssPackStorage):
            self.storage.create_pack_manifest(
                pack_id,
                version,
                str(normalized_manifest["cards_root"]),
                normalized_manifest,
            )
        else:
            pack_dir = self.packs_root / pack_id / version
            if pack_dir.exists():
                raise ValueError("pack already exists")
            cards_root = Path(str(normalized_manifest["cards_root"]))
            pack_dir.mkdir(parents=True, exist_ok=True)
            (pack_dir / cards_root).mkdir(parents=True, exist_ok=True)
            (pack_dir / "pack.json").write_text(
                json.dumps(normalized_manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        record = PackRecord(
            pack_id=pack_id,
            name=str(normalized_manifest["name"]),
            version=version,
            author=str(normalized_manifest["author"]),
            description=str(normalized_manifest["description"]),
            cards_root=str(normalized_manifest["cards_root"]),
            enabled=False,
            source="local",
        )
        self.registry.upsert(record)
        return record

    def create_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
    ) -> Path:
        return self.save_card(
            pack_id,
            card_type,
            card_id,
            frontmatter,
            body,
            folder_path=None,
        )

    def save_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
        folder_path: str | None = None,
        original_path: Path | None = None,
    ) -> Path:
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        return self.storage.save_card(
            pack_id,
            record.version,
            record.cards_root,
            card_type,
            card_id,
            folder_path,
            frontmatter,
            body,
            original_path=original_path,
        )

    def update_card(self, path: Path, frontmatter: Dict[str, Any], body: str) -> None:
        self.storage.update_card(path, frontmatter, body)

    def delete_card(self, pack_id: str, path: Path) -> None:
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        self.storage.delete_card(pack_id, record.version, record.cards_root, path)

    def list_pack_cards(self, pack_id: str) -> List[Path]:
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        if isinstance(self.storage, OssPackStorage):
            return self.storage.list_card_paths(
                pack_id, record.version, record.cards_root
            )
        root = self.storage.get_pack_cards_root(
            pack_id, record.version, record.cards_root
        )
        return list(root.rglob("*.md"))

    def load_card(self, pack_id: str, path: Path) -> Dict[str, Any]:
        if isinstance(self.storage, OssPackStorage):
            text = self.storage.read_card_text(path)
            return self._parse_card_text(text)
        fm, body = parse_card(path)
        return {"frontmatter": fm, "body": body}

    def card_exists(self, pack_id: str, path: Path) -> bool:
        record = self.registry.get(pack_id)
        if not record:
            return False
        if isinstance(self.storage, OssPackStorage):
            return self.storage.card_exists(path)
        return Path(path).exists()

    def sync_pack_content(self, pack_id: str) -> None:
        """同步指定卡包内容到当前存储后端。"""
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        self.storage.sync_pack(pack_id, record.version)

    def read_pack_json(
        self,
        pack_id: str,
        relative_path: str | Path,
        default: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        return self.storage.read_pack_json(
            pack_id, record.version, relative_path, default
        )

    def write_pack_json(
        self,
        pack_id: str,
        relative_path: str | Path,
        payload: dict[str, Any] | list[Any],
    ) -> None:
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        self.storage.write_pack_json(pack_id, record.version, relative_path, payload)

    def _download(self, url: str, dest: Path) -> None:
        """流式下载 zip，并限制大小。"""
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = 0
            with dest.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_ZIP_BYTES:
                        raise ValueError("zip too large")
                    f.write(chunk)

    def _read_manifest_from_zip(self, zip_path: Path) -> Dict[str, Any]:
        """从 zip 中提取并解析 pack manifest。"""
        with zipfile.ZipFile(zip_path) as zf:
            manifest_name = None
            for name in zf.namelist():
                if (
                    name.lower().endswith("pack.json")
                    or name.lower().endswith("pack.yaml")
                    or name.lower().endswith("pack.yml")
                ):
                    manifest_name = name
                    break
            if not manifest_name:
                raise ValueError("manifest not found in zip")
            raw = zf.read(manifest_name).decode("utf-8")
            if manifest_name.lower().endswith((".yaml", ".yml")):
                data = yaml.safe_load(raw)
            else:
                data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("manifest invalid")
            return data

    def _sha256(self, path: Path) -> str:
        """计算文件的 sha256。"""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _validate_requires(self, manifest: Dict[str, Any]) -> None:
        """校验卡包对引擎版本的要求。"""
        requires = manifest.get("requires")
        if not requires:
            return
        if isinstance(requires, str) and requires > ENGINE_VERSION:
            raise ValueError("engine version too low for this pack")

    def _parse_card_text(self, text: str) -> Dict[str, Any]:
        raw = text or ""
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            if not isinstance(fm, dict):
                fm = {}
            return {"frontmatter": fm, "body": body}
        return {"frontmatter": {}, "body": raw}
