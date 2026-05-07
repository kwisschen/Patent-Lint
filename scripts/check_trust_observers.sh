#!/bin/sh
# Trust-observer invariant gate.
#
# Any frontend file that registers a PerformanceObserver on type:
# 'resource' must filter entries through `isTrustRelevantResource` (see
# frontend/src/lib/trustObserver.js for the rule and rationale). Raw
# observer entries include local disk reads (file://), blob/data URIs,
# and failed-offline fetches — none of which are network egress.
# Surfacing them as "network active" violates the no-upload trust copy.
#
# This script runs both as a pre-commit hook (.githooks/pre-commit)
# and as a CI step (.github/workflows/ci.yml) so the gate fires
# regardless of whether someone bypasses the local hook with
# `--no-verify`.
#
# Genuine non-trust observers can opt out by adding the comment
# `// trust-observer-exempt: <reason>` in the same file.
#
# Exit codes:
#   0 — clean (or no observers found)
#   1 — at least one violation; details printed to stderr

set -e

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$REPO_ROOT"

if [ ! -d frontend/src ]; then
    # No frontend tree — nothing to check. (Useful in case the script is
    # invoked from a worktree or partial checkout.)
    exit 0
fi

CANDIDATES=$(grep -rl "new PerformanceObserver" frontend/src 2>/dev/null || true)
VIOLATIONS=""
for file in $CANDIDATES; do
    if ! grep -q "type: *['\"]resource['\"]" "$file"; then
        continue
    fi
    if grep -q "trust-observer-exempt" "$file"; then
        continue
    fi
    if ! grep -q "isTrustRelevantResource" "$file"; then
        VIOLATIONS="$VIOLATIONS    $file
"
    fi
done

if [ -n "$VIOLATIONS" ]; then
    echo "" >&2
    echo "[trust-observers] Invariant violation:" >&2
    printf "%s" "$VIOLATIONS" >&2
    echo "" >&2
    echo "Files that register a PerformanceObserver on type: 'resource'" >&2
    echo "must filter entries through isTrustRelevantResource (see" >&2
    echo "frontend/src/lib/trustObserver.js for the rule and rationale)." >&2
    echo "" >&2
    echo "Fix: import { isTrustRelevantResource } from '../lib/trustObserver'" >&2
    echo "and call .filter(isTrustRelevantResource) on getEntries()." >&2
    echo "" >&2
    echo "If your observer is genuinely not a trust surface, add the comment" >&2
    echo "// trust-observer-exempt: <reason>" >&2
    echo "in the same file." >&2
    echo "" >&2
    exit 1
fi

exit 0
