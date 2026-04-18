# Git hooks

Repository-managed hooks. Git does not run them until you point
`core.hooksPath` here once per clone:

```bash
npm --prefix frontend run setup-hooks
```

(equivalent to `git config core.hooksPath .githooks`).

## Hooks

### `pre-commit` — wheel staleness guard (Phase 9 #39)

Fails the commit if any `src/patentlint/**/*.py` has a newer mtime than
`frontend/public/patentlint-*.whl`. Remediation printed on failure:

```
cd frontend && npm run build:wheel
```

Then re-stage the rebuilt wheel and retry the commit.

No wheel rebuild happens inside the hook — it only compares mtimes. The
tighter byte-level check lives in CI (Phase 9 #40).

## Skipping

If you have a genuine reason to bypass (you almost certainly don't),
`git commit --no-verify` skips all hooks. Walker-relevant commits should
never ship without a matching wheel — the browser executes the wheel,
not the source tree.
