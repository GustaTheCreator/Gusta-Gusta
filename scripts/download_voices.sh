#!/usr/bin/env bash
# Descarrega a voz masculina inglesa do Piper.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/piper"
HF="https://huggingface.co/rhasspy/piper-voices/resolve/main"
mkdir -p "$DIR"
get() { curl -fL --retry 3 -o "$DIR/$2" "$HF/$1"; }
get "en/en_GB/alan/medium/en_GB-alan-medium.onnx" en_GB-alan-medium.onnx
get "en/en_GB/alan/medium/en_GB-alan-medium.onnx.json" en_GB-alan-medium.onnx.json
echo "Voz em $DIR"
