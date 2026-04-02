from __future__ import annotations

from pathlib import Path
from typing import Protocol
import shutil
import tempfile
import zipfile

from ..config import SETTINGS
from .zip_utils import ensure_within_directory, safe_extract


class PackStorageProtocol(Protocol):
    """Contract for pack content persistence backends."""

    packs_root: Path

    def get_pack_dir(self, pack_id: str, version: str) -> Path: ...

    def get_pack_cards_root(
        self, pack_id: str, version: str, cards_root: str
    ) -> Path: ...

    def install_pack_from_zip(
        self,
        zip_path: Path,
        pack_id: str,
        version: str,
        cards_root: str,
    ) -> None: ...

    def remove_pack(self, pack_id: str, version: str) -> None: ...

    def export_pack(self, pack_id: str, version: str, output_path: Path) -> None: ...

    def save_card(
        self,
        pack_id: str,
        version: str,
        cards_root: str,
        card_type: str,
        card_id: str,
        frontmatter: dict,
        body: str,
        original_path: Path | None = None,
    ) -> Path: ...

    def update_card(self, path: Path, frontmatter: dict, body: str) -> None: ...

    def delete_card(
        self, pack_id: str, version: str, cards_root: str, path: Path
    ) -> None: ...

    def sync_pack(self, pack_id: str, version: str) -> None: ...


def _resolve_card_type_dir(pack_root: Path, card_type: str) -> str:
    normalized = str(card_type).strip()
    if not normalized:
        return "cards"
    singular = normalized
    plural = "memories" if normalized == "memory" else f"{normalized}s"
    if (pack_root / singular).exists():
        return singular
    if (pack_root / plural).exists():
        return plural
    return plural


class LocalPackStorage:
    """Filesystem-backed pack storage used by the current production path."""

    def __init__(self, packs_root: Path):
        self.packs_root = packs_root
        self.packs_root.mkdir(parents=True, exist_ok=True)

    def get_pack_dir(self, pack_id: str, version: str) -> Path:
        return self.packs_root / pack_id / version

    def get_pack_cards_root(self, pack_id: str, version: str, cards_root: str) -> Path:
        return self.get_pack_dir(pack_id, version) / cards_root

    def install_pack_from_zip(
        self,
        zip_path: Path,
        pack_id: str,
        version: str,
        cards_root: str,
    ) -> None:
        dest_root = self.get_pack_dir(pack_id, version)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            safe_extract(zip_path, td_path)
            root = Path(cards_root)
            if not (td_path / root).exists():
                raise ValueError("cards_root missing in zip")
            dest_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(td_path, dest_root, dirs_exist_ok=True)

    def remove_pack(self, pack_id: str, version: str) -> None:
        pack_dir = self.get_pack_dir(pack_id, version)
        if pack_dir.exists():
            shutil.rmtree(pack_dir)

    def export_pack(self, pack_id: str, version: str, output_path: Path) -> None:
        pack_dir = self.get_pack_dir(pack_id, version)
        if not pack_dir.exists():
            raise ValueError("pack files missing")
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in pack_dir.rglob("*"):
                if path.is_file():
                    if not ensure_within_directory(pack_dir, path):
                        raise ValueError("pack path escaped pack directory")
                    zf.write(path, path.relative_to(pack_dir))

    def save_card(
        self,
        pack_id: str,
        version: str,
        cards_root: str,
        card_type: str,
        card_id: str,
        frontmatter: dict,
        body: str,
        original_path: Path | None = None,
    ) -> Path:
        from .card_editor import render_card
        from .validator import validate_card_frontmatter

        frontmatter = dict(frontmatter)
        frontmatter["id"] = card_id
        frontmatter["type"] = card_type
        validate_card_frontmatter(frontmatter, body)
        pack_root = self.get_pack_cards_root(pack_id, version, cards_root)
        card_dir = pack_root / _resolve_card_type_dir(pack_root, card_type)
        card_dir.mkdir(parents=True, exist_ok=True)
        path = card_dir / f"{card_id}.md"
        path.write_text(render_card(frontmatter, body), encoding="utf-8")
        if original_path:
            old_path = Path(original_path)
            if (
                old_path != path
                and old_path.exists()
                and ensure_within_directory(pack_root, old_path)
            ):
                old_path.unlink()
        return path

    def update_card(self, path: Path, frontmatter: dict, body: str) -> None:
        from .card_editor import render_card
        from .validator import validate_card_frontmatter

        validate_card_frontmatter(frontmatter, body)
        path.write_text(render_card(frontmatter, body), encoding="utf-8")

    def delete_card(
        self, pack_id: str, version: str, cards_root: str, path: Path
    ) -> None:
        pack_root = self.get_pack_cards_root(pack_id, version, cards_root)
        target = Path(path)
        if not target.exists():
            return
        if not ensure_within_directory(pack_root, target):
            raise ValueError("card path is outside pack root")
        target.unlink()

    def sync_pack(self, pack_id: str, version: str) -> None:
        pack_dir = self.get_pack_dir(pack_id, version)
        if not pack_dir.exists():
            raise ValueError("pack files missing")


