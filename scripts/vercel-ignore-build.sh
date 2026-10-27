#!/bin/sh
# Vercel "Ignored Build Step" for the product and course projects: exit 0 skips
# the build, exit 1 builds. Arguments are the git pathspecs the project depends on.
#
# Vercel clones shallowly. When the last successful deploy is older than the
# clone, a plain `git diff` against VERCEL_GIT_PREVIOUS_SHA exits 128 ("bad
# object"), Vercel counts that as a failed deploy, and the previous SHA then
# never advances (every main merge failed the course deploy this way from
# 2026-10-26). So fetch the commit, and build when it still cannot be found.
P="${VERCEL_GIT_PREVIOUS_SHA:-HEAD^}"
if ! git cat-file -e "$P^{commit}" 2>/dev/null; then
  git fetch --quiet --depth=1000 origin "$P" 2>/dev/null || git fetch --quiet --unshallow 2>/dev/null
fi
git cat-file -e "$P^{commit}" 2>/dev/null || exit 1
git diff --quiet "$P" HEAD -- "$@"
