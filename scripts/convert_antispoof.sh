#!/usr/bin/env bash
# Converte os modelos anti-spoofing (Silent-Face, MiniVision, Apache 2.0) para ONNX num container
# descartável com PyTorch CPU. Só os arquivos de pesos (.pth) do repositório são usados, lidos com
# weights_only=True; nenhum código dele é executado. O projeto entra só-leitura; a saída vai para app/models.
# Rodar no WSL: bash scripts/convert_antispoof.sh   (só é preciso repetir para atualizar os modelos)
set -euo pipefail
cd "$(dirname "$0")/.."
PROJ="$(pwd)"
mkdir -p "$PROJ/app/models"
docker run --rm -v "$PROJ:/w:ro" -v "$PROJ/app/models:/out" python:3.11-slim bash -c '
  set -e
  apt-get update -qq >/dev/null && apt-get install -y -qq git >/dev/null
  pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.5.1
  pip install -q "numpy<2" onnx onnxruntime
  git clone -q --depth 1 https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git /repo
  echo "commit: $(git -C /repo rev-parse HEAD)"
  python /w/scripts/convert_antispoof.py /repo/resources/anti_spoof_models /out
'
ls -la "$PROJ/app/models"
