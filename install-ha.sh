#!/bin/sh
set -eu

BASE_URL="https://raw.githubusercontent.com/collt8080/word-game/master"
DEST_DIR="${PYSCRIPT_DIR:-/config/pyscript}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' 0 HUP INT TERM

if [ -z "${PYSCRIPT_DIR:-}" ] && [ ! -d /config ]; then
    printf '%s\n' "Home Assistant /config was not found. Run this in the HA Terminal add-on."
    exit 1
fi

if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    printf '%s\n' "This installer needs curl or wget."
    exit 1
fi

download_file() {
    source_url="$1"
    destination="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$source_url" -o "$destination"
    else
        wget -q "$source_url" -O "$destination"
    fi
}

FILES="ha_word_relay.py word_store.py stdict_api.py jev_api.py requirements.txt .env.example turso_word_chain/__init__.py turso_word_chain/engine.py turso_word_chain/utils.py"

for file in $FILES; do
    mkdir -p "$TEMP_DIR/$(dirname "$file")"
    download_file "$BASE_URL/$file" "$TEMP_DIR/$file"
done

mkdir -p "$DEST_DIR/turso_word_chain"
for file in $FILES; do
    mkdir -p "$DEST_DIR/$(dirname "$file")"
    cp "$TEMP_DIR/$file" "$DEST_DIR/$file"
done

if [ ! -f "$DEST_DIR/.env" ]; then
    cp "$DEST_DIR/.env.example" "$DEST_DIR/.env"
    printf '%s\n' "Created $DEST_DIR/.env from the example. Add your API keys before starting the game."
else
    printf '%s\n' "Kept existing $DEST_DIR/.env."
fi

printf '%s\n' "Word game files installed in $DEST_DIR. Reload Pyscript, then call pyscript.manage_word_relay."
