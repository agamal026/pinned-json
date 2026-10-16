# Security policy

Security fixes target the latest release and `main`. Use
[private vulnerability reporting](https://github.com/agamal026/pinned-json/security/advisories/new)
for a suspected boundary bypass, with a synthetic reproduction and the affected
version. Do not include real secrets, private datasets, or confidential review
records. Reports are handled best effort with no response deadline or bounty.

The expected manifest digest is trusted configuration. Allowing an untrusted
party to replace both a manifest and its expected digest is outside the trust
boundary. The package does not classify content, remove secrets or isolate a
consumer process. See the README for the complete supported scope.
