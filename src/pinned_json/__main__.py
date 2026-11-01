"""Command-line interface. Validation failures never emit fixture bytes."""

from __future__ import annotations

import argparse
import os
import sys

from .core import PinnedJsonError, load_manifest


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's normal error includes supplied arguments and their values.
        self.exit(2, "ARGUMENT_ERROR\n")


def _discard_failed_stdout(output) -> None:
    # Python flushes the original standard stream again during shutdown. After
    # a failed buffered write, send that retry to the null device so it cannot
    # append a traceback or replace our exit status. Leave caller-owned streams
    # alone; this cleanup is only for the process's original stdout buffer.
    if output is not getattr(sys.__stdout__, "buffer", None):
        return
    try:
        with open(os.devnull, "wb", buffering=0) as sink:
            os.dup2(sink.fileno(), output.fileno())
    except (OSError, ValueError):
        # Cleanup failure must not hide the original I/O error. Shutdown may
        # still report its own error if the OS cannot provide a usable sink.
        pass


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="pinned-json", description="Verify and emit externally pinned JSON fixtures.")
    parser.add_argument("--root", required=True, help="Directory containing manifest.json")
    parser.add_argument("--manifest-sha256", required=True, help="Reviewed manifest digest from trusted external configuration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Check every pinned fixture; success is silent")
    emit = commands.add_parser("emit", help="Write one verified fixture's original bytes")
    emit.add_argument("case_id")
    args = parser.parse_args(argv)
    output = None
    try:
        manifest = load_manifest(args.root, args.manifest_sha256)
        if args.command == "verify":
            manifest.verify()
        else:
            payload = manifest.emit(args.case_id)
            # No stdout writes occur until all input validation has completed.
            output = sys.stdout.buffer
            remaining = memoryview(payload)
            while remaining:
                written = output.write(remaining)
                # Raw stdout (-u) may write only a prefix or return None when
                # it would block. Never report success or spin on no progress.
                if written is None or written <= 0:
                    raise OSError("output made no progress")
                remaining = remaining[written:]
            output.flush()
        return 0
    except PinnedJsonError as error:
        print(error.code, file=sys.stderr)
        return 1
    except OSError:
        if output is not None:
            _discard_failed_stdout(output)
        print("IO_ERROR", file=sys.stderr)
        return 1
    except Exception:
        print("INTERNAL_ERROR", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
