#!/usr/bin/env bash
# Idempotent bootstrap for the image-plane Cloud Agent dev environment.
#
# Layers:
#   1. system packages: python venv/pip + zstd (to unpack the ollama runtime)
#   2. project virtualenv with the [heic,dev] extras (Pillow, pillow-heif, pytest)
#   3. a Linux `sips` compatibility shim so the macOS-only iCloud-intake
#      picture-hash tests run here too (no application code is changed)
#   4. the standalone ollama runtime for the optional captioning stage
#
# Safe to re-run: every step checks before it acts.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "[install] 1/4 system packages"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends python3-venv python3-pip zstd curl ca-certificates

echo "[install] 2/4 python virtualenv + package (heic, dev extras)"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e ".[heic,dev]"

echo "[install] 3/4 sips compatibility shim"
VENV_PY="$REPO_DIR/.venv/bin/python"
SHIM="$REPO_DIR/.cursor/bin/sips"
chmod +x "$SHIM"
sudo tee /usr/local/bin/sips >/dev/null <<EOF
#!/usr/bin/env bash
exec "$VENV_PY" "$SHIM" "\$@"
EOF
sudo chmod +x /usr/local/bin/sips

echo "[install] 4/4 ollama runtime (optional captioning stage)"
OLLAMA_VERSION="v0.32.15"
if [ ! -x bin/bin/ollama ]; then
  mkdir -p bin
  if curl -fsSL "https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/ollama-linux-amd64.tar.zst" -o /tmp/ollama.tar.zst; then
    tar --use-compress-program=unzstd -xf /tmp/ollama.tar.zst -C bin
    rm -f /tmp/ollama.tar.zst
    echo "[install]     ollama $(bin/bin/ollama --version 2>/dev/null | tail -1)"
  else
    echo "[install]     WARNING: ollama download failed; the caption stage stays unavailable" >&2
    echo "[install]              until you install it. Ingest/dedup/status and tests are unaffected." >&2
  fi
fi

echo "[install] done — run the suite with: .venv/bin/python -m pytest tests/ -q"
