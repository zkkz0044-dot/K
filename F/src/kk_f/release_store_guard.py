"""FH04 root-owned immutable release-store metadata guard."""

from __future__ import annotations

import os
import stat
from pathlib import PurePosixPath, Path


class ReleaseStoreGuardError(ValueError):
    pass


def _parts(value: object) -> tuple[str, ...]:
    if not isinstance(value, (str, os.PathLike)):
        raise ReleaseStoreGuardError("absolute release-store path required")
    text = os.fspath(value)
    if (
        not text.startswith("/")
        or "\x00" in text
        or (text != "/" and (text.endswith("/") or "//" in text))
    ):
        raise ReleaseStoreGuardError("canonical absolute release-store path required")
    p = PurePosixPath(text)
    if p.as_posix() != text or any(x in ("", ".", "..") for x in p.parts[1:]):
        raise ReleaseStoreGuardError("canonical absolute release-store path required")
    return tuple(p.parts[1:])


def verify_store_root(value: str | os.PathLike[str]) -> tuple[Path, int]:
    parts = _parts(value)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nfd
            st = os.fstat(fd)
            if st.st_uid != 0:
                raise ReleaseStoreGuardError("release-store ancestor must be root-owned")
            if st.st_mode & 0o022 and not (st.st_mode & stat.S_ISVTX):
                raise ReleaseStoreGuardError("release-store ancestor is writable by non-root")
        st = os.fstat(fd)
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise ReleaseStoreGuardError(
                "release-store root must be root-owned and non-writable by non-root"
            )
        return Path(os.fspath(value)), st.st_dev
    except ReleaseStoreGuardError:
        raise
    except OSError as exc:
        raise ReleaseStoreGuardError("release-store path cannot be resolved safely") from exc
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def verify_published_release(store_root: str | os.PathLike[str], release_id: str) -> Path:
    store, dev = verify_store_root(store_root)
    release = store / release_id
    try:
        rst = release.lstat()
    except OSError as exc:
        raise ReleaseStoreGuardError("published release unavailable") from exc
    if (
        not stat.S_ISDIR(rst.st_mode)
        or stat.S_ISLNK(rst.st_mode)
        or rst.st_uid != 0
        or rst.st_dev != dev
        or rst.st_mode & 0o222
    ):
        raise ReleaseStoreGuardError("published release root metadata invalid")
    try:
        for current, dirs, files, dirfd in os.fwalk(release, topdown=True, follow_symlinks=False):
            cst = os.fstat(dirfd)
            if cst.st_uid != 0 or cst.st_dev != dev or cst.st_mode & 0o222:
                raise ReleaseStoreGuardError("published release directory metadata invalid")
            for name in dirs:
                st = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if (
                    not stat.S_ISDIR(st.st_mode)
                    or stat.S_ISLNK(st.st_mode)
                    or st.st_uid != 0
                    or st.st_dev != dev
                    or st.st_mode & 0o222
                ):
                    raise ReleaseStoreGuardError("published release directory metadata invalid")
            for name in files:
                st = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(st.st_mode)
                    or st.st_uid != 0
                    or st.st_dev != dev
                    or st.st_mode & 0o222
                    or st.st_nlink != 1
                ):
                    raise ReleaseStoreGuardError("published release file metadata invalid")
    except OSError as exc:
        raise ReleaseStoreGuardError("published release metadata scan failed") from exc
    return release


def remove_private_stage(stage: str | os.PathLike[str]) -> None:
    root = Path(stage)
    if not root.exists() or root.is_symlink():
        return
    try:
        for current, dirs, files in os.walk(root, topdown=False, followlinks=False):
            cur = Path(current)
            try:
                os.chmod(cur, 0o700)
            except OSError:
                pass
            for name in dirs:
                try:
                    os.chmod(cur / name, 0o700)
                except OSError:
                    pass
        import shutil

        shutil.rmtree(root)
    except OSError as exc:
        raise ReleaseStoreGuardError("private stage cleanup failed") from exc


def seal_private_stage(stage: str | os.PathLike[str], store_dev: int) -> None:
    if os.geteuid() != 0:
        raise ReleaseStoreGuardError("release sealing requires root")
    root = Path(stage)
    try:
        for current, dirs, files in os.walk(root, topdown=False, followlinks=False):
            cur = Path(current)
            for name in files:
                p = cur / name
                st = p.lstat()
                if (
                    not stat.S_ISREG(st.st_mode)
                    or stat.S_ISLNK(st.st_mode)
                    or st.st_dev != store_dev
                    or st.st_nlink != 1
                ):
                    raise ReleaseStoreGuardError("stage file metadata invalid")
                mode = 0o555 if st.st_mode & 0o111 else 0o444
                os.chown(p, 0, 0)
                os.chmod(p, mode)
            for name in dirs:
                p = cur / name
                st = p.lstat()
                if (
                    not stat.S_ISDIR(st.st_mode)
                    or stat.S_ISLNK(st.st_mode)
                    or st.st_dev != store_dev
                ):
                    raise ReleaseStoreGuardError("stage directory metadata invalid")
                os.chown(p, 0, 0)
                os.chmod(p, 0o555)
        st = root.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_dev != store_dev:
            raise ReleaseStoreGuardError("stage root metadata invalid")
        os.chown(root, 0, 0)
        os.chmod(root, 0o555)
    except OSError as exc:
        raise ReleaseStoreGuardError("release sealing failed") from exc
