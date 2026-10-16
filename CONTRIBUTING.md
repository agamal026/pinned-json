# Contributing

Useful contributions include reproducible filesystem-boundary bugs, clearer
trust-model documentation, and focused workflow improvements.

Open an issue describing your use case before proposing a large API change.
For a pull request, include a small synthetic regression and run the README's
test command. Tests must stay offline and must not read private datasets.
Describe the checks you ran and disclose material AI assistance.

The initial supported platform is Linux with Python 3.10 or newer. A new
platform needs an explicitly reviewed equivalent to the no-follow descriptor
walk, not an unchecked fallback to ordinary path opening.

Contributions use the MIT license. Preserve third-party attribution where
applicable. Reviews and support are best effort.
