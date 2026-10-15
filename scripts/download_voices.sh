#!/usr/bin/env bash
# Descarrega as vozes masculinas do Piper (só precisas disto com TTS_PROVIDER=piper).
# A voz pt_PT tem "ã" no nome, o que parte o descarregador do Piper; por isso vai por URL.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/piper"
HF="https://huggingface.co/rhasspy/piper-voices/resolve/main"
mkdir -p "$DIR"
get() { curl -fL --retry 3 -o "$DIR/$2" "$HF/$1"; }
get "pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx" pt_PT-tugao-medium.onnx
get "pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx.json" pt_PT-tugao-medium.onnx.json
get "en/en_GB/alan/medium/en_GB-alan-medium.onnx" en_GB-alan-medium.onnx
get "en/en_GB/alan/medium/en_GB-alan-medium.onnx.json" en_GB-alan-medium.onnx.json
echo "Vozes em $DIR"
