#!/bin/zsh
set -eu

ROOT="${ICLOUD_EXPORT_ROOT:-$HOME/icloud-originals/photos}"
DATABASE="${ICLOUD_PHOTOS_DB:-$HOME/Pictures/Photos Library.photoslibrary/database/Photos.sqlite}"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/export_icloud_photos.py"

mkdir -p "$ROOT"
/usr/bin/python3 "$SCRIPT" export --database "$DATABASE" --root "$ROOT" "$@" 2>&1 | tee -a "$ROOT/export.log"
