# Commercial License

PatentLint is licensed under [PolyForm Noncommercial 1.0.0](LICENSE) for
noncommercial use. Any use by a commercial enterprise — including internal
use by a law firm, corporate legal department, or legal tech vendor —
requires a separate commercial license.

## Use that requires a commercial license

- A law firm running PatentLint to review draft patent applications for
  client matters, billable or otherwise.
- A corporate IP department deploying PatentLint internally to review
  in-house patent applications.
- A legal tech vendor bundling, integrating, or redistributing PatentLint
  in a commercial product.
- Hosted-service resale of PatentLint functionality.
- Any use "for the benefit of a commercial enterprise" as defined in
  PolyForm Noncommercial 1.0.0.

## Use that does not require a commercial license

- Individual practitioners evaluating PatentLint on personal or
  non-billable work.
- Academic and research use.
- Personal study, hobby projects, and amateur pursuits.
- Reviewing the source code for education, evaluation, or portfolio
  review.
- Use by charitable organizations, educational institutions, public
  research organizations, public safety or health organizations,
  environmental protection organizations, or government institutions, per
  the "Noncommercial Organizations" clause of the license.

## Zero-trust architecture is preserved under commercial licensing

PatentLint's core architectural commitment is that user documents never
leave the browser. The Pyodide wheel runs entirely client-side, performs
zero network requests at analysis time, and has no telemetry, no license
validation server, and no call-home mechanism. See the Security page at
<https://patentlint.com/security> for the live demonstration.

**Commercial licenses do not change this.** The enterprise Docker
distribution is also air-gappable, requires no license server, and
performs no runtime license checks. Commercial licensing is an offline
contractual agreement between Christopher Chen and the licensee, not a
runtime enforcement mechanism. Law firms and corporate legal departments
evaluating PatentLint under IT security review can confirm:

- No network calls at runtime (browser or Docker)
- No license key verification against an external service
- No usage reporting or phone-home telemetry
- Source-visible wheel with SPDX-registered license metadata

## Requesting a commercial license

Commercial licenses are available directly from Christopher Chen, sole
copyright holder. Terms are negotiated per customer and typically cover:

- Named-entity use rights with seat or site scope
- Support SLA and update cadence
- Indemnification
- A commercial grant that supersedes PolyForm Noncommercial 1.0.0 for the
  licensed distribution

To request a commercial license, contact:

[kwisschen@gmail.com](mailto:kwisschen@gmail.com)

## Enterprise Docker distribution

The enterprise Docker distribution of PatentLint ships under a separate
commercial agreement that supersedes PolyForm Noncommercial 1.0.0 for
that specific distribution. Enterprise customers receive a
`LICENSE-COMMERCIAL` file governing their deployment, with terms specific
to their seat count, support level, and permitted use.

---

Copyright (c) 2025 Christopher Chen. All rights reserved.
