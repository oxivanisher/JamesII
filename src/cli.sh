#!/bin/sh

# Save original working directory
INPWD=$(pwd)

# --- resolve script path (handles symlinks on Linux/macOS) ---
resolve_link() {
    PRG=$1

    # If readlink supports -f (GNU coreutils), just use it
    if command -v readlink >/dev/null 2>&1; then
        if readlink -f "$PRG" >/dev/null 2>&1; then
            readlink -f "$PRG"
            return
        fi
    fi

    # Fallback for macOS / BSD readlink (no -f)
    while [ -L "$PRG" ]; do
        LINK=$(readlink "$PRG")
        case $LINK in
            /*) PRG=$LINK ;;
            *)  PRG=$(dirname "$PRG")/"$LINK" ;;
        esac
    done
    echo "$PRG"
}

SCRIPT_PATH=$(resolve_link "$0")
DIR=$(cd "$(dirname "$SCRIPT_PATH")" && pwd)

cd "$DIR" || exit 1

if [ -f "../venv/bin/python" ]; then
    pwd
    ../venv/bin/python ./cli.py "$@"
else
    ./cli.py "$@"
fi

# Return to original directory
cd "$INPWD" >/dev/null 2>&1
