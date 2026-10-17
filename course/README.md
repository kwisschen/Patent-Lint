# Course site: learn.patentlint.com

This directory is the course site for "Every Word Counts: The Format and Language of a U.S. Patent Application" (一字千金：美國專利申請文件的格式與用語).
It is deliberately separate from the PatentLint product in `frontend/`.

**Final URL, frozen for the semester:** https://learn.patentlint.com/every-word-counts/
Every route under it is published. `every-word-counts/build.test.js` pins the URL and the route list.

## How it is kept apart from the product

- Its own Vercel project, root directory `course/`, served on its own origin (`learn.patentlint.com`). Separate deploys, rollbacks, headers, and browser storage.
- Its own CI workflow (`.github/workflows/course.yml`), triggered only by changes under `course/`.
- Each project skips builds for commits that do not touch it (`ignoreCommand` in `course/vercel.json` and `frontend/vercel.json`).
- No shared code, styles, packages, or lockfile. The build uses only Node built-ins; `jsdom` is a test-only dependency and Vercel installs nothing.

## Commands (run from `course/`)

- `npm ci && npm test`: build into a temporary directory and check the generated pages.
- `npm run build`: write the site to `course/dist/`.

## Recreating the hosting

- Vercel: import the GitHub repo as a new project, set Root Directory to `course`, leave the framework preset as Other. Everything else comes from `course/vercel.json`.
- Domain: add `learn.patentlint.com` to that project.
- DNS (Cloudflare, zone `patentlint.com`): a `CNAME` record `learn` pointing to the target Vercel shows, proxy status DNS only.

## Editing content

- Page bodies: `every-word-counts/pages.mjs`.
- Interface strings, English and Traditional Chinese: `every-word-counts/strings.json` only. Add every key in both languages.
- Write CJK full-width punctuation as `\u` escapes in `strings.json`.