class OssPackStorage(LocalPackStorage):
    """OSS-backed pack storage with a local cache mirror."""

    def __init__(self, packs_root: Path):
        super().__init__(packs_root)
        if not SETTINGS.oss_endpoint or not SETTINGS.oss_bucket:
            raise ValueError(
                "TEXTRPG_OSS_ENDPOINT and TEXTRPG_OSS_BUCKET are required for OSS pack storage"
            )
        try:
            import oss2  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            raise ValueError("oss2 package is required for OSS pack storage") from exc
        self._oss2 = oss2
        self._bucket = oss2.Bucket(
            oss2.Auth(SETTINGS.oss_access_key_id, SETTINGS.oss_access_key_secret),
            SETTINGS.oss_endpoint,
            SETTINGS.oss_bucket,
        )
        self._prefix = str(SETTINGS.oss_prefix or "textrpg").strip("/")

    def get_pack_dir(self, pack_id: str, version: str) -> Path:
        local = super().get_pack_dir(pack_id, version)
        if not local.exists():
            self._download_pack(pack_id, version, local)
        return local

    def install_pack_from_zip(
        self,
        zip_path: Path,
        pack_id: str,
        version: str,
        cards_root: str,
    ) -> None:
        super().install_pack_from_zip(zip_path, pack_id, version, cards_root)
        self._upload_pack_dir(pack_id, version)

    def remove_pack(self, pack_id: str, version: str) -> None:
        prefix = self._pack_prefix(pack_id, version)
        for obj in self._oss2.ObjectIterator(self._bucket, prefix=prefix):
            self._bucket.delete_object(obj.key)
        super().remove_pack(pack_id, version)

    def export_pack(self, pack_id: str, version: str, output_path: Path) -> None:
        self.get_pack_dir(pack_id, version)
        super().export_pack(pack_id, version, output_path)

    def save_card(
        self,
        pack_id: str,
        version: str,
        cards_root: str,
        card_type: str,
        card_id: str,
        frontmatter: dict,
        body: str,
        original_path: Path | None = None,
    ) -> Path:
        path = super().save_card(
            pack_id,
            version,
            cards_root,
            card_type,
            card_id,
            frontmatter,
            body,
            original_path=original_path,
        )
        self._upload_file(path, pack_id, version)
        if original_path:
            self._delete_remote_path(original_path, pack_id, version)
        return path

    def update_card(self, path: Path, frontmatter: dict, body: str) -> None:
        super().update_card(path, frontmatter, body)
        pack_id, version = self._resolve_pack_from_path(path)
        self._upload_file(path, pack_id, version)

    def delete_card(
        self, pack_id: str, version: str, cards_root: str, path: Path
    ) -> None:
        super().delete_card(pack_id, version, cards_root, path)
        self._delete_remote_path(path, pack_id, version)

    def sync_pack(self, pack_id: str, version: str) -> None:
        pack_dir = super().get_pack_dir(pack_id, version)
        if not pack_dir.exists():
            raise ValueError("pack files missing")
        self._upload_pack_dir(pack_id, version)

    def _pack_prefix(self, pack_id: str, version: str) -> str:
        return f"{self._prefix}/packs/{pack_id}/{version}"

    def _object_key(self, pack_id: str, version: str, relative_path: Path) -> str:
        relative = str(relative_path).replace("\\", "/").lstrip("/")
        return f"{self._pack_prefix(pack_id, version)}/{relative}"

    def _upload_pack_dir(self, pack_id: str, version: str) -> None:
        pack_dir = super().get_pack_dir(pack_id, version)
        if not pack_dir.exists():
            return
        for path in pack_dir.rglob("*"):
            if path.is_file():
                self._upload_file(path, pack_id, version)

    def _upload_file(self, path: Path, pack_id: str, version: str) -> None:
        pack_dir = super().get_pack_dir(pack_id, version)
        relative = path.relative_to(pack_dir)
        self._bucket.put_object_from_file(
            self._object_key(pack_id, version, relative), str(path)
        )

    def _download_pack(self, pack_id: str, version: str, dest_root: Path) -> None:
        prefix = self._pack_prefix(pack_id, version)
        found = False
        for obj in self._oss2.ObjectIterator(self._bucket, prefix=prefix):
            found = True
            relative = obj.key[len(prefix) :].lstrip("/")
            if not relative:
                continue
            target = dest_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            self._bucket.get_object_to_file(obj.key, str(target))
        if found:
            dest_root.mkdir(parents=True, exist_ok=True)

    def _delete_remote_path(self, path: Path, pack_id: str, version: str) -> None:
        pack_dir = super().get_pack_dir(pack_id, version)
        target = Path(path)
        if not ensure_within_directory(pack_dir, target):
            return
        relative = target.relative_to(pack_dir)
        self._bucket.delete_object(self._object_key(pack_id, version, relative))

    def _resolve_pack_from_path(self, path: Path) -> tuple[str, str]:
        try:
            relative = path.resolve(strict=False).relative_to(
                self.packs_root.resolve(strict=False)
            )
        except Exception as exc:
            raise ValueError("card path is outside pack storage root") from exc
        parts = relative.parts
        if len(parts) < 2:
            raise ValueError("card path is too short")
        return parts[0], parts[1]
