#!/usr/bin/env bash
# Fail if the repo tracks anything that must stay off this public repo:
# scraped SLU documentation, snapshots, eval question sets, data dumps,
# archives or secrets.
# Runs in CI on every push and PR; run it locally with:
#   bash scripts/check-no-slu-data.sh
set -euo pipefail

MAX_BYTES=$((1024 * 1024))  # uv.lock is the largest legitimate file (~350 KB)
failed=0

fail() {
  echo "::error file=$1::$2"
  failed=1
}

# The top-level data/ folder, snapshots, archives, dumps, and .env files
# (.env, .env.local, ...). Made-up test fixtures and .env.example are allowed.
forbidden_path='^data/|(^|/)snapshots/|\.(zip|tar|gz|tgz|bz2|xz|7z|rar|parquet|feather|sqlite3?|db|dump|pkl|pickle|npy|npz)$|(^|/)\.env(\..*)?$'
allowed_path='^tests/fixtures/|(^|/)\.env\.example$'

# A scraped page starts with an HTML comment: "Source:" and its Libra docs URL.
# The pattern is split, and this comment leaves the URL out, so this script
# doesn't match itself.
scraped_page='Source:[[:space:]]*https?://docs\.libra\.'"slu\.edu"

# An eval question set (#17) has both of these fields. The real sets stay on
# the team OneDrive; only made-up examples under tests/fixtures/ are allowed.
# (Split like above so this script doesn't match itself.)
eval_answer_field='^[[:space:]-]*expected_'"answer:"
eval_facts_field='^[[:space:]-]*must_'"mention:"

while IFS= read -r -d '' file; do
  [[ -f "$file" ]] || continue
  if [[ "$file" =~ $forbidden_path && ! "$file" =~ $allowed_path ]]; then
    fail "$file" "data, snapshot, archive or .env file must not be committed"
  fi
  size=$(wc -c <"$file")
  if (( size > MAX_BYTES )); then
    fail "$file" "file is $size bytes (limit $MAX_BYTES); large files are usually data"
  fi
  if grep -Iq -E "$scraped_page" "$file"; then
    fail "$file" "looks like a scraped Libra docs page"
  fi
  if [[ ! "$file" =~ $allowed_path ]] && grep -Iq -E "$eval_answer_field" "$file" \
      && grep -Iq -E "$eval_facts_field" "$file"; then
    fail "$file" "looks like an eval question set; keep it on the team OneDrive"
  fi
done < <(git ls-files -z)

if (( failed )); then
  echo "SLU data check failed. Remove the files above (git rm --cached <file>) and add them to .gitignore."
  exit 1
fi
echo "SLU data check passed: no docs, snapshots, eval sets, data or secrets tracked."
