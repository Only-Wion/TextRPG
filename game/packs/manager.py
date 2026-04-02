from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile

import requests
import yaml

from ..config import ENGINE_VERSION, PACKS_DIR, PACK_REGISTRY_PATH, SETTINGS
from .registry import PackRecord, PackRegistry
from .storage import LocalPackStorage, OssPackStorage, PackStorageProtocol
from .validator import PACK_ID_RE, SEMVER_RE, validate_manifest

MAX_ZIP_BYTES = 50 * 1024 * 1024


class PackManager:
    """在磁盘上安装、移除并管理卡包。"""

    def __init__(
        self,
        packs_root: Path = PACKS_DIR,
        registry_path: Path = PACK_REGISTRY_PATH,
        storage: PackStorageProtocol | None = None,
    ):
        if storage is not None:
            self.storage = storage
        elif SETTINGS.pack_storage_backend == "oss":
            self.storage = OssPackStorage(packs_root)
        else:
            self.storage = LocalPackStorage(packs_root)
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

    def create_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
    ) -> Path:
        return self.save_card(pack_id, card_type, card_id, frontmatter, body)

    def save_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
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

    def sync_pack_content(self, pack_id: str) -> None:
        """同步指定卡包内容到当前存储后端。"""
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        self.storage.sync_pack(pack_id, record.version)

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
