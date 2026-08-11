#!/usr/bin/env bash
#
# workflow-automator — one-liner installer (Linux / macOS)
#
# Downloads the latest from GitHub, installs it, then hands off to the
# interactive wizard (daemon setup + summary).  Nothing is copied from the
# script you just ran — everything comes fresh from GitHub, so you always
# get the newest version.
#
set -euo pipefail

REPO="aakashjabraham-hue/workflow-automator"
BRANCH="master"
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/workflow-automator"
BIN="${HOME}/.local/bin"

command -v curl >/dev/null 2>&1 || { echo "  ✗  curl is required."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "  ✗  python3 is required."; exit 1; }

mkdir -p "$BASE" "$BIN"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "  ⬇️   Downloading workflow-automator…"
curl -# -fL -H "Cache-Control: no-cache" \
  "https://codeload.github.com/${REPO}/tar.gz/refs/heads/${BRANCH}?v=$(date +%s)" \
  -o "$TMP/wa.tgz"

echo "  📦  Extracting…"
mkdir -p "$TMP/tree"
tar -xzf "$TMP/wa.tgz" -C "$TMP/tree" --strip-components=1

rm -rf "$BASE/current"
mkdir -p "$BASE"
mv "$TMP/tree" "$BASE/current"

# Write the launcher shim next to the app tree.
python3 - "$BASE/current" "$BIN" <<'PYEOF'
import os, sys
app_dir, bin_dir = sys.argv[1], sys.argv[2]
shim = f"""#!/usr/bin/env python3
import os, sys
sys.path.insert(0, {app_dir!r})
from src.main import main
sys.exit(main())
"""
path = os.path.join(bin_dir, "workflow-automator")
with open(path, "w", encoding="utf-8") as f:
    f.write(shim)
os.chmod(path, 0o755)
print(f"  ✅  Installed launcher → {path}")
PYEOF

echo

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "  💡  Add $BIN to your PATH first (or open a new terminal):"
     echo "      export PATH=\"$BIN:\$PATH\"" ;;
esac

echo
echo "  🚀  Running the setup wizard…"
exec "$BIN/workflow-automator" install --skip-download