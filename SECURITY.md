# Security Policy

## Supported Versions

This is a research / public comparables tool, not a production service.
Only the `main` branch is supported. There are no long-term support branches.

## Reporting a Vulnerability

If you find a security issue (leaked secret in commit history, dependency with known
CVE, data exfiltration path, auth bypass in the backend API), **do not open a public
issue**.

Instead, email the maintainer privately. Use the email address listed on the GitHub
profile of the repository owner, or open a private security advisory:

https://github.com/yuyongkim/10-k-therapy/security/advisories/new

Please include:
- A short description of the issue and its impact
- Repro steps or a proof-of-concept
- The affected file paths / commits
- Any suggested mitigation

You can expect an initial response within 7 days.

## Out of scope

- Issues in `docs/paper_*.md` or other files that are already excluded from the
  repository via `.gitignore`.
- Secrets in `config.yaml` — this file is gitignored. If you see a leaked key in
  history anyway, that IS in scope.
- DoS against the local development server (the project is not designed to be
  exposed publicly).

## Not a substitute for legal or investment advice

This project extracts and normalizes disclosure data. Any use of its outputs in
valuation, investment, or legal contexts is the user's responsibility. See LICENSE.
