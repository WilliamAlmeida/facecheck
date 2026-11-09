"""Teste da prova de vida. Rodar DENTRO do container (o WSL repassa via stdin):

    docker exec -i facecheck_api python - < scripts/liveness_test.py

1. Desafio de virar a cabeça (máquina de estados) com 1 e 2 lados, ângulos simulados.
2. Camada passiva (PassiveGate) com probabilidades simuladas: real, foto, dúvida.
3. Modelo anti-spoofing carregado e avaliando um rosto real de foto de exemplo.
4. Ponta a ponta: cadastra o rosto, envia a mesma imagem repetidas vezes ao /api/recognize e confere
   que o resultado é coerente com o modo configurado (passive: passa só se o modelo disser "real";
   active: foto parada nunca passa). Remove a pessoa e o evento de teste no final.
"""
import json
import os
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/app")
import cv2  # noqa: E402
import insightface  # noqa: E402
from app.main import (AntiSpoof, Liveness, PassiveGate, LIVENESS, LIVENESS_TIMEOUT, MODELS_DIR,  # noqa: E402
                      SPOOF_FAKE_MAX, SPOOF_FRAMES, SPOOF_REAL_MIN, YAW_TURN)

BASE = "http://localhost:8000"
ok_all = True


def check(cond, msg):
    global ok_all
    print(("  OK    " if cond else "  FALHA ") + msg)
    ok_all &= bool(cond)


# ---------- 1. desafio ----------
print("1) desafio de virar a cabeça")
yaw_for = {"left": YAW_TURN + 0.1, "right": -(YAW_TURN + 0.1)}
for sides in (2, 1):
    lv = Liveness(sides=sides); key = (1, 1); t = 1000.0
    r = lv.update(key, 0.0, t)                              # olha de frente
    seq = list(lv.states[key]["seq"])
    for d in seq:
        t += 0.4
        r = lv.update(key, yaw_for[d], t)
    check(r["status"] == "passed" and len(seq) == sides, f"{sides} lado(s): pessoa real (frente, {', '.join(seq)}) passa")

lv = Liveness(sides=1); t = 2000.0; statuses = set()
for _ in range(60):                                         # foto parada de frente por ~12 s
    statuses.add(lv.update(key, 0.02, t)["status"]); t += 0.2
check("passed" not in statuses and "timeout" in statuses, "1 lado: foto parada de frente nunca passa e expira")

lv = Liveness(sides=1); t = 3000.0; statuses = set()
for _ in range(60):                                         # foto de alguém já virado
    statuses.add(lv.update(key, YAW_TURN + 0.1, t)["status"]); t += 0.2
check("passed" not in statuses, "1 lado: foto parada com rosto virado nunca passa")

lv = Liveness(sides=2); t = 4000.0
lv.update(key, 0.0, t); d = lv.states[key]["seq"][0]
lv.update(key, yaw_for[d], t + 0.3)                         # só um lado
for _ in range(3):
    lv.missed(1, set())                                     # rosto sumiu do quadro
check(key not in lv.states, "rosto saiu do quadro: desafio é reiniciado")

# ---------- 2. camada passiva ----------
print("2) camada passiva (probabilidades simuladas)")
g = PassiveGate(); k = (1, 2); t = 100.0
v = [g.update(k, 0.95, t + i * 0.6)[0] for i in range(SPOOF_FRAMES)]
check(v[-1] == "real" and all(x == "checking" for x in v[:-1]), f"pessoa real: 'checking' até o {SPOOF_FRAMES}º quadro, depois 'real'")
g = PassiveGate()
v = [g.update(k, 0.05, t + i * 0.6)[0] for i in range(SPOOF_FRAMES)]
check(v[-1] == "spoof", "foto/tela: 'spoof' com média baixa")
g = PassiveGate()
mid = (SPOOF_REAL_MIN + SPOOF_FAKE_MAX) / 2
v = [g.update(k, mid, t + i * 0.6)[0] for i in range(SPOOF_FRAMES + 1)]
check(v[-1] == "doubt", f"zona cinzenta ({mid:.2f}): 'doubt' no {SPOOF_FRAMES + 1}º quadro → desafio")
g = PassiveGate()
g.update(k, 0.05, t); v, m, n = g.update(k, 0.95, t + 10)   # quadro antigo fora da janela
check(n == 1 and v == "checking", "quadros fora da janela de tempo são descartados")

