{
  description = "Global git commit logger with SQLite backend";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        packages = {
          default = self.packages.${system}.git-global-log;

          git-global-log = pkgs.stdenv.mkDerivation {
            pname = "git-global-log";
            version = "0.1.0";

            src = ./src;

            buildInputs = [pkgs.python3];

            installPhase = ''
              mkdir -p $out/bin
              cp git-global-log.py $out/bin/git-global-log
              chmod +x $out/bin/git-global-log

              # Patch shebang to use Nix's python3
              patchShebangs $out/bin/git-global-log
            '';

            meta = with pkgs.lib; {
              description = "Global git commit logger with SQLite backend";
              license = licenses.mit;
              maintainers = [];
              platforms = platforms.unix;
            };
          };
        };

        # Development shell
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python3
            git
            sqlite
          ];
        };
      }
    )
    // {
      # Home Manager module (system-agnostic)
      homeManagerModules.default = {
        config,
        lib,
        pkgs,
        ...
      }:
        with lib; let
          cfg = config.programs.git-global-log;
        in {
          options.programs.git-global-log = {
            enable = mkEnableOption "git global commit logger";

            package = mkOption {
              type = types.package;
              default = self.packages.${pkgs.stdenv.hostPlatform.system}.git-global-log;
              description = "The git-global-log package to use";
            };

            databasePath = mkOption {
              type = types.str;
              default = "${config.home.homeDirectory}/.local/share/git-commits/log.sqlite";
              description = "Path to the SQLite database";
            };
          };

          config = mkIf cfg.enable {
            home.packages = [cfg.package];

            # Install the post-commit hook using programs.git.hooks
            programs.git.hooks.post-commit = pkgs.writeShellScript "git-global-log-post-commit" ''
              set -euo pipefail

              if ! git global-log add HEAD --db-path "${cfg.databasePath}" 2>/dev/null; then
                  commit_hash=$(git rev-parse HEAD)
                  echo "Warning: Failed to log commit to global database" >&2
                  echo "To manually add this commit, run: git global-log add $commit_hash --db-path '${cfg.databasePath}'" >&2
              fi

              exit 0
            '';
          };
        };
    };
}
