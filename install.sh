#!/bin/sh
# install.sh — install `auto` on Linux/macOS.
#
# Makes the script executable and symlinks it into ~/.local/bin (override with
# BINDIR=...). Re-running is safe: it just refreshes the symlink.
#
#     ./install.sh
#
set -eu

REPO="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO/auto"
BINDIR="${BINDIR:-$HOME/.local/bin}"
DEST="$BINDIR/auto"

if [ ! -f "$SRC" ]; then
    echo "install: cannot find 'auto' next to install.sh (looked in $REPO)" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "install: python3 is required but was not found on PATH." >&2
    echo "         Install Python 3 and run ./install.sh again." >&2
    exit 1
fi

chmod +x "$SRC"
mkdir -p "$BINDIR"
ln -sf "$SRC" "$DEST"
echo "install: linked $DEST -> $SRC"

# Warn (don't fail) if the install directory is not on PATH yet.
case ":$PATH:" in
    *":$BINDIR:"*)
        ;;
    *)
        echo
        echo "install: $BINDIR is not on your PATH."
        echo "         Add this line to your shell profile (~/.bashrc, ~/.zshrc):"
        echo
        echo "             export PATH=\"$BINDIR:\$PATH\""
        echo
        echo "         Then open a new terminal."
        ;;
esac

echo
echo "Done. Try:  auto claude"
