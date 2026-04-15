# Third-Party Notices

PatentLint is distributed under [PolyForm Noncommercial 1.0.0](LICENSE).
This file lists third-party software that PatentLint depends on at
runtime, along with their respective licenses. Each listed dependency is
used under the terms of its own license; inclusion in this list does not
imply endorsement by the original authors.

Development-only dependencies (test runners, linters, build tools) are
not listed here — they are not shipped with PatentLint to end users.

## Python runtime dependencies

### Browser tier (shipped via the Pyodide wheel)

The browser tier is the in-browser, client-side analysis path at
<https://patentlint.com>. The Pyodide worker fetches these four packages
from PyPI via `micropip` at startup and runs them entirely in WebAssembly.
No PatentLint-originated network activity occurs at analysis time; all
document processing stays in the browser.

| Package | Version constraint | License | Repository |
|---|---|---|---|
| pydantic | >=2.6,<3 | MIT | https://github.com/pydantic/pydantic |
| python-docx | >=1.1,<2 | MIT | https://github.com/python-openxml/python-docx |
| snowballstemmer | >=2.2 | BSD-3-Clause | https://github.com/snowballstem/snowball |
| click | >=8.1,<9 | BSD-3-Clause | https://github.com/pallets/click |

### Docker/CLI tier (optional extras)

These packages are shipped only in the Docker and CLI distributions
(`pip install patentlint[api]` or the `LICENSE-COMMERCIAL`-governed
enterprise Docker image). They are not part of the browser tier.

| Package | Version constraint | License | Purpose |
|---|---|---|---|
| Jinja2 | >=3.1 | BSD-3-Clause | PDF report templating |
| weasyprint | >=62 | BSD-3-Clause | PDF rendering |
| fastapi | >=0.111,<1 | MIT | HTTP API framework |
| uvicorn[standard] | >=0.29,<1 | BSD-3-Clause | ASGI server |
| python-multipart | >=0.0.9 | Apache-2.0 | Multipart form handling |

## Frontend runtime dependencies

The following list is generated from `npx license-checker --production
--direct --json` at commit time. It lists direct production dependencies
of the React/Vite frontend bundle shipped at <https://patentlint.com>.
Transitive dependencies (deep tree) are licensed under compatible
permissive terms; the full transitive list can be regenerated at any time
via `cd frontend && npx license-checker --production`.

