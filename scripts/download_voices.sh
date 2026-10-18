#!/usr/bin/env bash
# Descarrega a voz masculina portuguesa (Portugal) do Piper.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/piper"
HF="https://huggingface.co/rhasspy/piper-voices/resolve/main"
mkdir -p "$DIR"
get() { curl -fL --retry 3 -o "$DIR/$2" "$HF/$1"; }
get "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx" pt_PT-tugao-medium.onnx
get "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx.json" pt_PT-tugao-medium.onnx.json
echo "Voz em $DIR"
