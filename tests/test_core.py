from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from pinned_json import MAX_BYTES, PinnedJsonError, load_manifest
from pinned_json import core


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux descriptor semantics required")
class PinnedJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "fixtures"
        self.root.mkdir()
        self.body = b'{ "message": "synthetic fixture", "value": 3 }\n'
        self.path = self.root / "case.json"
        self.path.write_bytes(self.body)
        self.value = {
            "schema_version": 1,
            "files": {"sample": {"path": "case.json", "sha256": digest(self.body)}},
        }
        self.trusted = self.write_manifest(self.value)

    def write_manifest(self, value: object) -> str:
        return self.write_raw_manifest(json.dumps(value).encode())

    def write_raw_manifest(self, data: bytes) -> str:
        (self.root / "manifest.json").write_bytes(data)
        return digest(data)

    def load(self):
        return load_manifest(self.root, self.trusted)

    def assert_code(self, code: str, operation) -> None:
        with self.assertRaises(PinnedJsonError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)

    def cli(self, *args: str, trusted: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "pinned_json", "--root", str(self.root),
             "--manifest-sha256", trusted if trusted is not None else self.trusted, *args],
            capture_output=True, timeout=5,
        )

    def restrict_mode(self, path: Path, mode: int) -> None:
        previous = stat.S_IMODE(path.stat().st_mode)
        self.addCleanup(path.chmod, previous)
        path.chmod(mode)

    def require_permission_denied(self, operation) -> None:
        try:
            operation()
        except PermissionError:
            return
        self.skipTest("Permission restrictions are bypassed in this environment")

    def assert_traversal_without_listing(self, directory: Path) -> None:
        self.restrict_mode(directory, 0o111)
        self.require_permission_denied(lambda: os.listdir(directory))
        self.assertEqual(digest((self.root / "manifest.json").read_bytes()), self.trusted)
        self.assertEqual(self.path.read_bytes(), self.body)
        manifest = self.load()
        self.assertIsNone(manifest.verify())
        self.assertEqual(manifest.emit("sample"), self.body)
        verified = self.cli("verify")
        self.assertEqual((verified.returncode, verified.stdout, verified.stderr), (0, b"", b""))
        emitted = self.cli("emit", "sample")
        self.assertEqual((emitted.returncode, emitted.stdout, emitted.stderr), (0, self.body, b""))

    def assert_cli_access_denied(self) -> None:
        for args in (("verify",), ("emit", "sample")):
            result = self.cli(*args)
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (1, b"", b"FILE_ACCESS_ERROR\n"))

    def test_exact_emission_and_unlisted_files_are_not_read(self):
        (self.root / "labels.json").write_bytes(b"not JSON; unapproved label")
        manifest = self.load()
        self.assertEqual(manifest.case_ids, ("sample",))
        self.assertIsNone(manifest.verify())
        self.assertEqual(manifest.emit("sample"), self.body)
        self.assert_code("CASE_NOT_FOUND", lambda: manifest.emit("labels"))

    def test_manifest_tampering_is_rejected_before_parsing(self):
        (self.root / "manifest.json").write_bytes(b"unapproved manifest")
        self.assert_code("MANIFEST_HASH_MISMATCH", self.load)

    def test_file_tampering_is_rejected(self):
        manifest = self.load()
        self.path.write_bytes(b'{"message":"changed"}')
        self.assert_code("FILE_HASH_MISMATCH", lambda: manifest.emit("sample"))

    def test_digest_format_is_required(self):
        for value in ("", "a" * 63, "A" * 64, "g" * 64, None, 1):
            with self.subTest(value=value):
                self.assert_code("TRUSTED_DIGEST_INVALID", lambda: load_manifest(self.root, value))

    def test_exact_manifest_schema(self):
        values = [
            [], {}, {"schema_version": 1, "files": {}},
            {"schema_version": True, "files": self.value["files"]},
            {"schema_version": 2, "files": self.value["files"]},
            {**self.value, "extra": "unapproved field"},
            {"schema_version": 1, "files": []},
            {"schema_version": 1, "files": {"sample": {"path": "case.json"}}},
            {"schema_version": 1, "files": {"sample": {"path": "case.json", "sha256": 1}}},
            {"schema_version": 1, "files": {"sample": {**self.value["files"]["sample"], "label": 1}}},
            {"schema_version": 1, "files": {"bad case": self.value["files"]["sample"]}},
        ]
        for value in values:
            with self.subTest(value=value):
                self.trusted = self.write_manifest(value)
                self.assert_code("MANIFEST_SCHEMA_INVALID", self.load)

    def test_manifest_duplicate_keys_are_rejected(self):
        self.trusted = self.write_raw_manifest(b'{"schema_version":1,"schema_version":1,"files":{}}')
        self.assert_code("MANIFEST_JSON_INVALID", self.load)

    def test_manifest_paths_are_strict_relative_paths(self):
        for path in ("/tmp/case.json", "../case.json", "sub/../case.json", "./case.json",
                     "sub//case.json", "case.json/", "sub\\case.json", "", "bad\u0000path", "\ud800", 3):
            with self.subTest(path=path):
                self.value["files"]["sample"]["path"] = path
                self.trusted = self.write_manifest(self.value)
                self.assert_code("PATH_INVALID", self.load)

    def test_nested_regular_files_work(self):
        (self.root / "nested").mkdir()
        self.path.rename(self.root / "nested" / "case.json")
        self.value["files"]["sample"]["path"] = "nested/case.json"
        self.trusted = self.write_manifest(self.value)
        self.assertEqual(self.load().emit("sample"), self.body)

    def test_execute_only_root_is_supported(self):
        self.assert_traversal_without_listing(self.root)

    def test_execute_only_root_ancestor_is_supported(self):
        self.assert_traversal_without_listing(self.base)

    def test_execute_only_fixture_ancestor_is_supported(self):
        nested = self.root / "nested"
        nested.mkdir()
        self.path = self.path.rename(nested / "case.json")
        self.value["files"]["sample"]["path"] = "nested/case.json"
        self.trusted = self.write_manifest(self.value)
        self.assert_traversal_without_listing(nested)

    def test_directory_search_permission_is_required(self):
        manifest = self.load()
        self.restrict_mode(self.root, 0o444)
        self.require_permission_denied(self.path.read_bytes)
        self.assert_code("FILE_ACCESS_ERROR", self.load)
        self.assert_code("FILE_ACCESS_ERROR", manifest.verify)
        self.assert_code("FILE_ACCESS_ERROR", lambda: manifest.emit("sample"))
        self.assert_cli_access_denied()

    def test_fixture_read_permission_is_required(self):
        manifest = self.load()
        self.restrict_mode(self.path, 0o000)
        self.require_permission_denied(self.path.read_bytes)
        self.load()
        self.assert_code("FILE_ACCESS_ERROR", manifest.verify)
        self.assert_code("FILE_ACCESS_ERROR", lambda: manifest.emit("sample"))
        self.assert_cli_access_denied()

    def test_parent_components_in_root_are_rejected(self):
        self.assert_code("ROOT_INVALID", lambda: load_manifest(self.root / ".." / "fixtures", self.trusted))

    def test_relative_root_is_supported(self):
        with mock.patch("pinned_json.core.os.getcwd", return_value=str(self.base)):
            self.assertEqual(load_manifest("./fixtures", self.trusted).emit("sample"), self.body)

    def test_symlinked_manifest_is_rejected(self):
        manifest = self.root / "manifest.json"
        destination = self.base / "external-manifest.json"
        manifest.rename(destination)
        manifest.symlink_to(destination)
        self.assert_code("PATH_UNSAFE", self.load)

    def test_symlinked_fixture_is_rejected_even_with_matching_bytes(self):
        destination = self.base / "external-case.json"
        self.path.rename(destination)
        self.path.symlink_to(destination)
        self.assert_code("PATH_UNSAFE", lambda: self.load().emit("sample"))

    def test_symlinked_fixture_ancestor_is_rejected(self):
        destination = self.base / "outside"
        destination.mkdir()
        self.path.rename(destination / "case.json")
        (self.root / "nested").symlink_to(destination, target_is_directory=True)
        self.value["files"]["sample"]["path"] = "nested/case.json"
        self.trusted = self.write_manifest(self.value)
        self.assert_code("PATH_UNSAFE", lambda: self.load().emit("sample"))

    def test_every_root_ancestor_is_opened_without_following_links(self):
        link = self.base / "alias"
        link.symlink_to(self.base, target_is_directory=True)
        self.assert_code("PATH_UNSAFE", lambda: load_manifest(link / "fixtures", self.trusted))

    def test_root_is_rechecked_at_emission(self):
        manifest = self.load()
        moved = self.base / "moved"
        self.root.rename(moved)
        self.root.symlink_to(moved, target_is_directory=True)
        self.assert_code("PATH_UNSAFE", lambda: manifest.emit("sample"))

    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        self.path.unlink()
        os.mkfifo(self.path)
        result = self.cli("emit", "sample")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"FILE_NOT_REGULAR\n")

    def test_directories_are_not_fixture_files(self):
        self.path.unlink()
        self.path.mkdir()
        self.assert_code("FILE_NOT_REGULAR", lambda: self.load().emit("sample"))

    def test_missing_files_return_only_a_code(self):
        self.path.unlink()
        self.assert_code("FILE_ACCESS_ERROR", lambda: self.load().emit("sample"))

    def test_manifest_size_is_bounded(self):
        self.trusted = self.write_raw_manifest(b" " * (MAX_BYTES + 1))
        self.assert_code("FILE_TOO_LARGE", self.load)

    def test_fixture_at_limit_works_and_larger_file_is_rejected(self):
        body = b'"' + b"x" * (MAX_BYTES - 2) + b'"'
        self.path.write_bytes(body)
        self.value["files"]["sample"]["sha256"] = digest(body)
        self.trusted = self.write_manifest(self.value)
        manifest = self.load()
        self.assertEqual(manifest.emit("sample"), body)
        self.path.write_bytes(body + b" ")
        self.assert_code("FILE_TOO_LARGE", lambda: manifest.emit("sample"))

    def test_read_limit_does_not_trust_stat_size(self):
        manifest = self.load()
        self.path.write_bytes(b" " * (MAX_BYTES + 1))
        real_fstat = os.fstat

        def zero_size(fd):
            fields = list(real_fstat(fd))
            fields[6] = 0
            return os.stat_result(fields)

        with mock.patch("pinned_json.core.os.fstat", side_effect=zero_size):
            self.assert_code("FILE_TOO_LARGE", lambda: manifest.emit("sample"))

    def test_json_is_parsed_strictly_even_when_hash_is_pinned(self):
        for body in (b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}', b"NaN",
                     b"Infinity", b"-Infinity", b"1e309", b"-1e309", b"[1,]",
                     b"{} trailing", b"\xff", b"\xef\xbb\xbf{}", b"9" * 4301):
            with self.subTest(body=body[:60]):
                self.path.write_bytes(body)
                self.value["files"]["sample"]["sha256"] = digest(body)
                self.trusted = self.write_manifest(self.value)
                self.assert_code("JSON_INVALID", lambda: self.load().emit("sample"))

    def test_case_identifiers_are_bounded(self):
        manifest = self.load()
        for case_id in ("../sample", "", ".sample", "a" * 65, "sample\n", None):
            with self.subTest(case_id=case_id):
                self.assert_code("CASE_ID_INVALID", lambda: manifest.emit(case_id))

    def test_loaded_manifest_pins_are_immutable(self):
        manifest = self.load()
        with self.assertRaises(TypeError):
            manifest._files["sample"] = manifest._files["sample"]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            manifest._files["sample"].sha256 = "0" * 64
        with self.assertRaises(dataclasses.FrozenInstanceError):
            manifest._root = str(self.base)

    def test_later_manifest_edits_do_not_change_loaded_approval(self):
        manifest = self.load()
        self.value["files"]["labels"] = self.value["files"]["sample"]
        self.write_manifest(self.value)
        self.assert_code("CASE_NOT_FOUND", lambda: manifest.emit("labels"))
        self.assertEqual(manifest.emit("sample"), self.body)

    def test_parse_and_emit_use_the_same_bytes_as_hashing(self):
        manifest = self.load()
        original = core._strict_json

        def replace_during_parse(data, error_code):
            self.path.write_bytes(b'{"message":"replaced after hashing"}')
            return original(data, error_code)

        with mock.patch("pinned_json.core._strict_json", side_effect=replace_during_parse):
            self.assertEqual(manifest.emit("sample"), self.body)
        self.assert_code("FILE_HASH_MISMATCH", lambda: manifest.emit("sample"))

    def test_verify_checks_all_entries_but_emit_checks_the_selected_one(self):
        self.value["files"]["missing"] = {"path": "missing.json", "sha256": digest(b"{}")}
        self.trusted = self.write_manifest(self.value)
        manifest = self.load()
        self.assertEqual(manifest.emit("sample"), self.body)
        self.assert_code("FILE_ACCESS_ERROR", manifest.verify)

    def test_unsupported_platform_has_fixed_error(self):
        with mock.patch("pinned_json.core.sys.platform", "darwin"):
            self.assert_code("PLATFORM_UNSUPPORTED", self.load)

    def test_cli_verify_is_silent_and_emit_preserves_original_bytes(self):
        verified = self.cli("verify")
        self.assertEqual((verified.returncode, verified.stdout, verified.stderr), (0, b"", b""))
        emitted = self.cli("emit", "sample")
        self.assertEqual((emitted.returncode, emitted.stdout, emitted.stderr), (0, self.body, b""))

    def test_cli_failures_have_no_stdout_or_supplied_values(self):
        for args, trusted, expected in (
            (("emit", "sample"), "sensitive-digest-input", b"TRUSTED_DIGEST_INVALID\n"),
            (("emit", "private-name"), self.trusted, b"CASE_NOT_FOUND\n"),
            (("emit", "../private-name"), self.trusted, b"CASE_ID_INVALID\n"),
            (("emit", "sample", "--sensitive-value"), self.trusted, b"ARGUMENT_ERROR\n"),
            (("unknown-private-command",), self.trusted, b"ARGUMENT_ERROR\n"),
        ):
            with self.subTest(args=args):
                result = self.cli(*args, trusted=trusted)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, expected)

    def test_cli_tampering_never_emits_any_fixture_bytes(self):
        self.path.write_bytes(b'{"message":"unapproved change"}')
        result = self.cli("emit", "sample")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, b"", b"FILE_HASH_MISMATCH\n"))


if __name__ == "__main__":
    unittest.main()
