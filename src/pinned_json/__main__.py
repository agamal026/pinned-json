"""Command-line interface. Validation failures never emit fixture bytes."""

from __future__ import annotations

import argparse
import sys

from .core import PinnedJsonError, load_manifest


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's normal error includes supplied arguments and their values.
        self.exit(2, "ARGUMENT_ERROR\n")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="pinned-json", description="Verify and emit externally pinned JSON fixtures.")
    parser.add_argument("--root", required=True, help="Directory containing manifest.json")
    parser.add_argument("--manifest-sha256", required=True, help="Reviewed manifest digest from trusted external configuration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Check every pinned fixture; success is silent")
    emit = commands.add_parser("emit", help="Write one verified fixture's original bytes")
    emit.add_argument("case_id")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.root, args.manifest_sha256)
        if args.command == "verify":
            manifest.verify()
        else:
            payload = manifest.emit(args.case_id)
            # No stdout writes occur until all input validation has completed.
            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()
        return 0
    except PinnedJsonError as error:
        print(error.code, file=sys.stderr)
        return 1
    except OSError:
        print("IO_ERROR", file=sys.stderr)
        return 1
    except Exception:
        print("INTERNAL_ERROR", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
