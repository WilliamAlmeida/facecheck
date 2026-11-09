"""Teste ponta a ponta da API (pessoas, eventos com lista, presença). Rodar DENTRO do container:

    docker exec -i facecheck_api python - < scripts/api_test.py

Cria dados com prefixo "ZZ Teste", confere tudo e apaga no final.
"""
import json
import os
import sys
import urllib.request
import uuid

import cv2
import insightface
import psycopg

BASE = "http://localhost:8000"
ok_all = True


def check(cond, msg):
    global ok_all
    print(("  OK    " if cond else "  FALHA ") + msg)
    ok_all &= bool(cond)


def req(method, path, data=None, headers=None, raw=False):
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r) as resp:
            body = resp.read()
            return body.decode("utf-8-sig") if raw else (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        return {"_status": e.code, "_body": e.read().decode()}


def post_json(path, obj, method="POST"):
    return req(method, path, json.dumps(obj).encode(), {"Content-Type": "application/json"})


def post_img(path, jpg):
    b = uuid.uuid4().hex
    body = (b"--" + b.encode() + b'\r\nContent-Disposition: form-data; name="image"; filename="f.jpg"\r\n'
            b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n--" + b.encode() + b"--\r\n")
    return req("POST", path, body, {"Content-Type": "multipart/form-data; boundary=" + b})


# foto de teste: maior rosto da foto de grupo do InsightFace
group = cv2.imread(os.path.join(os.path.dirname(insightface.__file__), "data", "images", "t1.jpg"))
faces = post_img("/api/recognize", cv2.imencode(".jpg", group)[1].tobytes())["faces"]
bb = max(faces, key=lambda f: f["bbox"]["w"] * f["bbox"]["h"])["bbox"]
m = int(max(bb["w"], bb["h"]) * 0.9)
crop = group[max(0, bb["y"] - m):bb["y"] + bb["h"] + m, max(0, bb["x"] - m):bb["x"] + bb["w"] + m]
crop = cv2.resize(crop, (640, int(640 * crop.shape[0] / crop.shape[1])))
JPG = cv2.imencode(".jpg", crop)[1].tobytes()

created = {"people": [], "events": []}
try:
    print("1) migração")
    evs = req("GET", "/api/events?scope=all&limit=500")
    check(all(e["access"] in ("all", "list") for e in evs["items"]), "todos os eventos têm modo de acesso válido")

    print("2) pessoas: criar, editar, amostras")
    a = post_json("/api/people", {"name": "ZZ Teste Ana", "code": " 777 "})
    b = post_json("/api/people", {"name": "ZZ Teste Bruno"})
    created["people"] += [a["id"], b["id"]]
    check(a["code"] == "777", "matrícula salva sem espaços")
    up = post_json(f"/api/people/{a['id']}", {"name": "ZZ Teste Ana Souza", "code": "778"}, "PATCH")
    check(up["name"] == "ZZ Teste Ana Souza" and up["code"] == "778", "nome e matrícula atualizados")
    bad = post_json(f"/api/people/{a['id']}", {"name": "   "}, "PATCH")
    check(bad.get("_status") == 400, "nome vazio é recusado")
    en = [post_img(f"/api/people/{a['id']}/enroll", JPG) for _ in range(2)]
    check(all(isinstance(e.get("sample_id"), int) for e in en), "enroll devolve o id da amostra")
    pa = req("GET", f"/api/people/{a['id']}")
    check(len(pa["samples"]) == 2, "2 amostras cadastradas")
    req("DELETE", f"/api/people/{a['id']}/samples/{pa['samples'][0]['id']}")
    check(len(req("GET", f"/api/people/{a['id']}")["samples"]) == 1, "apagar uma amostra")
    req("DELETE", f"/api/people/{a['id']}/samples")
    check(len(req("GET", f"/api/people/{a['id']}")["samples"]) == 0, "refazer: apagar todas")
    post_img(f"/api/people/{a['id']}/enroll", JPG)
    found = req("GET", "/api/people?q=778")
    check(len(found) == 1 and found[0]["id"] == a["id"], "busca por matrícula")

    print("3) evento com lista")
    ev = post_json("/api/events", {"name": "ZZ Teste Convenção", "event_date": "2099-01-15"})
    created["events"].append(ev["id"])
    check(ev["access"] == "list", "evento novo nasce 'somente a lista'")
    r = post_img(f"/api/recognize?event_id={ev['id']}", JPG)
    f = next((x for x in r["faces"] if x["match"]), None)
    check(f and f["denied"] == "not_listed" and not f["checkin"] and not f["liveness"], "fora da lista: barrado, sem prova de vida")

    res = post_json(f"/api/events/{ev['id']}/participants", {"person_ids": [a["id"], b["id"], 999999]}, "PUT")
    check(res["participants"] == 2, "lista salva (id inexistente ignorado)")
    r = post_img(f"/api/recognize?event_id={ev['id']}", JPG)
    f = next((x for x in r["faces"] if x["match"]), None)
    lv = (f or {}).get("liveness") or {}
    check(f and not f["denied"] and (lv.get("status") in ("checking", "challenge", "passed", "spoof") or f["checkin"]),
          f"na lista: segue para a prova de vida (status {lv.get('status') or (f or {}).get('checkin')})")

    ev2 = post_json("/api/events", {"name": "ZZ Teste Individual", "event_date": "2099-02-01"})
    created["events"].append(ev2["id"])
    r = req("POST", f"/api/events/{ev2['id']}/participants/{a['id']}")
    r2 = req("POST", f"/api/events/{ev2['id']}/participants/{a['id']}")
    d2 = req("GET", f"/api/events/{ev2['id']}")
    check(r.get("listed") and r2.get("listed") and d2["stats"]["expected"] == 1, "incluir uma pessoa na lista (idempotente)")
    req("DELETE", f"/api/events/{ev2['id']}/participants/{a['id']}")
    check(req("GET", f"/api/events/{ev2['id']}")["stats"]["expected"] == 0, "tirar uma pessoa da lista")
    up_list = req("GET", "/api/events?scope=upcoming&q=zz%20teste%20conv")
    check(up_list["total"] == 1 and up_list["items"][0]["participants"] == 2, "busca e filtro 'próximos'")
    past_list = req("GET", "/api/events?scope=past&q=zz%20teste%20conv")
    check(past_list["total"] == 0, "não aparece em 'anteriores'")
    page = req("GET", "/api/events?scope=all&limit=1&offset=0")
    check(len(page["items"]) == 1 and page["total"] >= 1, "paginação (limit/offset)")

    print("4) presença, ausência, desfazer, CSV")
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:   # simula prova de vida aprovada
        conn.execute("DELETE FROM checkins WHERE event_id = %s", (ev["id"],))
        conn.execute("INSERT INTO checkins (event_id, person_id, score) VALUES (%s, %s, 0.9)", (ev["id"], a["id"]))
    d = req("GET", f"/api/events/{ev['id']}")
    check(d["stats"] == {"expected": 2, "present": 1, "absent": 1, "outside": 0}, f"estatísticas {d['stats']}")
    csv_txt = req("GET", f"/api/events/{ev['id']}/export.csv", raw=True)
    lines = csv_txt.strip().splitlines()
    check(len(lines) == 3 and "presente" in csv_txt and "ausente" in csv_txt and "778" in csv_txt, "CSV com presentes, ausentes e matrícula")

    post_json(f"/api/events/{ev['id']}/participants", {"person_ids": [b["id"]]}, "PUT")
    d = req("GET", f"/api/events/{ev['id']}")
    check(d["stats"]["outside"] == 1 and d["stats"]["expected"] == 1, "tirou da lista depois do check-in: conta como 'fora da lista'")
    cid = next(p["checkin_id"] for p in d["people"] if p["checkin_id"])
    req("DELETE", f"/api/events/{ev['id']}/checkins/{cid}")
    d = req("GET", f"/api/events/{ev['id']}")
    check(d["stats"]["present"] == 0 and d["stats"]["outside"] == 0, "desfazer presença")

    print("5) presença manual")
    r = post_json(f"/api/events/{ev['id']}/checkins", {"person_id": a["id"]})
    check(r.get("_status") == 409, "fora da lista: manual recusado (409)")
    r = post_json(f"/api/events/{ev['id']}/checkins", {"person_id": b["id"]})
    check(r.get("method") == "manual" and r.get("id"), "na lista: presença manual registrada")
    r = post_json(f"/api/events/{ev['id']}/checkins", {"person_id": b["id"]})
    check(r.get("_status") == 409, "manual repetido recusado (409)")
    d = req("GET", f"/api/events/{ev['id']}")
    pb = next(p for p in d["people"] if p["person_id"] == b["id"])
    check(pb["method"] == "manual" and pb["score"] is None and d["stats"]["present"] == 1, "detalhe mostra origem 'manual' e conta como presente")
    csv_txt = req("GET", f"/api/events/{ev['id']}/export.csv", raw=True)
    check("origem" in csv_txt.splitlines()[0] and ";manual;" in csv_txt, "CSV traz a coluna origem")

    ed = post_json(f"/api/events/{ev['id']}", {"name": "ZZ Teste Convenção 2", "access": "all"}, "PATCH")
    check(ed["name"] == "ZZ Teste Convenção 2" and ed["access"] == "all", "editar evento (nome e acesso)")
    d = req("GET", f"/api/events/{ev['id']}")
    check(d["stats"]["expected"] >= 2, "aberto a todos: esperados = todos os cadastrados")

    s = req("GET", "/api/stats")
    check(all(k in s for k in ("people", "events", "upcoming", "today", "checkins_today", "low_samples")), "estatísticas gerais")
    h = req("GET", "/api/health")
    check(h["liveness"] in ("passive", "active", "off") and "antispoof" in h, f"health: liveness={h['liveness']} antispoof={h['antispoof']['loaded']}")
finally:
    for eid in created["events"]:
        req("DELETE", f"/api/events/{eid}")
    for pid in created["people"]:
        req("DELETE", f"/api/people/{pid}")
    print("     dados de teste removidos")

print("RESULTADO:", "tudo ok" if ok_all else "HÁ FALHAS")
sys.exit(0 if ok_all else 1)
