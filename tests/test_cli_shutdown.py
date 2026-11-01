"""Exercise real stdout failures through interpreter shutdown, not mocked flushes."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from pinned_json.__main__ import main


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux output devices required")
class CliShutdownTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        # This fits inside stdout's buffer, so the failure first occurs at flush.
        self.body = b'{"value": 3}\n'
        self.fixture = self.root / "case.json"
        self.fixture.write_bytes(self.body)
        manifest = json.dumps({
            "schema_version": 1,
            "files": {"sample": {
                "path": "case.json", "sha256": hashlib.sha256(self.body).hexdigest(),
            }},
        }).encode()
        (self.root / "manifest.json").write_bytes(manifest)
        self.arguments = ["--root", str(self.root), "--manifest-sha256",
                          hashlib.sha256(manifest).hexdigest(), "emit", "sample"]
        self.environment = os.environ.copy()
        self.environment.pop("PYTHONUNBUFFERED", None)

    def run_cli(self, output, *, unbuffered=False):
        return subprocess.run(
            [sys.executable, *(["-u"] if unbuffered else []), "-m", "pinned_json",
             *self.arguments],
            stdout=output, stderr=subprocess.PIPE, env=self.environment, timeout=5,
        )

    def assert_io_error(self, result):
        # Compare after process exit: shutdown must not replace exit 1 with 120
        # or append an interpreter diagnostic to the fixed error code.
        self.assertEqual((result.returncode, result.stderr), (1, b"IO_ERROR\n"))

    def closed_pipe(self, *, unbuffered=False):
        reader, writer = os.pipe()
        os.close(reader)
        with os.fdopen(writer, "wb", buffering=0) as output:
            return self.run_cli(output, unbuffered=unbuffered)

    def test_buffered_closed_pipe_has_one_fixed_error(self):
        self.assert_io_error(self.closed_pipe())

    def test_unbuffered_closed_pipe_retains_fixed_error(self):
        self.assert_io_error(self.closed_pipe(unbuffered=True))

    def test_buffered_full_device_has_one_fixed_error(self):
        with open("/dev/full", "wb", buffering=0) as output:
            self.assert_io_error(self.run_cli(output))

    def test_unbuffered_full_device_retains_fixed_error(self):
        with open("/dev/full", "wb", buffering=0) as output:
            self.assert_io_error(self.run_cli(output, unbuffered=True))

    def test_buffered_nonblocking_full_pipe_has_one_fixed_error(self):
        import fcntl

        reader, writer = os.pipe()
        with os.fdopen(reader, "rb", buffering=0) as source, \
                os.fdopen(writer, "wb", buffering=0) as output:
            capacity = fcntl.fcntl(output.fileno(), fcntl.F_SETPIPE_SZ, 4096)
            os.set_blocking(output.fileno(), False)
            prefix = b"p" * capacity
            self.assertEqual(output.write(prefix), capacity)
            result = self.run_cli(output)
            output.close()
            captured = source.read()
        self.assert_io_error(result)
        self.assertEqual(captured, prefix, "Failed emission must not change the full pipe")

    def test_validation_error_precedes_closed_output(self):
        self.fixture.write_bytes(b"unapproved content")
        result = self.closed_pipe()
        self.assertEqual((result.returncode, result.stderr),
                         (1, b"FILE_HASH_MISMATCH\n"))

    def test_replaced_stdout_is_not_redirected(self):
        output = mock.Mock()
        output.write.side_effect = BrokenPipeError("private output detail")
        stderr = io.StringIO()
        with mock.patch("sys.stdout", buffer=output), mock.patch("sys.stderr", stderr), \
                mock.patch("os.dup2") as redirect:
            result = main(self.arguments)
        self.assertEqual((result, stderr.getvalue()), (1, "IO_ERROR\n"))
        redirect.assert_not_called()
        output.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
