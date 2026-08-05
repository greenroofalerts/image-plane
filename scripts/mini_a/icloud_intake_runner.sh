#!/bin/zsh
set -eu

MINI_B_HOST="${MINI_B_HOST:-macminib@macminibs-mac-mini}"
MINI_B_ROOT="${MINI_B_ICLOUD_ROOT:-/Users/macminib/icloud-originals/photos}"
LOCAL_ROOT="${ICLOUD_INTAKE_ROOT:-$HOME/image-plane/incoming/icloud}"
SCRIPT="$(cd "$(dirname "$0")/../mini_b" && pwd)/export_icloud_photos.py"
CHECK_ONLY=0

if [[ "${1:-}" == "--check-only" ]]; then
  CHECK_ONLY=1
  shift
fi

if [[ $# -ne 0 ]]; then
  print -u2 "Use --check-only or no options."
  exit 2
fi

mkdir -p "$LOCAL_ROOT/source"
ssh "$MINI_B_HOST" "test -f '$MINI_B_ROOT/manifest.jsonl'"
rsync -a --partial "$MINI_B_HOST:$MINI_B_ROOT/manifest.jsonl" "$LOCAL_ROOT/source/manifest.jsonl"
rsync -a --partial "$MINI_B_HOST:$MINI_B_ROOT/assets/" "$LOCAL_ROOT/source/assets/"
ssh "$MINI_B_HOST" "sqlite3 \"\$HOME/Pictures/Photos Library.photoslibrary/database/Photos.sqlite\" \"SELECT ZUUID FROM ZASSET WHERE ZKIND=0 AND COALESCE(ZTRASHEDSTATE,0)=0 AND COALESCE(ZHIDDEN,0)=0 ORDER BY ZUUID;\"" > "$LOCAL_ROOT/source/eligible-item-ids.txt"

ARGS=(mirror --source-root "$LOCAL_ROOT/source" --destination-root "$LOCAL_ROOT" --expected-items-file "$LOCAL_ROOT/source/eligible-item-ids.txt")
EXCLUSIONS="$HOME/image-plane/grind/excluded_moves_20260728.jsonl"
if [[ -f "$EXCLUSIONS" ]]; then
  ARGS+=(--exclusion-file "$EXCLUSIONS")
fi
PICTURE_HASHES="${ICLOUD_PICTURE_HASH_FILE:-$HOME/image-plane/grind/excluded_picture_hashes_20260801.jsonl}"
if [[ -f "$PICTURE_HASHES" ]]; then
  ARGS+=(--picture-hash-file "$PICTURE_HASHES")
fi
if [[ $CHECK_ONLY -eq 1 ]]; then
  ARGS+=(--check-only)
else
  ARGS+=(--write-complete)
fi

/usr/bin/python3 "$SCRIPT" "${ARGS[@]}"
