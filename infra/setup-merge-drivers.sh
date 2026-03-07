#!/bin/bash
# Setup custom merge drivers for JSON files
# Run this once after cloning the repo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔧 Setting up custom merge drivers..."

# JSONL merge driver (experiences.jsonl)
git config merge.jsonl-merge.name "JSONL merge driver"
git config merge.jsonl-merge.driver "python3 $REPO_ROOT/tools/git-merge-json.py jsonl %O %A %B"

# JSON array merge driver (diary.json, mini-blog.json, all-creations.json)
git config merge.json-array-merge.name "JSON array merge driver"
git config merge.json-array-merge.driver "python3 $REPO_ROOT/tools/git-merge-json.py array %O %A %B"

# Portal JSON merge driver
git config merge.portal-merge.name "Portal JSON merge driver"
git config merge.portal-merge.driver "python3 $REPO_ROOT/tools/git-merge-json.py portal %O %A %B"

echo "✅ Merge drivers configured!"
echo ""
echo "Configured drivers:"
git config --get-regexp 'merge\..*\.driver' | sed 's/^/  /'
