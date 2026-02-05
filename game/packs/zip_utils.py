from __future__ import annotations

from pathlib import Path
from typing import Iterable
import zipfile


def ensure_within_directory(base: Path, target: Path) -> bool:
    """判断目标路径是否仍在基准目录内。"""
    try:
        return base.resolve(strict=False) in target.resolve(strict=False).parents or base.resolve(strict=False) == target.resolve(strict=False)
    except Exception:
        return False


def safe_extract(zip_path: Path, dest_dir: Path, members: Iterable[zipfile.ZipInfo] | None = None) -> None:
    """安全解压 zip，防止 Zip Slip 路径穿越。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        infos = list(members) if members is not None else zf.infolist()
        for info in infos:
            target_path = dest_dir / info.filename
            if not ensure_within_directory(dest_dir, target_path):
                raise ValueError('zip slip detected')
        zf.extractall(dest_dir, members=[i.filename for i in infos])
