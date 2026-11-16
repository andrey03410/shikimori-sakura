#!/bin/sh
# Push the working tree to the `preview` branch without touching main's history.
# Prints the commit SHA to load in the browser (see README).
set -e
cd "$(dirname "$0")/.."
python3 build.py --assets-ref preview >/dev/null
git add -A
tree=$(git write-tree)
commit=$(git commit-tree "$tree" -p HEAD -m "preview")
git push -q -f origin "$commit:refs/heads/preview"
git reset -q
python3 build.py >/dev/null   # restore release build in dist/
echo "$commit"
