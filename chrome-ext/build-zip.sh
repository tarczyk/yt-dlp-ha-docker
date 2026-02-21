#!/usr/bin/env bash
# Build a .zip of the Chrome extension for distribution.
# Usage: from repo root: ./chrome-ext/build-zip.sh
#        or from chrome-ext: ./build-zip.sh
# Output: chrome-ext/ha-yt-dlp-chrome-ext-<version>.zip

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(grep -o '"version": *"[^"]*"' manifest.json | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
OUTPUT_ZIP="ha-yt-dlp-chrome-ext-${VERSION}.zip"

# Zip contents of chrome-ext (no parent path, no .git)
rm -f "$OUTPUT_ZIP"
zip -r "$OUTPUT_ZIP" . -x "*.zip" -x ".git*" -x "*.gitkeep" -x "build-zip.sh"

echo "Built: $SCRIPT_DIR/$OUTPUT_ZIP"
