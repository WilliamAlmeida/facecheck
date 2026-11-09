#!/usr/bin/env bash
# Teste rápido da API (rodar no WSL): health, analyze com imagem sem rosto, e remove a pessoa "Teste UI" se existir.
set -u
BASE="${BASE:-http://localhost:8090}"

echo "--- health"; curl -s "$BASE/api/health"; echo

echo "--- remove pessoa 'Teste UI' (se houver)"
id=$(curl -s "$BASE/api/people" | python3 -c 'import sys,json; print(next((p["id"] for p in json.load(sys.stdin) if p["name"]=="Teste UI"),""))')
if [ -n "$id" ]; then curl -s -o /dev/null -w "delete id=$id: %{http_code}\n" -X DELETE "$BASE/api/people/$id"; else echo "nenhuma"; fi

echo "--- analyze (imagem cinza, sem rosto)"
python3 - "$BASE" <<'EOF'
import sys, uuid, urllib.request, zlib, struct
base = sys.argv[1]
# PNG cinza 64x64 gerado na mão (sem depender de cv2 no host)
w = h = 64
raw = b"".join(b"\x00" + bytes([120]) * (w * 3) for _ in range(h))
def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
b = uuid.uuid4().hex
body = (b"--" + b.encode() + b"\r\nContent-Disposition: form-data; name=\"image\"; filename=\"f.png\"\r\nContent-Type: image/png\r\n\r\n"
        + png + b"\r\n--" + b.encode() + b"--\r\n")
req = urllib.request.Request(base + "/api/analyze", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b})
print(urllib.request.urlopen(req).read().decode())
EOF
