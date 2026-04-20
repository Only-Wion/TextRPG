from __future__ import annotations

from pathlib import Path
from typing import Protocol
import shutil
import tempfile
import zipfile
import json

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
        folder_path: str | None,
        frontmatter: dict,
        body: str,
        original_path: Path | None = None,
    ) -> Path: ...

    def update_card(self, path: Path, frontmatter: dict, body: str) -> None: ...

    def delete_card(
        self, pack_id: str, version: str, cards_root: str, path: Path
    ) -> None: ...

    def sync_pack(self, pack_id: str, version: str) -> None: ...

    def read_pack_json(
        self,
        pack_id: str,
        version: str,
        relative_path: str | Path,
        default: dict | list | None = None,
    ) -> dict | list | None: ...

    def write_pack_json(
        self,
        pack_id: str,
        version: str,
        relative_path: str | Path,
        payload: dict | list,
    ) -> None: ...


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


def _normalize_nested_folder(folder_path: str | None) -> str:
    raw = str(folder_path or "").replace("\\", "/").strip().strip("/")
    if not raw:
        return ""
    parts = [segment.strip() for segment in raw.split("/")]
    if any((not segment) or segment in {".", ".."} for segment in parts):
        raise ValueError("folder path is invalid")
    return "/".join(parts)