| Package | Version | License | Repository |
|---|---|---|---|
| @antfu/install-pkg | 1.1.0 | MIT | https://github.com/antfu/install-pkg |
| @babel/runtime | 7.29.2 | MIT | https://github.com/babel/babel |
| @base-ui/react | 1.3.0 | MIT | https://github.com/mui/base-ui |
| @base-ui/utils | 0.2.6 | MIT | https://github.com/mui/base-ui |
| @braintree/sanitize-url | 7.1.2 | MIT | https://github.com/braintree/sanitize-url |
| @chevrotain/cst-dts-gen | 11.1.2 | Apache-2.0 | https://github.com/Chevrotain/chevrotain |
| @chevrotain/gast | 11.1.2 | Apache-2.0 | https://github.com/Chevrotain/chevrotain |
| @chevrotain/regexp-to-ast | 11.1.2 | Apache-2.0 | https://github.com/Chevrotain/chevrotain |
| @chevrotain/types | 11.1.2 | Apache-2.0 | https://github.com/Chevrotain/chevrotain |
| @chevrotain/utils | 11.1.2 | Apache-2.0 | https://github.com/Chevrotain/chevrotain |
| @floating-ui/core | 1.7.5 | MIT | https://github.com/floating-ui/floating-ui |
| @floating-ui/dom | 1.7.6 | MIT | https://github.com/floating-ui/floating-ui |
| @floating-ui/react-dom | 2.1.8 | MIT | https://github.com/floating-ui/floating-ui |
| @floating-ui/utils | 0.2.11 | MIT | https://github.com/floating-ui/floating-ui |
| @fontsource-variable/geist | 5.2.8 | OFL-1.1 | https://github.com/fontsource/font-files |
| @iconify/types | 2.0.0 | MIT | https://github.com/iconify/iconify |
| @iconify/utils | 3.1.0 | MIT | https://github.com/iconify/iconify |
| @mermaid-js/parser | 1.0.1 | MIT | https://github.com/mermaid-js/mermaid |
| @noble/ciphers | 1.3.0 | MIT | https://github.com/paulmillr/noble-ciphers |
| @noble/hashes | 1.8.0 | MIT | https://github.com/paulmillr/noble-hashes |
| @radix-ui/primitive | 1.1.3 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-collapsible | 1.1.12 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-compose-refs | 1.1.2 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-context | 1.1.2 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-id | 1.1.1 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-presence | 1.1.5 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-primitive | 2.1.3 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-slot | 1.2.4 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-use-controllable-state | 1.2.2 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-use-effect-event | 0.0.2 | MIT | https://github.com/radix-ui/primitives |
| @radix-ui/react-use-layout-effect | 1.1.1 | MIT | https://github.com/radix-ui/primitives |
| @swc/helpers | 0.5.19 | Apache-2.0 | https://github.com/swc-project/swc |
| @types/d3-array | 3.2.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-axis | 3.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-brush | 3.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-chord | 3.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-color | 3.1.3 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-contour | 3.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-delaunay | 6.0.4 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-dispatch | 3.0.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-drag | 3.0.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-dsv | 3.0.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-ease | 3.0.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-fetch | 3.0.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-force | 3.0.10 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-format | 3.0.4 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-geo | 3.1.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-hierarchy | 3.1.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-interpolate | 3.0.4 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-path | 3.1.1 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-polygon | 3.0.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-quadtree | 3.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-random | 3.0.3 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-scale-chromatic | 3.1.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-scale | 4.0.9 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-selection | 3.0.11 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-shape | 3.1.8 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-time-format | 4.0.3 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-time | 3.0.4 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-timer | 3.0.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-transition | 3.0.9 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-zoom | 3.0.8 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3 | 7.4.3 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/geojson | 7946.0.16 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/prop-types | 15.7.15 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react-dom | 18.3.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react | 18.3.28 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/trusted-types | 2.0.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @upsetjs/venn.js | 2.0.0 | MIT | https://github.com/upsetjs/venn.js |
| acorn | 8.16.0 | MIT | https://github.com/acornjs/acorn |
| attr-accept | 2.2.5 | MIT | https://github.com/react-dropzone/attr-accept |
| base64-js | 0.0.8 | MIT | https://github.com/beatgammit/base64-js |
| brotli | 1.3.3 | MIT | https://github.com/devongovett/brotli.js |
| chevrotain-allstar | 0.3.1 | MIT | https://github.com/langium/chevrotain-allstar |
| chevrotain | 11.1.2 | Apache-2.0 | https://github.com/Chevrotain/chevrotain |
| class-variance-authority | 0.7.1 | Apache-2.0 | https://github.com/joe-bell/cva |
| clone | 2.1.2 | MIT | https://github.com/pvorb/node-clone |
| clsx | 2.1.1 | MIT | https://github.com/lukeed/clsx |
| commander | 7.2.0 | MIT | https://github.com/tj/commander.js |
| confbox | 0.1.8 | MIT | https://github.com/unjs/confbox |
| cookie | 1.1.1 | MIT | https://github.com/jshttp/cookie |
| cose-base | 1.0.3 | MIT | https://github.com/iVis-at-Bilkent/cose-base |
| csstype | 3.2.3 | MIT | https://github.com/frenic/csstype |
| cytoscape-cose-bilkent | 4.1.0 | MIT | https://github.com/cytoscape/cytoscape.js-cose-bilkent |
| cytoscape-fcose | 2.2.0 | MIT | https://github.com/iVis-at-Bilkent/cytoscape.js-fcose |
| cytoscape | 3.33.1 | MIT | https://github.com/cytoscape/cytoscape.js |
| d3-array | 3.2.4 | ISC | https://github.com/d3/d3-array |
| d3-axis | 3.0.0 | ISC | https://github.com/d3/d3-axis |
| d3-brush | 3.0.0 | ISC | https://github.com/d3/d3-brush |
| d3-chord | 3.0.1 | ISC | https://github.com/d3/d3-chord |
| d3-color | 3.1.0 | ISC | https://github.com/d3/d3-color |
| d3-contour | 4.0.2 | ISC | https://github.com/d3/d3-contour |
| d3-delaunay | 6.0.4 | ISC | https://github.com/d3/d3-delaunay |
| d3-dispatch | 3.0.1 | ISC | https://github.com/d3/d3-dispatch |
| d3-drag | 3.0.0 | ISC | https://github.com/d3/d3-drag |
| d3-dsv | 3.0.1 | ISC | https://github.com/d3/d3-dsv |
| d3-ease | 3.0.1 | BSD-3-Clause | https://github.com/d3/d3-ease |
| d3-fetch | 3.0.1 | ISC | https://github.com/d3/d3-fetch |
| d3-force | 3.0.0 | ISC | https://github.com/d3/d3-force |
| d3-format | 3.1.2 | ISC | https://github.com/d3/d3-format |
| d3-geo | 3.1.1 | ISC | https://github.com/d3/d3-geo |
| d3-hierarchy | 3.1.2 | ISC | https://github.com/d3/d3-hierarchy |
| d3-interpolate | 3.0.1 | ISC | https://github.com/d3/d3-interpolate |
| d3-path | 3.1.0 | ISC | https://github.com/d3/d3-path |
| d3-polygon | 3.0.1 | ISC | https://github.com/d3/d3-polygon |
| d3-quadtree | 3.0.1 | ISC | https://github.com/d3/d3-quadtree |
| d3-random | 3.0.1 | ISC | https://github.com/d3/d3-random |
| d3-sankey | 0.12.3 | BSD-3-Clause | https://github.com/d3/d3-sankey |
| d3-scale-chromatic | 3.1.0 | ISC | https://github.com/d3/d3-scale-chromatic |
| d3-scale | 4.0.2 | ISC | https://github.com/d3/d3-scale |
| d3-selection | 3.0.0 | ISC | https://github.com/d3/d3-selection |
| d3-shape | 3.2.0 | ISC | https://github.com/d3/d3-shape |
| d3-time-format | 4.1.0 | ISC | https://github.com/d3/d3-time-format |
| d3-time | 3.1.0 | ISC | https://github.com/d3/d3-time |
| d3-timer | 3.0.1 | ISC | https://github.com/d3/d3-timer |
| d3-transition | 3.0.1 | ISC | https://github.com/d3/d3-transition |
| d3-zoom | 3.0.0 | ISC | https://github.com/d3/d3-zoom |
| d3 | 7.9.0 | ISC | https://github.com/d3/d3 |
| dagre-d3-es | 7.0.14 | MIT | https://github.com/tbo47/dagre-es |
| dayjs | 1.11.20 | MIT | https://github.com/iamkun/dayjs |
| delaunator | 5.0.1 | ISC | https://github.com/mapbox/delaunator |
| dfa | 1.2.0 | MIT | https://github.com/devongovett/dfa |
| dompurify | 3.3.3 | (MPL-2.0 OR Apache-2.0) | https://github.com/cure53/DOMPurify |
| fast-deep-equal | 3.1.3 | MIT | https://github.com/epoberezkin/fast-deep-equal |
| file-selector | 2.1.2 | MIT | https://github.com/react-dropzone/file-selector |
| fontkit | 2.0.4 | MIT | https://github.com/foliojs/fontkit |
| hachure-fill | 0.5.2 | MIT | https://github.com/pshihn/hachure-fill |
| html-parse-stringify | 3.0.1 | MIT | https://github.com/henrikjoreteg/html-parse-stringify |
| i18next-browser-languagedetector | 8.2.1 | MIT | https://github.com/i18next/i18next-browser-languageDetector |
| i18next | 25.10.4 | MIT | https://github.com/i18next/i18next |
| iconv-lite | 0.6.3 | MIT | https://github.com/ashtuchkin/iconv-lite |
| internmap | 2.0.3 | ISC | https://github.com/mbostock/internmap |
| js-md5 | 0.8.3 | MIT | https://github.com/emn178/js-md5 |
| js-tokens | 4.0.0 | MIT | https://github.com/lydell/js-tokens |
| katex | 0.16.40 | MIT | https://github.com/KaTeX/KaTeX |
| khroma | 2.1.0 | MIT* | https://github.com/fabiospampinato/khroma |
| langium | 4.2.1 | MIT | https://github.com/eclipse-langium/langium |
| layout-base | 1.0.2 | MIT | https://github.com/iVis-at-Bilkent/layout-base |
| linebreak | 1.1.0 | MIT | https://github.com/devongovett/linebreaker |
| lodash-es | 4.17.23 | MIT | https://github.com/lodash/lodash |
| loose-envify | 1.4.0 | MIT | https://github.com/zertosh/loose-envify |
| lucide-react | 0.460.0 | ISC | https://github.com/lucide-icons/lucide |
| marked | 16.4.2 | MIT | https://github.com/markedjs/marked |
| mermaid | 11.13.0 | MIT | https://github.com/mermaid-js/mermaid |
| mlly | 1.8.2 | MIT | https://github.com/unjs/mlly |
| object-assign | 4.1.1 | MIT | https://github.com/sindresorhus/object-assign |
| package-manager-detector | 1.6.0 | MIT | https://github.com/antfu-collective/package-manager-detector |
| pako | 0.2.9 | MIT | https://github.com/nodeca/pako |
| path-data-parser | 0.1.0 | MIT | https://github.com/pshihn/path-data-parser |
| pathe | 2.0.3 | MIT | https://github.com/unjs/pathe |
| pdfkit | 0.18.0 | MIT | https://github.com/foliojs/pdfkit |
| pdfmake | 0.3.7 | MIT | https://github.com/bpampuch/pdfmake |
| pkg-types | 1.3.1 | MIT | https://github.com/unjs/pkg-types |
| png-js | 1.0.0 | MIT* | https://github.com/devongovett/png.js |
| points-on-curve | 0.2.0 | MIT | https://github.com/pshihn/bezier-points |
| points-on-path | 0.2.1 | MIT | https://github.com/pshihn/points-on-path |
| prop-types | 15.8.1 | MIT | https://github.com/facebook/prop-types |
| react-dom | 18.3.1 | MIT | https://github.com/facebook/react |
| react-dropzone | 14.4.1 | MIT | https://github.com/react-dropzone/react-dropzone |
| react-i18next | 16.6.1 | MIT | https://github.com/i18next/react-i18next |
| react-is | 16.13.1 | MIT | https://github.com/facebook/react |
| react-router-dom | 7.13.2 | MIT | https://github.com/remix-run/react-router |
| react-router | 7.13.2 | MIT | https://github.com/remix-run/react-router |
| react | 18.3.1 | MIT | https://github.com/facebook/react |
| reselect | 5.1.1 | MIT | https://github.com/reduxjs/reselect |
| restructure | 3.0.2 | MIT | https://github.com/devongovett/restructure |
| robust-predicates | 3.0.3 | Unlicense | https://github.com/mourner/robust-predicates |
| roughjs | 4.6.6 | MIT | https://github.com/pshihn/rough |
| rw | 1.3.3 | BSD-3-Clause | https://github.com/mbostock/rw |
| safer-buffer | 2.1.2 | MIT | https://github.com/ChALkeR/safer-buffer |
| sax | 1.6.0 | BlueOak-1.0.0 | https://github.com/isaacs/sax-js |
| scheduler | 0.23.2 | MIT | https://github.com/facebook/react |
| set-cookie-parser | 2.7.2 | MIT | https://github.com/nfriedly/set-cookie-parser |
| sonner | 2.0.7 | MIT | https://github.com/emilkowalski/sonner |
| stylis | 4.3.6 | MIT | https://github.com/thysultan/stylis.js |
| tabbable | 6.4.0 | MIT | https://github.com/focus-trap/tabbable |
| tailwind-merge | 2.6.1 | MIT | https://github.com/dcastil/tailwind-merge |
| tiny-inflate | 1.0.3 | MIT | https://github.com/devongovett/tiny-inflate |
| tinyexec | 1.0.4 | MIT | https://github.com/tinylibs/tinyexec |
| ts-dedent | 2.2.0 | MIT | https://github.com/tamino-martinius/node-ts-dedent |
| tslib | 2.8.1 | 0BSD | https://github.com/Microsoft/tslib |
| tw-animate-css | 1.4.0 | MIT | https://github.com/Wombosvideo/tw-animate-css |
| ufo | 1.6.3 | MIT | https://github.com/unjs/ufo |
| unicode-properties | 1.4.1 | MIT | https://github.com/devongovett/unicode-properties |
| unicode-trie | 2.0.0 | MIT | https://github.com/devongovett/unicode-trie |
| use-sync-external-store | 1.6.0 | MIT | https://github.com/facebook/react |
| uuid | 11.1.0 | MIT | https://github.com/uuidjs/uuid |
| void-elements | 3.1.0 | MIT | https://github.com/pugjs/void-elements |
| vscode-jsonrpc | 8.2.0 | MIT | https://github.com/Microsoft/vscode-languageserver-node |
| vscode-languageserver-protocol | 3.17.5 | MIT | https://github.com/Microsoft/vscode-languageserver-node |
| vscode-languageserver-textdocument | 1.0.12 | MIT | https://github.com/Microsoft/vscode-languageserver-node |
| vscode-languageserver-types | 3.17.5 | MIT | https://github.com/Microsoft/vscode-languageserver-node |
| vscode-languageserver | 9.0.1 | MIT | https://github.com/Microsoft/vscode-languageserver-node |
| vscode-uri | 3.1.0 | MIT | https://github.com/microsoft/vscode-uri |
| xmldoc | 2.0.3 | MIT | https://github.com/nfarina/xmldoc |

## License compatibility note

All runtime dependencies listed above are licensed under permissive
terms (MIT, BSD-*, Apache-2.0, ISC, 0BSD, Unlicense, OFL-1.1, or
BlueOak-1.0.0). No runtime dependency is licensed under GPL, AGPL, SSPL,
or any other strong copyleft license. PatentLint's PolyForm Noncommercial
1.0.0 license is downstream-compatible with all listed dependencies.

DOMPurify is dual-licensed under MPL-2.0 and Apache-2.0; PatentLint
elects to use it under the Apache-2.0 terms of that dual offer.

## Attribution

Copyright notices and license texts for each listed dependency are
preserved in the `node_modules` directory of the frontend development
environment and in the Python package metadata for the wheel
dependencies. Users wishing to inspect the full license text of any
dependency can do so via `pip show <package>` (Python) or `cat
node_modules/<package>/LICENSE` (frontend).

---

Generated: 2026-04-15
PatentLint is © 2025 Christopher Chen. All rights reserved.
