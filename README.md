# git-global-log

A global git commit logger that automatically captures detailed commit metadata into a SQLite database for analytics and archival purposes.

## Features

- Automatically logs every commit system-wide using git hooks
- CLI tool for manual operations
- Home Manager module for zero-config setup

## Installation

### With Home Manager

Add this flake to your Home Manager configuration:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager";
    git-global-log.url = "github:tophcodes/git-global-log";
  };

  outputs = { nixpkgs, git-global-log, home-manager, ... }: {
    homeConfigurations.youruser = home-manager.lib.homeManagerConfiguration {
      modules = [
        git-global-log.homeManagerModules.default
        {
          programs.git-global-log = {
            enable = true;
            # Optional: customize database location
            # databasePath = "/custom/path/to/commits.db";
          };
        }
      ];
    };
  };
}
```

### Manual Commands

```bash
# Add a commit to the log
git global-log add HEAD
git global-log add abc123def

# Remove a commit from the log
git global-log drop HEAD
git global-log drop abc123def

# Use custom database location
git global-log add HEAD --db-path /path/to/custom.db
```

## Database Location

Default: `~/.local/share/git-commits/log.sqlite`

Configure with the `databasePath` option in Home Manager.

## Database Schema

The SQLite database contains a single `commits` table with the following fields:

- `commit_hash` - Full commit hash (unique)
- `timestamp` - Unix timestamp from commit
- `repo_path` - Absolute path to git repository
- `commit_message` - Full commit message
- `author_name` - Author name
- `author_email` - Author email
- `branch_name` - Branch name (NULL for detached HEAD)
- `files_changed` - Number of files changed
- `created_at` - When the commit was logged

## Example Queries

```sql
-- Commits in the last 7 days
SELECT * FROM commits
WHERE timestamp > strftime('%s', 'now') - (7 * 24 * 60 * 60)
ORDER BY timestamp DESC;

-- Most active repositories
SELECT repo_path, COUNT(*) as commit_count
FROM commits
GROUP BY repo_path
ORDER BY commit_count DESC
LIMIT 10;

-- Commits per day
SELECT DATE(timestamp, 'unixepoch') as day, COUNT(*) as commits
FROM commits
GROUP BY day
ORDER BY day DESC;
```