# ---------- 3. modelo ----------
print("3) modelo anti-spoofing")
asp = AntiSpoof(MODELS_DIR)
check(asp.loaded and len(asp.models) == 2, f"{len(asp.models)} modelo(s) ONNX carregado(s) de {MODELS_DIR}")


def req(method, path, data=None, headers=None):
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(r) as resp:
        body = resp.read()
        return json.loads(body) if body else None


def post_json(path, obj):
    return req("POST", path, json.dumps(obj).encode(), {"Content-Type": "application/json"})


def post_img(path, jpg):
    b = uuid.uuid4().hex
    body = (b"--" + b.encode() + b'\r\nContent-Disposition: form-data; name="image"; filename="f.jpg"\r\n'
            b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n--" + b.encode() + b"--\r\n")
    return req("POST", path, body, {"Content-Type": "multipart/form-data; boundary=" + b})


img_path = os.path.join(os.path.dirname(insightface.__file__), "data", "images", "t1.jpg")
group = cv2.imread(img_path)
faces = post_img("/api/recognize", cv2.imencode(".jpg", group)[1].tobytes())["faces"]
b = max(faces, key=lambda f: f["bbox"]["w"] * f["bbox"]["h"])["bbox"]
m = int(max(b["w"], b["h"]) * 0.9)
x1, y1 = max(0, b["x"] - m), max(0, b["y"] - m)
x2, y2 = min(group.shape[1], b["x"] + b["w"] + m), min(group.shape[0], b["y"] + b["h"] + m)
crop = group[y1:y2, x1:x2]
crop = cv2.resize(crop, (640, int(640 * crop.shape[0] / crop.shape[1])))
jpg = cv2.imencode(".jpg", crop)[1].tobytes()
t0 = time.perf_counter()
real_group = asp.real_prob(group, b)
ms = (time.perf_counter() - t0) * 1000
an = post_img("/api/analyze", jpg)
print(f"     rosto na foto de grupo original: real={real_group:.3f} ({ms:.0f} ms) · no recorte 640px via /api/analyze: real={an['face'].get('real')}")
check(real_group is not None and 0 <= real_group <= 1 and "real" in an["face"], "modelo responde (0..1) e /api/analyze expõe 'real'")

# ---------- 4. ponta a ponta ----------
print(f"4) ponta a ponta com imagem parada (modo {LIVENESS})")
person = post_json("/api/people", {"name": "Teste Liveness"})
event = post_json("/api/events", {"name": "Teste liveness", "access": "all"})
try:
    en = post_img(f"/api/people/{person['id']}/enroll", jpg)
    check(en.get("ok"), f"foto cadastrada ({en.get('reason') or 'ok'})")
    statuses, reals, t0 = [], [], time.time()
    while time.time() - t0 < LIVENESS_TIMEOUT + 2:
        res = post_img(f"/api/recognize?event_id={event['id']}", jpg)
        for f in res["faces"]:
            if f["match"]:
                lv_ = f["liveness"] or {}
                statuses.append(lv_.get("status") or (f["checkin"] or {}).get("status"))
                if lv_.get("real") is not None:
                    reals.append(lv_["real"])
        time.sleep(0.15)
    detail = req("GET", f"/api/events/{event['id']}")
    checkins = [p for p in detail["people"] if p["checkin_id"]]
    rr = f"{min(reals):.2f}..{max(reals):.2f}" if reals else "-"
    print(f"     {len(statuses)} quadros · real {rr} · status: {sorted(set(map(str, statuses)))} · check-ins: {len(checkins)}")
    if LIVENESS == "passive":
        if "passed" in statuses or "new" in statuses:
            check(len(checkins) == 1 and reals and max(reals) >= SPOOF_REAL_MIN, "modelo disse 'real' → check-in (imagem é foto genuína de pessoa)")
        else:
            check(len(checkins) == 0, "modelo não liberou (spoof/dúvida) → nenhum check-in")
            check("spoof" in statuses or "challenge" in statuses or "timeout" in statuses, "barrado como spoof ou mandado para o desafio")
    else:
        check(len(checkins) == 0 and "timeout" in statuses, "active: imagem parada nunca passa")
finally:
    req("DELETE", f"/api/people/{person['id']}")
    req("DELETE", f"/api/events/{event['id']}")
    print("     pessoa e evento de teste removidos")

print("RESULTADO:", "tudo ok" if ok_all else "HÁ FALHAS")
sys.exit(0 if ok_all else 1)
