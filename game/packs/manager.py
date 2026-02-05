from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile

import requests
import yaml

from ..config import ENGINE_VERSION, PACKS_DIR, PACK_REGISTRY_PATH
from .registry import PackRecord, PackRegistry
from .validator import PACK_ID_RE, SEMVER_RE, validate_manifest
from .zip_utils import safe_extract

MAX_ZIP_BYTES = 50 * 1024 * 1024


class PackManager:
    """在磁盘上安装、移除并管理卡包。"""
    def __init__(self, packs_root: Path = PACKS_DIR, registry_path: Path = PACK_REGISTRY_PATH):
        self.packs_root = packs_root
        self.registry = PackRegistry(registry_path)
        self.packs_root.mkdir(parents=True, exist_ok=True)

    def list_packs(self) -> List[PackRecord]:
        """从注册表返回卡包记录。"""
        return self.registry.list()

    def install_pack_from_url(self, url: str) -> PackRecord:
        """从 URL 下载并安装卡包 zip。"""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / 'pack.zip'
            self._download(url, tmp)
            return self.install_pack_from_zip(tmp, source=url)

    def install_pack_from_zip(self, zip_path: Path, source: str | None = None) -> PackRecord:
        """从 zip 文件安装卡包。"""
        if zip_path.stat().st_size > MAX_ZIP_BYTES:
            raise ValueError('zip too large')
        manifest = self._read_manifest_from_zip(zip_path)
        validate_manifest(manifest)
        self._validate_requires(manifest)
        pack_id = str(manifest['pack_id'])
        version = str(manifest['version'])
        if not PACK_ID_RE.match(pack_id) or not SEMVER_RE.match(version):
            raise ValueError('invalid pack_id or version')
        if 'sha256' in manifest:
            digest = self._sha256(zip_path)
            if digest != str(manifest['sha256']):
                raise ValueError('sha256 mismatch')

        dest_root = self.packs_root / pack_id / version
        if dest_root.exists():
            raise ValueError('pack version already installed')
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            safe_extract(zip_path, td_path)
            cards_root = Path(str(manifest['cards_root']))
            if not (td_path / cards_root).exists():
                raise ValueError('cards_root missing in zip')
            dest_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(td_path, dest_root, dirs_exist_ok=True)

        record = PackRecord(
            pack_id=pack_id,
            name=str(manifest['name']),
            version=version,
            author=str(manifest['author']),
            description=str(manifest['description']),
            cards_root=str(manifest['cards_root']),
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
        pack_dir = self.packs_root / pack_id / record.version
        if pack_dir.exists():
            shutil.rmtree(pack_dir)
        self.registry.remove(pack_id)

    def enable_pack(self, pack_id: str, enabled: bool = True) -> None:
        """在注册表中启用或禁用卡包。"""
        self.registry.set_enabled(pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        """将卡包目录打包为 zip 文件。"""
        record = self.registry.get(pack_id)
        if not record:
            raise ValueError('pack not found')
        pack_dir = self.packs_root / pack_id / record.version
        if not pack_dir.exists():
            raise ValueError('pack files missing')
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for path in pack_dir.rglob('*'):
                if path.is_file():
                    zf.write(path, path.relative_to(pack_dir))

    def get_enabled_cards_roots(self) -> List[Path]:
        """返回所有已启用卡包的 cards 根目录。"""
        roots: List[Path] = []
        for record in self.registry.list():
            if not record.enabled:
                continue
            pack_dir = self.packs_root / record.pack_id / record.version
            root = pack_dir / record.cards_root
            if root.exists():
                roots.append(root)
        return roots

    def _download(self, url: str, dest: Path) -> None:
        """流式下载 zip，并限制大小。"""
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = 0
            with dest.open('wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_ZIP_BYTES:
                        raise ValueError('zip too large')
                    f.write(chunk)

    def _read_manifest_from_zip(self, zip_path: Path) -> Dict[str, Any]:
        """从 zip 中提取并解析 pack manifest。"""
        with zipfile.ZipFile(zip_path) as zf:
            manifest_name = None
            for name in zf.namelist():
                if name.lower().endswith('pack.json') or name.lower().endswith('pack.yaml') or name.lower().endswith('pack.yml'):
                    manifest_name = name
                    break
            if not manifest_name:
                raise ValueError('manifest not found in zip')
            raw = zf.read(manifest_name).decode('utf-8')
            if manifest_name.lower().endswith(('.yaml', '.yml')):
                data = yaml.safe_load(raw)
            else:
                data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('manifest invalid')
            return data

    def _sha256(self, path: Path) -> str:
        """计算文件的 sha256。"""
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    def _validate_requires(self, manifest: Dict[str, Any]) -> None:
        """校验卡包对引擎版本的要求。"""
        requires = manifest.get('requires')
        if not requires:
            return
        if isinstance(requires, str) and requires > ENGINE_VERSION:
            raise ValueError('engine version too low for this pack')
