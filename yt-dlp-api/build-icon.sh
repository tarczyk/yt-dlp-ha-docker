#!/usr/bin/env bash
# Generate logo.png and icon.png from icon.svg for the Home Assistant add-on.
# Requires one of: ImageMagick (convert), librsvg (rsvg-convert), or macOS (qlmanage).

set -e
cd "$(dirname "$0")"
SVG=icon.svg

if [[ ! -f "$SVG" ]]; then
  echo "Missing $SVG"
  exit 1
fi

if command -v convert &>/dev/null; then
  convert -background none -resize 128x128 "$SVG" icon.png
  convert -background none -resize 256x256 "$SVG" logo.png
  echo "Generated icon.png (128x128) and logo.png (256x256) with ImageMagick."
elif command -v rsvg-convert &>/dev/null; then
  rsvg-convert -w 128 -h 128 "$SVG" -o icon.png
  rsvg-convert -w 256 -h 256 "$SVG" -o logo.png
  echo "Generated icon.png and logo.png with rsvg-convert."
elif [[ "$(uname)" == Darwin ]] && command -v qlmanage &>/dev/null; then
  qlmanage -t -s 128 -o . "$SVG" 2>/dev/null && mv icon.svg.png icon.png
  qlmanage -t -s 256 -o . "$SVG" 2>/dev/null && mv icon.svg.png logo.png
  echo "Generated icon.png and logo.png with qlmanage (macOS)."
else
  echo "Install ImageMagick (convert), librsvg (rsvg-convert), or use macOS."
  echo "Alternatively, convert icon.svg to PNG at https://cloudconvert.com/svg-to-png"
  echo "  - Save 128x128 as icon.png and 256x256 as logo.png in this directory."
  exit 1
fi
