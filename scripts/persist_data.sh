#!/usr/bin/env bash
# Retry only the same validated commit; never force-push, rebase or overwrite a concurrent main.
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
base="$(git rev-parse HEAD)"
fetch_main() {
  for n in 1 2 3; do
    if timeout 45s git fetch --no-tags origin main; then return 0; fi
    if [ "$n" -lt 3 ]; then sleep "$((n*5))"; fi
  done
  echo "::error::Unable to verify remote main after bounded network retries." >&2
  return 1
}
result() { echo "changed=$1" >> "$GITHUB_OUTPUT"; }
fetch_main
if [ "$(git rev-parse origin/main)" != "$base" ]; then
  echo "::warning::Main advanced during collection; retain newer committed data."
  result false
  exit 0
fi
git add site/data/
if git diff --cached --quiet; then result false; exit 0; fi
git commit -m "chore(data): refresh models, rankings and resources"
candidate="$(git rev-parse HEAD)"
for n in 1 2 3; do
  if timeout 45s git push origin HEAD:main; then result true; exit 0; fi
  # A lost response may hide a successful push. Read remote state before retrying.
  fetch_main
  remote="$(git rev-parse origin/main)"
  if [ "$remote" = "$candidate" ]; then result true; exit 0; fi
  if [ "$remote" != "$base" ]; then
    echo "::warning::Concurrent main update won; generated snapshot not published."
    result false
    exit 0
  fi
  if [ "$n" -lt 3 ]; then sleep "$((n*5))"; fi
done
echo "::error::Data push failed without a concurrent main update after bounded retries."
exit 1
