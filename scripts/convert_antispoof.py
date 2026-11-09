"""Converte os pesos MiniFASNet do Silent-Face-Anti-Spoofing (MiniVision, Apache 2.0) para ONNX.

Uso (dentro de um container com torch CPU; ver convert_antispoof.sh):
    python convert_antispoof.py <pasta com os .pth> <pasta de saída>

Não executa código do repositório: a arquitetura vem de minifasnet.py (deste projeto) e os pesos
são lidos com torch.load(weights_only=True), que não desserializa objetos arbitrários.
Gera <saida>/<nome>.onnx e antispoof.json (fator de recorte e tamanho de entrada de cada modelo)
e confere a exportação comparando PyTorch x ONNX Runtime.

Pré-processamento na inferência (igual ao original):
  recorte do rosto com o "scale" do modelo → resize 80x80 → BGR float32 0..255 (sem normalizar) → NCHW.
Saída: logits de 3 classes; softmax; índice 1 = rosto real. O original soma a softmax dos dois modelos.
"""
import json
import os
import sys
from collections import OrderedDict

import numpy as np
import onnxruntime as ort
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minifasnet import build  # noqa: E402

src_dir, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
manifest = {"source": "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing", "license": "Apache-2.0",
            "input": "BGR float32 0..255, NCHW", "classes": ["fake", "real", "fake"], "models": []}


def parse_name(fname):
    """'2.7_80x80_MiniFASNetV2.pth' -> (80, 80, 'MiniFASNetV2', 2.7); '4_0_0_80x80_...' -> scale 4.0"""
    info = fname.split("_")[0:-1]
    h, w = info[-1].split("x")
    model_type = fname.split(".pth")[0].split("_")[-1]
    scale = None if info[0] == "org" else float(info[0])
    return int(h), int(w), model_type, scale


for fname in sorted(os.listdir(src_dir)):
    if not fname.endswith(".pth"):
        continue
    h, w, model_type, scale = parse_name(fname)
    model = build(model_type, conv6_kernel=((h + 15) // 16, (w + 15) // 16))
    state = torch.load(os.path.join(src_dir, fname), map_location="cpu", weights_only=True)
    if next(iter(state)).startswith("module."):
        state = OrderedDict((k[7:], v) for k, v in state.items())
    missing, unexpected = model.load_state_dict(state, strict=True), None
    model.eval()

    onnx_name = fname.replace(".pth", ".onnx")
    onnx_path = os.path.join(out_dir, onnx_name)
    dummy = torch.rand(1, 3, h, w) * 255
    torch.onnx.export(model, dummy, onnx_path, opset_version=12, input_names=["input"], output_names=["logits"],
                      dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, do_constant_folding=True)

    with torch.no_grad():
        ref = model(dummy).numpy()
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    got = sess.run(None, {"input": dummy.numpy().astype(np.float32)})[0]
    diff = float(np.abs(ref - got).max())
    assert diff < 1e-3, f"{fname}: diferença torch x onnx = {diff}"
    print(f"{fname} -> {onnx_name}  scale={scale} input={w}x{h} classes={ref.shape[1]} "
          f"diff={diff:.2e} {os.path.getsize(onnx_path) / 1e6:.2f} MB")
    manifest["models"].append({"file": onnx_name, "type": model_type, "scale": scale, "width": w, "height": h})

with open(os.path.join(out_dir, "antispoof.json"), "w") as f:
    json.dump(manifest, f, indent=2)
print("manifest ok:", [m["file"] for m in manifest["models"]])
