# Buffered stdout shutdown: executed evidence

November 1, 2026. This packet documents [owned-tool PR #2](https://github.com/agamal026/pinned-json/pull/2). It is not an external contribution, release, or claim of human review.

## Exact source

- Base: `7cee22f4fce35e4b278c1169a37d6966987c7802`.
- Test-only baseline: `bf4e340747dab0d9ead9374d0e00790c6b39daeb`, tree `764ce4af5e08698eadb9aa3fcc0f60e2533c58fb`.
- Corrected source: `29f71894f596dcbd0be6474cf7f514cf0023988e`, tree `a7ea3f1c2a3c20e538d59f7f70e805063b1ae642`.
- Actual hosted checkout: `425e57ab9382121ad4361f00a88a6c145aaa6316`. Its canonical Git commit has the identical corrected tree and base/corrected parents above.
- Source comparison: three files, 132 additions, no deletions; CLI, shutdown tests, and changelog only. No core loader, dependency, API, signal-disposition, or workflow change.

Corrected CLI: 3,078 bytes, Git blob `78e581b941ea1d38bc252e39d6f89b37d014d7ed`, SHA-256 `81a593cd5ab16e390ac2b9a154b60faa47fb3c53609ba4793f2b74a5b65cc228`.

New test file: 4,329 bytes, Git blob `c59b4151c014c431923f74b9193d4d79883ef708`, SHA-256 `c017b80dc6f85942d6c19802acc6feb3ec8c41892700b7dd9a7481c77b8edda7`. These test bytes are identical in the failing baseline and correction. Original package source files were reconstructed from GitHub and checked against their canonical Git blob hashes before execution; the corrected CLI blob was read back after publication.

## Reproduction and correction

At 11:39:01 UTC, an offline real-pipe reproduction sent valid, correctly pinned JSON to a closed pipe. The two-byte buffered case returned exit 120 and `IO_ERROR` followed by an interpreter shutdown diagnostic. The same unbuffered case returned exit 1 and only `IO_ERROR`. Larger-write controls were recorded separately; not every failing output stream triggers the buffered-shutdown defect.

Three added regression cases reproduce the actual shutdown problem for a small buffered fixture: a closed pipe, the full Linux output device, and a full nonblocking pipe. Four controls cover the unbuffered pipe/device paths, validation before output, and caller-owned replacement stdout. Assertions inspect complete subprocess termination and exact stderr, rather than mocking away interpreter shutdown. Pipe capacity and reader closure are explicit; no timing sleeps are used.

After an output error, the correction redirects only the process's original stdout buffer descriptor to the null device. Python's final flush can then discard pending bytes without appending an interpreter diagnostic or replacing exit 1 with 120. Caller-owned replacement streams are neither redirected nor closed. The temporary null-device handle is closed deterministically. Existing short-write handling and validation-before-output remain unchanged.

Output remains nontransactional. Standard error and OS resources remain trusted. If the OS cannot provide a usable null sink, cleanup preserves the original I/O error, but a further shutdown diagnostic is still possible. No security boundary bypass or malicious input was investigated.

## Local evidence: focused, not the full suite

Linux, CPython 3.13.5, UID 0. Only the seven new shutdown tests were present in the local reconstruction; the existing 45-case suite was not run locally. No local filesystem-permission, package-installation, or documented-example result is claimed.

Command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v`.

| Execution UTC | Reported | Passed | Failures | Errors | Skipped | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline 11:40:42.573206–11:40:47.872658 | 7 | 4 | 3 | 0 | 0 | Expected failure, exit 1 |
| Initial correction 11:41:17.640711–11:41:22.444231 | 7 | 7 | 0 | 0 | 0 | Success, exit 0 |
| Final exact source 11:42:52.318614–11:42:57.967684 | 7 | 7 | 0 | 0 | 0 | Success, exit 0 |

The initial correction was followed by a whitespace-only blank-line cleanup and the final exact-source run. Test-reported durations were 4.545, 4.132, and 4.862 seconds respectively; receipt intervals include process startup. Complete output and original receipt timestamps are archived, not inferred from file modification times.

## Hosted complete validation

[Tests run 41303208135](https://github.com/agamal026/pinned-json/actions/runs/41303208135) completed successfully on the exact-tree checkout above. All three complete decoded logs were inspected.

| Python | Job | Passed | Failures/errors | Skipped | Summary UTC | Test seconds |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| 3.10.22 | [124838261300](https://github.com/agamal026/pinned-json/actions/runs/41303208135/job/124838261300) | 52 | 0 | 0 | 11:44:39.0678804 | 1.561 |
| 3.12.15 | [124838261477](https://github.com/agamal026/pinned-json/actions/runs/41303208135/job/124838261477) | 52 | 0 | 0 | 11:44:35.1419073 | 1.501 |
| 3.14.9 | [124838261540](https://github.com/agamal026/pinned-json/actions/runs/41303208135/job/124838261540) | 52 | 0 | 0 | 11:44:34.1099732 | 1.676 |

Each Ubuntu 26.04.1 x64 job built and installed the package, ran the full unchanged unittest command, and passed the documented verify/emit/byte-for-byte comparison example. All seven new cases, all 45 previous cases, and all five existing filesystem-permission cases actually executed without skips. Package metadata remains 0.1.1; a CI installation is not a published release. No other platform was validated.

Full hosted logs were inspected through GitHub but are not archived in this packet. The canonical job URLs and selected observations do not imply permanent log availability.

## Archive and integrity

[validation-evidence.tar.gz](validation-evidence.tar.gz): 3,775 bytes, SHA-256 `d5c5b75759736241d1bcc61aa0627027c969ad74dc0a7ca28935d80d308f0eb3`, Git blob `5baf459e74ce587d9986356cb6231d7b74134149`. The returned upload blob matches the local Git blob hash.

The 11 safe regular members preserve all three complete local logs, their three execution receipts, direct reproduction results, source hashes, redaction records, a consolidated receipt, and a SHA-256 manifest. Six occurrences of the temporary checkout prefix in baseline traces were replaced with `[CHECKOUT]`; no lines were deleted or reordered. Original and published hashes and line counts are retained. All manifest entries, archive paths and JSON members were checked. No private settings, credentials, application records, or correspondence are included.

## Review and applied lesson

Serial automated design and integration review checked exact source, original-stream identity, failure isolation, deterministic descriptor cleanup, unchanged success behavior, and the real-process assertions. Native independent subagents were unavailable; no independent or personal human review is claimed.

The [official Python SIGPIPE note](https://docs.python.org/3.11/library/signal.html#note-on-sigpipe) explains that stdout may be flushed again at shutdown and documents null-device redirection. The implementation applies that lesson while adding the caller-owned-stream guard and retaining the existing signal behavior.

OpenAI ChatGPT (GPT-6 Astra Pro) generated the implementation, synthetic tests, analysis, and write-up. Both source commits contain Assisted-By trailers. No adoption, reward eligibility, payment, or accepted external-project credit follows from this owned maintenance.
