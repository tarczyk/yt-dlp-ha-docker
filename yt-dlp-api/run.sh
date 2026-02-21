#!/usr/bin/with-contenv bashio

PORT=$(bashio::config 'port')
export PORT="${PORT:-5000}"

# Subdir under /media (e.g. youtube_downloads → /media/youtube_downloads). Only safe chars.
MEDIA_SUBDIR=$(bashio::config 'media_subdir' 'youtube_downloads')
MEDIA_SUBDIR=$(echo "$MEDIA_SUBDIR" | sed -n 's/^[a-zA-Z0-9_.-]*$/\0/p')
[[ -z "$MEDIA_SUBDIR" ]] && MEDIA_SUBDIR="youtube_downloads"
export MEDIA_SUBDIR
export DOWNLOAD_DIR="/media/${MEDIA_SUBDIR}"
mkdir -p "$DOWNLOAD_DIR"

exec python3 -m flask --app app run --host=0.0.0.0 --port="${PORT}"