def _normalize_pack_relative_path(relative_path: str | Path) -> Path:
    raw = str(relative_path).replace("\\", "/").strip().strip("/")
    if not raw:
        raise ValueError("relative path is required")
    path = Path(raw)
    if path.is_absolute():
        raise ValueError("relative path must be relative")
    if any(
        segment in {".", ".."} or not str(segment).strip() for segment in path.parts
    ):
        raise ValueError("relative path is invalid")
    return path


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
        folder_path: str | None,
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
        type_dir = _resolve_card_type_dir(pack_root, card_type)
        nested_folder = _normalize_nested_folder(folder_path)
        card_dir = pack_root / type_dir
        if nested_folder:
            card_dir = card_dir / Path(nested_folder)
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

    def read_pack_json(
        self,
        pack_id: str,
        version: str,
        relative_path: str | Path,
        default: dict | list | None = None,
    ) -> dict | list | None:
        target = self.get_pack_dir(pack_id, version) / _normalize_pack_relative_path(
            relative_path
        )
        if not target.exists():
            return default
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return default

    def write_pack_json(
        self,
        pack_id: str,
        version: str,
        relative_path: str | Path,
        payload: dict | list,
    ) -> None:
        target = self.get_pack_dir(pack_id, version) / _normalize_pack_relative_path(
            relative_path
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class OssPackStorage(LocalPackStorage):
    """OSS-backed pack storage without persistent local cache writes."""

    def __init__(self, packs_root: Path, user_namespace: str | None = None):
        self.packs_root = packs_root
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
        namespace = str(user_namespace or "default").strip().strip("/")
        self._user_namespace = namespace or "default"

    def get_pack_dir(self, pack_id: str, version: str) -> Path:
        return self.packs_root / pack_id / version

    def install_pack_from_zip(
        self,
        zip_path: Path,
        pack_id: str,
        version: str,
        cards_root: str,
    ) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            names = [name for name in zf.namelist() if not name.endswith("/")]
            if not any(
                Path(name).parts and Path(name).parts[0] == cards_root for name in names
            ):
                raise ValueError("cards_root missing in zip")
            for name in names:
                key = self._object_key(pack_id, version, Path(name))
                self._bucket.put_object(key, zf.read(name))

    def remove_pack(self, pack_id: str, version: str) -> None:
        prefix = self._pack_prefix(pack_id, version)
        for obj in self._oss2.ObjectIterator(self._bucket, prefix=prefix):
            self._bucket.delete_object(obj.key)

    def export_pack(self, pack_id: str, version: str, output_path: Path) -> None:
        prefix = self._pack_prefix(pack_id, version)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            found = False
            for obj in self._oss2.ObjectIterator(self._bucket, prefix=prefix):
                relative = obj.key[len(prefix) :].lstrip("/")
                if not relative:
                    continue
                found = True
                content = self._bucket.get_object(obj.key).read()
                zf.writestr(relative, content)
        if not found:
            raise ValueError("pack files missing")

    def save_card(
        self,
        pack_id: str,
        version: str,
        cards_root: str,
        card_type: str,
        card_id: str,
        folder_path: str | None,
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

        card_dir = self._resolve_card_type_dir_remote(
            pack_id, version, cards_root, card_type
        )
        nested_folder = _normalize_nested_folder(folder_path)
        relative = Path(cards_root) / card_dir
        if nested_folder:
            relative = relative / Path(nested_folder)
        relative = relative / f"{card_id}.md"
        path = self.get_pack_dir(pack_id, version) / relative
        self._bucket.put_object(
            self._object_key(pack_id, version, relative),
            render_card(frontmatter, body).encode("utf-8"),
        )
        if original_path:
            pack_dir = self.get_pack_dir(pack_id, version)
            old_target = Path(original_path)
            if ensure_within_directory(pack_dir, old_target):
                old_relative = old_target.relative_to(pack_dir)
                # Only delete old object when path actually changed (rename/move).
                if old_relative != relative:
                    self._bucket.delete_object(
                        self._object_key(pack_id, version, old_relative)
                    )
        return path

    def update_card(self, path: Path, frontmatter: dict, body: str) -> None:
        from .card_editor import render_card
        from .validator import validate_card_frontmatter

        validate_card_frontmatter(frontmatter, body)
        pack_id, version = self._resolve_pack_from_path(path)
        pack_dir = self.get_pack_dir(pack_id, version)
        if not ensure_within_directory(pack_dir, Path(path)):
            raise ValueError("card path is outside pack root")
        relative = Path(path).relative_to(pack_dir)
        self._bucket.put_object(
            self._object_key(pack_id, version, relative),
            render_card(frontmatter, body).encode("utf-8"),
        )

    def delete_card(
        self, pack_id: str, version: str, cards_root: str, path: Path
    ) -> None:
        self._delete_remote_path(path, pack_id, version)

    def sync_pack(self, pack_id: str, version: str) -> None:
        prefix = self._pack_prefix(pack_id, version)
        if not any(
            True for _ in self._oss2.ObjectIterator(self._bucket, prefix=prefix)
        ):
            raise ValueError("pack files missing")

    def read_pack_json(
        self,
        pack_id: str,
        version: str,
        relative_path: str | Path,
        default: dict | list | None = None,
    ) -> dict | list | None:
        key = self._object_key(
            pack_id, version, _normalize_pack_relative_path(relative_path)
        )
        try:
            if not self._bucket.object_exists(key):
                return default
            raw = self._bucket.get_object(key).read()
            text = (
                raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
            )
            return json.loads(text)
        except Exception:
            return default

    def write_pack_json(
        self,
        pack_id: str,
        version: str,
        relative_path: str | Path,
        payload: dict | list,
    ) -> None:
        key = self._object_key(
            pack_id, version, _normalize_pack_relative_path(relative_path)
        )
        self._bucket.put_object(
            key,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    def list_card_paths(
        self, pack_id: str, version: str, cards_root: str
    ) -> list[Path]:
        prefix = self._pack_prefix(pack_id, version)
        cards_prefix = f"{prefix}/{str(cards_root).strip('/')}/"
        root = self.get_pack_cards_root(pack_id, version, cards_root)
        paths: list[Path] = []
        for obj in self._oss2.ObjectIterator(self._bucket, prefix=cards_prefix):
            rel = obj.key[len(prefix) :].lstrip("/")
            if rel.endswith(".md"):
                paths.append(root.parent / rel)
        return sorted(paths)

    def read_card_text(self, path: Path) -> str:
        pack_id, version = self._resolve_pack_from_path(path)
        pack_dir = self.get_pack_dir(pack_id, version)
        target = Path(path)
        if not ensure_within_directory(pack_dir, target):
            raise ValueError("card path is outside pack root")
        relative = target.relative_to(pack_dir)
        data = self._bucket.get_object(
            self._object_key(pack_id, version, relative)
        ).read()
        return data.decode("utf-8")

    def card_exists(self, path: Path) -> bool:
        try:
            pack_id, version = self._resolve_pack_from_path(path)
            pack_dir = self.get_pack_dir(pack_id, version)
            target = Path(path)
            if not ensure_within_directory(pack_dir, target):
                return False
            relative = target.relative_to(pack_dir)
            key = self._object_key(pack_id, version, relative)
            return bool(self._bucket.object_exists(key))
        except Exception:
            return False

    def create_pack_manifest(
        self,
        pack_id: str,
        version: str,
        cards_root: str,
        manifest: dict,
    ) -> None:
        manifest_rel = Path("pack.json")
        self._bucket.put_object(
            self._object_key(pack_id, version, manifest_rel),
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        keep_rel = Path(cards_root) / ".keep"
        self._bucket.put_object(
            self._object_key(pack_id, version, keep_rel),
            b"",
        )

    def _pack_prefix(self, pack_id: str, version: str) -> str:
        return f"{self._prefix}/users/{self._user_namespace}/packs/{pack_id}/{version}"

    def _object_key(self, pack_id: str, version: str, relative_path: Path) -> str:
        relative = str(relative_path).replace("\\", "/").lstrip("/")
        return f"{self._pack_prefix(pack_id, version)}/{relative}"

    def _delete_remote_path(self, path: Path, pack_id: str, version: str) -> None:
        pack_dir = self.get_pack_dir(pack_id, version)
        target = Path(path)
        if not ensure_within_directory(pack_dir, target):
            return
        relative = target.relative_to(pack_dir)
        self._bucket.delete_object(self._object_key(pack_id, version, relative))

    def _resolve_card_type_dir_remote(
        self,
        pack_id: str,
        version: str,
        cards_root: str,
        card_type: str,
    ) -> str:
        normalized = str(card_type).strip()
        if not normalized:
            return "cards"
        singular = normalized
        plural = "memories" if normalized == "memory" else f"{normalized}s"
        existing = self._list_card_type_dirs(pack_id, version, cards_root)
        if singular in existing:
            return singular
        if plural in existing:
            return plural
        return plural

    def _list_card_type_dirs(
        self, pack_id: str, version: str, cards_root: str
    ) -> set[str]:
        prefix = f"{self._pack_prefix(pack_id, version)}/{str(cards_root).strip('/')}/"
        result: set[str] = set()
        for obj in self._oss2.ObjectIterator(self._bucket, prefix=prefix):
            rel = obj.key[len(prefix) :].lstrip("/")
            if not rel:
                continue
            first = rel.split("/", 1)[0].strip()
            if first:
                result.add(first)
        return result

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
