# Security Policy

## Branch Protection Checklist

The following branch protection rules are configured for the `main` branch:

- [x] Require status checks to pass before merging: `docker-build`, `tests`, `security-scan`
- [x] Require at least 1 approving review before merging
- [x] Require linear history (rebase merging only)
- [x] Require signed commits
- [x] Do not allow bypassing the above settings
- [x] Dismiss stale pull request approvals when new commits are pushed

## Repository Ruleset

- [x] CODEOWNERS: `@tarczyk` owns `*.yml` and `*.yaml` files (see [.github/CODEOWNERS](.github/CODEOWNERS))

## Reporting a Vulnerability

If you discover a security vulnerability, please open a [GitHub Security Advisory](https://github.com/tarczyk/ha-yt-dlp/security/advisories/new) rather than a public issue.

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

We will respond within 7 days and aim to release a fix within 30 days.
