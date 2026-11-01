# CLI output completion: executed evidence

November 1, 2026. This packet documents [owned-tool PR #1](https://github.com/agamal026/pinned-json/pull/1); it is not an external contribution or a release.

## Exact source

- Original production: `93b9c46a324097a0cc43f16cbf31e16269e8139d`.
- Test-only baseline: `982d2ccbab3dd92e4756a62994d603b17cf3f17d`, tree `d31c42d935d1f30f062b6c476dc3221796bdf54d`.
- Corrected production with identical tests: `53a4a33b58da50b58f6937cb8462f867dfde6ab1`, tree `b994f88d7c1dfa3ccc17edd9dfbd9acd46914800`.
- Actual hosted checkout: `7ba6a4aacd94b1ca516ab614c1a79c6747892cfd`; canonical Git commit read confirms the identical corrected tree and parents original/corrected above.
- Source PR: three files, 129 additions and two deletions. No core loader, dependency, API or workflow change.

Corrected CLI SHA-256: `c067384572efc6ecc57f0ef242a9eadf84011ed57491cd0e513fcf36ec751215`; Git blob `65665fb40948f40354f14517ffc2ab7f25a9ee16`.

Test file SHA-256: `9bf7e3e9e8750e255a5cfa8491832a90ad8f9a0648499a5b38e5fca721909529`; Git blob `349ff65679720d87b1f7a582632add5938c339e3`. These test bytes are identical in the failing baseline and correction.

## Real failure and correction

At 09:30:46 UTC, an offline reproduction used a valid pinned 262,144-byte JSON fixture and a real Linux nonblocking pipe of capacity 4,096 bytes. The original unbuffered CLI wrote only 4,096 bytes to an initially empty pipe, or zero fixture bytes to a full pipe, while returning exit 0 with no diagnostic. A normally drained blocking pipe received all 262,144 bytes and returned exit 0.

The correction consumes positive short writes until all verified bytes are written. A write returning None or zero progress produces the existing fixed IO_ERROR diagnostic and nonzero exit rather than success or a busy loop. Descriptor blocking mode is not altered. Input validation still precedes every output operation, and final flushing remains checked. Output errors can leave an already-written prefix; the CLI is not transactional.

## Actual local validation

Linux, CPython 3.13.5, unprivileged account. Original source/test text was reconstructed from GitHub and matched its original Git blob hashes before execution. The correction was tested before its equivalent source commit was created.

Command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v`.

| Source | Reported | Passed | Failures | Errors | Skipped | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original production and original tests | 36 | 36 | 0 | 0 | 0 | 14.453 |
| Original production and new tests | 45 | 39 | 6 | 0 | 0 | 15.876 |
| Corrected production and identical new tests | 45 | 45 | 0 | 0 | 0 | 15.427 |

All five filesystem-permission cases actually ran. Nine added output tests include the two real-pipe regressions, successful short writes, no-progress handling, partial-write/flush errors, validation-before-output and complete unbuffered maximum-size emission. Six fail against original production; three are compatibility controls. Whitespace and patch-application checks passed. Exact per-run UTC timestamps were not retained; do not infer them from file modification times. No local package-installation or documented-example execution is claimed.

## Actual hosted validation

[Tests run 41294029069](https://github.com/agamal026/pinned-json/actions/runs/41294029069) completed successfully on the exact checkout above. All three complete decoded logs were inspected, not merely the green workflow badge.

| Actual Python | Job | Passed | Failures/errors | Skipped | Test summary UTC |
| --- | --- | ---: | ---: | ---: | --- |
| 3.10.22 | [124810997622](https://github.com/agamal026/pinned-json/actions/runs/41294029069/job/124810997622) | 45 | 0 | 0 | 09:39:06.4433256 |
| 3.12.15 | [124810997578](https://github.com/agamal026/pinned-json/actions/runs/41294029069/job/124810997578) | 45 | 0 | 0 | 09:38:59.6221883 |
| 3.14.9 | [124810997454](https://github.com/agamal026/pinned-json/actions/runs/41294029069/job/124810997454) | 45 | 0 | 0 | 09:39:02.8118646 |

All jobs used Ubuntu 26.04.1 x64, built and installed the package with `python -m pip install .`, executed `python -m unittest discover -s tests -v`, and passed the unchanged documented example's verify, emit and byte-for-byte cmp steps. Each log lists all 45 cases as ok, including the permission checks and both real-pipe regressions. The package metadata remains 0.1.1; installing a build in CI is not publishing a release. No other platform was validated.

## Preserved local logs

[local-logs.tar.gz](local-logs.tar.gz) contains the complete original-suite, regression-baseline and corrected-suite output, plus redactions.json. Only six occurrences of the temporary checkout prefix in the baseline failure trace were replaced with `[CHECKOUT]`. No log lines were removed or reordered. The redaction record preserves original/published hashes and line counts.

Archive: 2,225 bytes; SHA-256 `8120429d73fb1857b74b104b2aa4f03a80078236f2357327bde07594725e44f1`; Git blob `125148426f0d2eadf1952afd4969a0e4595d61c7`. Its four members are regular files with safe relative paths. Full hosted logs were read through GitHub but are not archived here; canonical job links and the selected facts above retain that limitation.

## Review and scope

Serial automated design and integration review checked progress handling, preservation of validation-before-output, fixed diagnostics and the absence of blocking-mode changes. Native independent subagents were unavailable; no independent or human review is asserted. OpenAI ChatGPT (GPT-6 Astra Pro) generated the implementation, synthetic tests, write-up and review; both source commits carry Assisted-By trailers.

Applied primary-source lesson: [RawIOBase.write](https://docs.python.org/3.10/library/io.html#io.RawIOBase.write) permits short counts and None, so success must depend on complete progress, not merely the absence of an exception. No adoption, financial reward, broader platform support or accepted external-project credit follows from this owned maintenance.
