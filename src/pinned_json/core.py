"""Read bounded JSON files whose exact bytes are pinned by a reviewed manifest."""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import stat
import sys
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

MAX_BYTES = 256 * 1024
MAX_CASES = 1024
_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class PinnedJsonError(Exception):
    """A failure identified by a fixed code, without any supplied input text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _PinnedFile:
    path: str
    sha256: str


@dataclass(frozen=True)
class Manifest:
    """Immutable pins loaded by :func:`load_manifest`.

    Verification checks every case. Emission checks only the requested case and
    returns exactly the bytes that were hashed and parsed, without reformatting.
    """

    _root: str
    _files: Mapping[str, _PinnedFile]

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(self._files)

    def emit(self, case_id: str) -> bytes:
        if not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id):
            raise PinnedJsonError("CASE_ID_INVALID")
        pinned = self._files.get(case_id)
        if pinned is None:
            raise PinnedJsonError("CASE_NOT_FOUND")
        data = _read_file(self._root, pinned.path)
        if hashlib.sha256(data).hexdigest() != pinned.sha256:
            raise PinnedJsonError("FILE_HASH_MISMATCH")
        _strict_json(data, "JSON_INVALID")
        return data

    def verify(self) -> None:
        for case_id in self.case_ids:
            self.emit(case_id)


def _require_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise PinnedJsonError("PLATFORM_UNSUPPORTED")


def _root_path(root: str | os.PathLike[str]) -> str:
    try:
        raw = os.fspath(root)
    except TypeError:
        raise PinnedJsonError("ROOT_INVALID") from None
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise PinnedJsonError("ROOT_INVALID")
    try:
        raw.encode("utf-8")
    except UnicodeError:
        raise PinnedJsonError("ROOT_INVALID") from None
    if ".." in raw.split("/"):
        raise PinnedJsonError("ROOT_INVALID")
    if not raw.startswith("/"):
        try:
            raw = os.getcwd() + "/" + raw
        except OSError:
            raise PinnedJsonError("FILE_ACCESS_ERROR") from None
    # Only empty and dot components are elided. A parent component is never
    # normalized away, and symlinks are never resolved to their targets.
    return "/" + "/".join(part for part in raw.split("/") if part not in ("", "."))


def _relative_parts(path: object) -> list[str]:
    if not isinstance(path, str) or not path or len(path) > 4096 or "\x00" in path or "\\" in path:
        raise PinnedJsonError("PATH_INVALID")
    try:
        path.encode("utf-8")
    except UnicodeError:
        raise PinnedJsonError("PATH_INVALID") from None
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PinnedJsonError("PATH_INVALID")
    return parts


def _access_error(error: OSError) -> PinnedJsonError:
    if error.errno in (errno.ELOOP, errno.ENOTDIR):
        return PinnedJsonError("PATH_UNSAFE")
    return PinnedJsonError("FILE_ACCESS_ERROR")


def _open_root(root: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for part in root.split("/"):
            if not part:
                continue
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_file(root: str, path: str) -> bytes:
    _require_linux()
    parts = _relative_parts(path)
    directory_fd = None
    file_fd = None
    try:
        directory_fd = _open_root(root)
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        # O_NONBLOCK prevents opening a FIFO from waiting for a writer. The
        # descriptor is then checked, so devices/directories/FIFOs are refused.
        file_fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=directory_fd,
        )
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode):
            raise PinnedJsonError("FILE_NOT_REGULAR")
        if info.st_size > MAX_BYTES:
            raise PinnedJsonError("FILE_TOO_LARGE")
        chunks = []
        size = 0
        while size <= MAX_BYTES:
            chunk = os.read(file_fd, min(64 * 1024, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > MAX_BYTES:
            raise PinnedJsonError("FILE_TOO_LARGE")
        return b"".join(chunks)
    except OSError as error:
        raise _access_error(error) from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _strict_json(data: bytes, error_code: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def constant(_value: str) -> None:
        raise ValueError

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError
        return result

    def bounded_int(value: str) -> int:
        # Also bound conversion on Python 3.10, which predates the default
        # decimal-integer digit limit in newer Python versions.
        if len(value.lstrip("-")) > 4300:
            raise ValueError
        return int(value)

    try:
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=pairs,
            parse_constant=constant, parse_float=finite_float, parse_int=bounded_int,
        )
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        raise PinnedJsonError(error_code) from None


def load_manifest(root: str | os.PathLike[str], trusted_hash: str) -> Manifest:
    """Load ``manifest.json`` against a digest supplied by external review.

    This function does not create an approval or derive its own trusted digest.
    Root may be absolute or relative; lexical ``..`` components are refused.
    """
    _require_linux()
    if not isinstance(trusted_hash, str) or not _DIGEST.fullmatch(trusted_hash):
        raise PinnedJsonError("TRUSTED_DIGEST_INVALID")
    root_path = _root_path(root)
    data = _read_file(root_path, "manifest.json")
    if hashlib.sha256(data).hexdigest() != trusted_hash:
        raise PinnedJsonError("MANIFEST_HASH_MISMATCH")
    value = _strict_json(data, "MANIFEST_JSON_INVALID")
    if not isinstance(value, dict) or set(value) != {"schema_version", "files"}:
        raise PinnedJsonError("MANIFEST_SCHEMA_INVALID")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise PinnedJsonError("MANIFEST_SCHEMA_INVALID")
    files = value["files"]
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_CASES:
        raise PinnedJsonError("MANIFEST_SCHEMA_INVALID")
    pinned = {}
    for case_id, entry in files.items():
        if not _CASE_ID.fullmatch(case_id):
            raise PinnedJsonError("MANIFEST_SCHEMA_INVALID")
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise PinnedJsonError("MANIFEST_SCHEMA_INVALID")
        _relative_parts(entry["path"])
        digest = entry["sha256"]
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise PinnedJsonError("MANIFEST_SCHEMA_INVALID")
        pinned[case_id] = _PinnedFile(entry["path"], digest)
    return Manifest(root_path, MappingProxyType(pinned))
