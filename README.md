# pinned-json

Export exactly the JSON fixtures you reviewed, without accidentally bundling
neighboring labels, notes, or other files.

`pinned-json` is a small Python library and CLI extracted from an offline
evidence-packet workflow. A trusted manifest lists case IDs, relative paths and
SHA256 hashes. The tool verifies the manifest against a separately supplied
digest, validates a selected file, and emits its original bytes without
reserializing them. It makes no network requests and has no runtime dependencies.

**Early release. Linux and Python 3.10+ only.** Maintained by
[@agamal026](https://github.com/agamal026); support is best effort.

## Try the synthetic example

From a checkout of this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/pinned-json --root examples/demo \
  --manifest-sha256 a628ac4a58c386a3e11da73b63a850001f1334fb0e261dae9f203aa76d43a9e3 verify
.venv/bin/pinned-json --root examples/demo \
  --manifest-sha256 a628ac4a58c386a3e11da73b63a850001f1334fb0e261dae9f203aa76d43a9e3 emit demo
```

`verify` validates every listed fixture and exits successfully without output.
`emit demo` writes exactly `examples/demo/packet.json`. The neighboring
`labels.json` is deliberately absent from the manifest and is never included.
Editing even whitespace in the packet causes verification to fail.

The digest above is for this repository's synthetic demonstration. For your
own data, review the complete fixture bytes and manifest, then preserve the
approved manifest digest in trusted configuration or review records. Computing
a fresh digest from whatever input happens to exist immediately before each
run would discard that review boundary.

## Manifest

The root must contain `manifest.json` with exactly this structure:

```json
{
  "schema_version": 1,
  "files": {
    "example": {
      "path": "packets/example.json",
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  }
}
```

Paths are relative to the selected root. Absolute paths, traversal components,
symlinks in the root or any file ancestor, and nonregular files are rejected.
Directories require search (execute) permission; listing permission is
unnecessary. The manifest and selected fixtures must be readable.
Manifest and fixture files are each limited to 256 KiB. JSON must be UTF-8;
duplicate object keys, nonfinite numbers and malformed JSON are rejected.
Fixtures may contain any JSON value; application-specific schemas are outside
this package's scope.

A manifest contains 1–1,024 cases. IDs match
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. Paths have at most 4,096 characters and
integer literals at most 4,300 digits. A root containing a lexical `..`
component is rejected.

## Python API

```python
from pinned_json import load_manifest

manifest = load_manifest(
    "examples/demo",
    "a628ac4a58c386a3e11da73b63a850001f1334fb0e261dae9f203aa76d43a9e3",
)
manifest.verify()
payload = manifest.emit("demo")  # exact bytes, already validated
```

Loaded manifest metadata is immutable. Each `emit` reads and validates the file
again. Validation completes before any bytes are written by the CLI. Rejections
use fixed error codes on stderr, without echoing file contents or input paths.
An output-device failure after writing starts can leave partial output; the
CLI does not provide transactional delivery to a pipe or file.

## Trust and limits

The manifest digest must come from a source you trust. Anyone who can replace
both the manifest and its expected digest can change the admitted files. Hashes
establish byte equality, not authorship, independent review or content safety.

Reviewers must exclude secrets, unwanted labels and unsafe content themselves.
The tool does not sanitize text, check citations, score answers, or restrict
what another process can read. A reviewed packet can still contain malicious
instructions. Use appropriate controls before passing it to a model or tool.
Filesystem and OS resources remain trusted; this is not a general sandbox.

## Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[PROVENANCE.md](PROVENANCE.md). MIT licensed. No evaluation corpus or provider
integration is included.
