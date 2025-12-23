#!/usr/bin/env bash
# Global git commit logger
# Automatically logs all commits to SQLite database

set -euo pipefail

if ! git-global-log add HEAD 2>/dev/null; then
    commit_hash=$(git rev-parse HEAD)
    echo "Warning: Failed to log commit to global database" >&2
    echo "To manually add this commit, run: git global-log add $commit_hash" >&2
fi

# Always exit successfully to never block commits
exit 0
