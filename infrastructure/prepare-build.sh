#!/usr/bin/env bash
# Prépare la Lambda Layer (code partagé + FFmpeg) avant sam build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAYER="$ROOT/backend/layer"
PYTHON_DIR="$LAYER/python"
BIN_DIR="$LAYER/bin"

FFMPEG_TAR="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

mkdir -p "$PYTHON_DIR" "$BIN_DIR"

cp "$ROOT/backend/shared/utils.py" "$PYTHON_DIR/"
cp "$ROOT/backend/shared/video_processor.py" "$PYTHON_DIR/"

if [[ ! -x "$BIN_DIR/ffmpeg" ]]; then
  echo "Téléchargement de FFmpeg pour Lambda..."
  tmp="$(mktemp -d)"
  curl -sL "$FFMPEG_TAR" -o "$tmp/ffmpeg.tar.xz"
  tar -xJf "$tmp/ffmpeg.tar.xz" -C "$tmp"
  static_dir="$(find "$tmp" -maxdepth 1 -type d -name 'ffmpeg-*-static' | head -1)"
  cp "$static_dir/ffmpeg" "$static_dir/ffprobe" "$BIN_DIR/"
  chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"
  rm -rf "$tmp"
  echo "FFmpeg installé dans backend/layer/bin/"
fi

echo "Layer prête."
