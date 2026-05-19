# Security Policy

## Architecture

PatentLint analyzes patent drafts entirely in the user's browser via a Python-to-WebAssembly engine (Pyodide). The patent draft content is never transmitted off the user's device — there is no analysis server, no database, no logging of file content. See [patentlint.com/security](https://patentlint.com/security) for the airplane-mode verification demo.

## Supported Versions

The hosted application at [patentlint.com](https://patentlint.com) tracks `main` and is the canonical surface. Tagged releases are issued ad-hoc; users running the source-available / Docker tier should upgrade to the latest release for the current security posture.

## Reporting a Vulnerability

If you find a security issue, please **email [kwisschen@gmail.com](mailto:kwisschen@gmail.com)** rather than opening a public GitHub issue. A short description and reproduction steps are appreciated.

Reports are read directly by the maintainer. There is no bug-bounty program. Coordinated disclosure is preferred — a brief acknowledgement and an estimated remediation timeline will be sent within a reasonable window of receipt.

The following classes of report are in scope:

- Client-side vulnerabilities in the web application (XSS, content-injection, etc.)
- Exfiltration paths that would route patent draft content off the user's device
- Supply-chain risks affecting the bundled Pyodide wheel or third-party dependencies
- Hosting-layer misconfigurations on patentlint.com (e.g., headers, TLS)

The following are explicitly out of scope:

- Findings against forks, mirrors, or unrelated deployments
- Reports that require disabling browser security features (e.g., self-XSS via DevTools paste)
- Theoretical issues without a working proof-of-concept
- Reports against third-party services (Vercel, jsDelivr, GitHub) — please report directly to those providers

## Disclosure of Voluntary Diagnostic Reports

When a user clicks "Send anonymously" on a check finding, a de-identified diagnostic payload is forwarded to a GitHub Issues tracker on the public repository [kwisschen/Patent-Lint](https://github.com/kwisschen/Patent-Lint). The payload is sanitized in the browser before transmission — no IP, no email, no browser headers, no full claim text. See the [Privacy Policy § 6](https://patentlint.com/privacy) for the full disclosure.

If you believe the de-identification path leaks information that could be linked back to a draft or a user, please report it under the vulnerability-reporting flow above.
