# Changelog

## Unreleased

- Complete short writes when emitting verified fixture bytes to raw stdout.
  Report `IO_ERROR` instead of success when output makes no progress, including
  a nonblocking pipe used with unbuffered Python. An output failure can still
  leave a partial prefix; emission is not transactional.
- Add real-pipe regressions and controls for short writes, stalled output,
  write/flush failures, validation before output, and full unbuffered emission.
- Avoid a second stdout flush error during interpreter shutdown after an output
  failure. Redirect only the process's original stdout to the null device;
  leave caller-owned replacement streams untouched. Add real buffered-output
  regressions for closed pipes, a full device, and a blocked pipe.

## 0.1.1 — 2026-10-17

- Allow execute-only fixture roots, root ancestors and nested directories by
  using path descriptors for traversal. Symlink and regular-file restrictions
  remain enforced.
- Add real permission regressions for directory traversal and denied access.
  Tests explicitly skip when the environment bypasses the tested permissions.

## 0.1.0 — 2026-10-16

Initial early release of the standalone Linux library and CLI:

- Externally pinned manifest with immutable case metadata.
- Bounded regular-file reads with no-follow directory traversal.
- Strict JSON validation and exact-byte emission.
- Offline adversarial tests and synthetic examples.

No semantic evaluation, secret sanitization, provider connection, or original
study data is included.
