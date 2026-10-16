# Provenance

The initial code was extracted and adapted from the maintainer's locally
developed offline evidence-packet loader. That application used fixed reviewed
inputs; this package makes the trusted manifest an explicit interface and has
its own tests. It does not replace or certify the original application.

Implementation, documentation and independent code review used Codex assistance.
The runtime uses Python's standard library. All included example data is
synthetic and authored for this package. No upstream source-code excerpts,
evaluation corpus, reference judgments or private project records are included.

The original application-specific checks are not advertised as general secret
sanitization. The reusable scope is bounded file loading, pinned-byte integrity,
strict JSON parsing and exact-byte emission.
