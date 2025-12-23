#!/usr/bin/env python3
"""
git-global-log: Global git commit logger

Usage:
    git global-log add <commit-hash> [--db-path PATH]
    git global-log drop <commit-hash> [--db-path PATH]
"""

import sys
import sqlite3
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Dict, Any


DEFAULT_DB_PATH = Path.home() / ".local/share/git-commits/log.sqlite"


class GitGlobalLog:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def init_db(self):
        """Create database and schema if it doesn't exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash TEXT NOT NULL UNIQUE,
                    timestamp INTEGER NOT NULL,
                    repo_path TEXT NOT NULL,
                    commit_message TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    branch_name TEXT,
                    files_changed INTEGER NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE INDEX IF NOT EXISTS idx_repo_path ON commits(repo_path);
                CREATE INDEX IF NOT EXISTS idx_timestamp ON commits(timestamp);
                CREATE INDEX IF NOT EXISTS idx_author_email ON commits(author_email);
                CREATE INDEX IF NOT EXISTS idx_branch_name ON commits(branch_name);
                CREATE INDEX IF NOT EXISTS idx_created_at ON commits(created_at);
            """)
            conn.commit()
        finally:
            conn.close()

    def run_git_command(self, args: list[str]) -> str:
        """Run git command and return output"""
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}")

    def is_git_repo(self) -> bool:
        """Check if current directory is in a git repository"""
        try:
            self.run_git_command(["rev-parse", "--git-dir"])
            return True
        except RuntimeError:
            return False

    def get_commit_metadata(self, commit_hash: str) -> Dict[str, Any]:
        """Extract all metadata for a commit"""
        if not self.is_git_repo():
            raise RuntimeError("Not in a git repository")

        # Get canonical commit hash
        canonical_hash = self.run_git_command(["rev-parse", commit_hash])

        # Get timestamp
        timestamp = int(self.run_git_command(["show", "-s", "--format=%ct", canonical_hash]))

        # Get repository path
        repo_path = self.run_git_command(["rev-parse", "--show-toplevel"])

        # Get commit message
        commit_message = self.run_git_command(["show", "-s", "--format=%B", canonical_hash])

        # Get author name
        author_name = self.run_git_command(["show", "-s", "--format=%an", canonical_hash])

        # Get author email
        author_email = self.run_git_command(["show", "-s", "--format=%ae", canonical_hash])

        # Get branch name (may be HEAD for detached state)
        branch_name = self.run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        if branch_name == "HEAD":
            # Detached HEAD state
            branch_name = None

        # Get files changed count
        files_output = self.run_git_command([
            "diff-tree", "--no-commit-id", "--name-only", "-r", canonical_hash
        ])
        files_changed = len(files_output.splitlines()) if files_output else 0

        return {
            "commit_hash": canonical_hash,
            "timestamp": timestamp,
            "repo_path": repo_path,
            "commit_message": commit_message,
            "author_name": author_name,
            "author_email": author_email,
            "branch_name": branch_name,
            "files_changed": files_changed
        }

    def add_commit(self, commit_hash: str) -> int:
        """Add a commit to the database"""
        try:
            metadata = self.get_commit_metadata(commit_hash)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            self.init_db()
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO commits (
                        commit_hash, timestamp, repo_path, commit_message,
                        author_name, author_email, branch_name, files_changed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metadata["commit_hash"],
                    metadata["timestamp"],
                    metadata["repo_path"],
                    metadata["commit_message"],
                    metadata["author_name"],
                    metadata["author_email"],
                    metadata["branch_name"],
                    metadata["files_changed"]
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                # Commit already exists - this is fine (idempotent)
                pass
            finally:
                conn.close()
            return 0
        except sqlite3.Error as e:
            print(f"Error: Database error: {e}", file=sys.stderr)
            print("Check database permissions and disk space", file=sys.stderr)
            return 1

    def drop_commit(self, commit_hash: str) -> int:
        """Remove a commit from the database"""
        if not self.db_path.exists():
            print("No commit log found")
            return 0

        try:
            # Try to resolve to canonical hash if we're in a git repo
            if self.is_git_repo():
                try:
                    canonical_hash = self.run_git_command(["rev-parse", commit_hash])
                except RuntimeError:
                    # Invalid hash, but still try to delete it as-is
                    canonical_hash = commit_hash
            else:
                canonical_hash = commit_hash

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM commits WHERE commit_hash = ?",
                    (canonical_hash,)
                )
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"Removed commit {canonical_hash}")
                else:
                    print(f"Commit {canonical_hash} not found in log")
            finally:
                conn.close()
            return 0
        except sqlite3.Error as e:
            print(f"Error: Database error: {e}", file=sys.stderr)
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="Global git commit logger",
        usage="git global-log <command> [<args>]"
    )
    parser.add_argument("command", choices=["add", "drop"], help="Command to execute")
    parser.add_argument("commit_hash", help="Commit hash to add or drop")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH,
                        help="Path to SQLite database")

    args = parser.parse_args()

    log = GitGlobalLog(args.db_path)

    if args.command == "add":
        return log.add_commit(args.commit_hash)
    elif args.command == "drop":
        return log.drop_commit(args.commit_hash)
    else:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
