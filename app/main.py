"""FaceCheck - protótipo de registro de presença por reconhecimento facial.

API FastAPI: pessoas (embeddings ArcFace via InsightFace), eventos com lista de participantes,
check-ins com prova de vida ativa. Busca vetorial com pgvector no Postgres.
"""
import csv
import io
import os
import random
import threading
import time
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from insightface.app import FaceAnalysis

DATABASE_URL = os.environ["DATABASE_URL"]
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.45"))
MIN_FACE_PX = int(os.getenv("MIN_FACE_PX", "60"))
APP_TZ = os.getenv("APP_TZ", "America/Sao_Paulo")              # "hoje" e horários do CSV
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Prova de vida: "passive" (padrão: modelo anti-spoofing em todo quadro, desafio só na dúvida),
# "active" (sempre desafio de virar a cabeça) ou "off"
LIVENESS = os.getenv("LIVENESS", "passive").lower()
YAW_FRONT = float(os.getenv("LIVENESS_YAW_FRONT", "0.12"))   # |yaw| abaixo disso = de frente
YAW_TURN = float(os.getenv("LIVENESS_YAW_TURN", "0.25"))     # |yaw| acima disso = virou (~25°)
LIVENESS_TIMEOUT = float(os.getenv("LIVENESS_TIMEOUT", "8"))  # segundos para completar o desafio
LIVENESS_SIDES = int(os.getenv("LIVENESS_SIDES", "1" if LIVENESS == "passive" else "2"))  # lados a virar
LIVENESS_MAX_MISSES = 3                                       # quadros seguidos sem o rosto → reinicia
LIVENESS_MATCH_SLACK = 0.12                                   # tolerância de similaridade com o rosto virado
# camada passiva (Silent-Face MiniFASNet): média da probabilidade "real" nos últimos quadros
SPOOF_REAL_MIN = float(os.getenv("SPOOF_REAL_MIN", "0.80"))  # média ≥ → pessoa real, passa direto
SPOOF_FAKE_MAX = float(os.getenv("SPOOF_FAKE_MAX", "0.40"))  # média ≤ → foto/tela, barrado
SPOOF_FRAMES = int(os.getenv("SPOOF_FRAMES", "2"))            # quadros mínimos para decidir
SPOOF_WINDOW = 3.0                                            # segundos: janela dos quadros considerados
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

TODAY = "(now() AT TIME ZONE %(tz)s)::date"

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS people (
    id serial PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS face_embeddings (
    id serial PRIMARY KEY,
    person_id int NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    embedding vector(512) NOT NULL,
    det_score real,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS events (
    id serial PRIMARY KEY,
    name text NOT NULL,
    event_date date NOT NULL DEFAULT current_date,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS checkins (
    id serial PRIMARY KEY,
    event_id int NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id int NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    score real,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, person_id)
);
-- v2: matrícula, controle de acesso por evento e lista de participantes
ALTER TABLE people ADD COLUMN IF NOT EXISTS code text;
-- eventos antigos continuam abertos a todos; novos nascem com lista
ALTER TABLE events ADD COLUMN IF NOT EXISTS access text NOT NULL DEFAULT 'all';
ALTER TABLE events ALTER COLUMN access SET DEFAULT 'list';
CREATE TABLE IF NOT EXISTS event_people (
    event_id int NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id int NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, person_id)
);
CREATE INDEX IF NOT EXISTS event_people_person_idx ON event_people (person_id);
-- v3: origem da presença (face = reconhecimento, manual = registrada no admin)
ALTER TABLE checkins ADD COLUMN IF NOT EXISTS method text NOT NULL DEFAULT 'face';
CREATE INDEX IF NOT EXISTS face_embeddings_person_idx ON face_embeddings (person_id);
"""

pool: ConnectionPool | None = None
face_app: FaceAnalysis | None = None


class AntiSpoof:
    """Prova de vida passiva: MiniFASNet (Silent-Face-Anti-Spoofing, MiniVision, Apache 2.0) em ONNX.
    Recorta o rosto com o fator de cada modelo, 80x80, BGR 0..255, soma a softmax dos modelos.
    Devolve a probabilidade média de "rosto real" (índice 1)."""

    def __init__(self, models_dir: str):
        import json
        import onnxruntime as ort
        self.models = []
        manifest = os.path.join(models_dir, "antispoof.json")
        if not os.path.exists(manifest):
            return
        with open(manifest) as f:
            for m in json.load(f)["models"]:
                path = os.path.join(models_dir, m["file"])
                if not os.path.exists(path):
                    continue
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                sess = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
                self.models.append((sess, float(m["scale"]), int(m["width"]), int(m["height"])))

    @property
    def loaded(self) -> bool:
        return bool(self.models)

    @staticmethod
    def _crop(img, bbox, scale, out_w, out_h):
        src_h, src_w = img.shape[:2]
        x, y, bw, bh = bbox["x"], bbox["y"], max(1, bbox["w"]), max(1, bbox["h"])
        scale = min((src_h - 1) / bh, (src_w - 1) / bw, scale)
        nw, nh = bw * scale, bh * scale
        cx, cy = x + bw / 2, y + bh / 2
        l, t, r, b = cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2
        if l < 0:
            r -= l; l = 0
        if t < 0:
            b -= t; t = 0
        if r > src_w - 1:
            l -= r - src_w + 1; r = src_w - 1
        if b > src_h - 1:
            t -= b - src_h + 1; b = src_h - 1
        l, t, r, b = int(l), int(t), int(r), int(b)
        crop = img[t:b + 1, l:r + 1]
        return cv2.resize(crop, (out_w, out_h))

    def real_prob(self, img, bbox) -> float | None:
        if not self.models:
            return None
        total = np.zeros(3, dtype=np.float64)
        for sess, scale, w, h in self.models:
            x = self._crop(img, bbox, scale, w, h).astype(np.float32).transpose(2, 0, 1)[None]
            logits = sess.run(None, {"input": x})[0][0][:3]
            e = np.exp(logits - logits.max())
            total += e / e.sum()
        return float(total[1] / len(self.models))


class PassiveGate:
    """Decide por pessoa/evento com a média dos últimos quadros: real, spoof, doubt ou checking."""

    def __init__(self):
        self.lock = threading.Lock()
        self.hist: dict[tuple, list] = {}

    def update(self, key, real: float, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            h = [(t, r) for t, r in self.hist.get(key, []) if now - t <= SPOOF_WINDOW]
            h.append((now, real))
            self.hist[key] = h[-5:]
            scores = [r for _, r in self.hist[key]]
        n, mean = len(scores), sum(scores) / len(scores)
        if n < SPOOF_FRAMES:
            verdict = "checking"
        elif mean >= SPOOF_REAL_MIN:
            verdict = "real"
        elif mean <= SPOOF_FAKE_MAX:
            verdict = "spoof"
        elif n >= SPOOF_FRAMES + 1:
            verdict = "doubt"
        else:
            verdict = "checking"
        return verdict, round(mean, 3), n

    def clear(self, key):
        with self.lock:
            self.hist.pop(key, None)


antispoof: AntiSpoof | None = None
passive = PassiveGate()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global pool, face_app, antispoof
    # Schema primeiro (register_vector precisa do tipo "vector" existir)
    import psycopg
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(SCHEMA)
    pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, kwargs={"row_factory": dict_row},
                          configure=register_vector, open=True)
    face_app = FaceAnalysis(name="buffalo_l",
                            allowed_modules=["detection", "recognition"],
                            providers=["CPUExecutionProvider"])
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    antispoof = AntiSpoof(MODELS_DIR)
    if LIVENESS == "passive" and not antispoof.loaded:
        print("AVISO: LIVENESS=passive mas app/models/antispoof.json não existe; "
              "usando desafio ativo em todo check-in (rode scripts/convert_antispoof.sh)")
    else:
        print(f"prova de vida: {LIVENESS} · anti-spoofing: {len(antispoof.models)} modelo(s)")
    yield
    pool.close()


app = FastAPI(title="FaceCheck", lifespan=lifespan)


# ---------- helpers ----------

def rows(conn, sql, params=None):
    return conn.execute(sql, params or {}).fetchall()


def row(conn, sql, params=None):
    return conn.execute(sql, params or {}).fetchone()


def clean(s: str | None) -> str | None:
    s = (s or "").strip()
    return s or None


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "imagem inválida")
    return img


def detect_faces(img: np.ndarray):
    faces = face_app.get(img)
    out = []
    for f in faces:
        x1, y1, x2, y2 = [float(v) for v in f.bbox]
        if min(x2 - x1, y2 - y1) < MIN_FACE_PX:
            continue
        out.append(f)
    out.sort(key=lambda f: -(f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))   # maior rosto primeiro
    return out


def bbox_dict(f):
    x1, y1, x2, y2 = [round(float(v)) for v in f.bbox]
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}


def face_pose(f):
    """yaw ~0 de frente; >0 = pessoa virou para a ESQUERDA dela (imagem não espelhada); roll em graus.
    Usa os 5 pontos do detector: deslocamento do nariz em relação ao meio dos olhos, normalizado
    pela distância entre os olhos. Uma foto plana girada não muda essa razão."""
    kps = getattr(f, "kps", None)
    if kps is None or len(kps) < 3:
        return None, None
    le, re, nose = kps[0], kps[1], kps[2]
    eye_dist = float(np.hypot(*(re - le))) or 1.0
    mid = (le + re) / 2
    yaw = float((nose[0] - mid[0]) / eye_dist)
    roll = float(np.degrees(np.arctan2(re[1] - le[1], re[0] - le[0])))
    return yaw, roll


class Liveness:
    """Desafio ativo por pessoa e evento.

    Depois do reconhecimento, a pessoa precisa: olhar de frente, depois virar a cabeça para os
    dois lados numa ordem sorteada, em até LIVENESS_TIMEOUT segundos, sem sair do quadro.
    Foto ou tela parada não muda o ângulo dos pontos do rosto, então não passa.
    """

    def __init__(self, sides: int | None = None):
        self.lock = threading.Lock()
        self.states: dict[tuple, dict] = {}
        self.sides = sides if sides is not None else LIVENESS_SIDES

    def _new(self, now):
        seq = random.sample(["left", "right"], max(1, min(2, self.sides)))
        return {"seq": seq, "step": 0, "front": False, "started": now, "last": now, "misses": 0}

    def clear(self, key):
        with self.lock:
            self.states.pop(key, None)

    def _view(self, st, now, status="challenge"):
        action = "front" if not st["front"] else st["seq"][st["step"]]
        return {"status": status, "action": action, "step": st["step"] + (1 if st["front"] else 0),
                "steps": len(st["seq"]) + 1,
                "remaining": round(max(0.0, LIVENESS_TIMEOUT - (now - st["started"])), 1)}

    def active(self, key) -> bool:
        with self.lock:
            return key in self.states

    def update(self, key, yaw, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            st = self.states.get(key)
            if st is None or now - st["last"] > 3.0:          # novo ou abandonado: começa do zero
                st = self.states[key] = self._new(now)
            st["last"], st["misses"] = now, 0
            if now - st["started"] > LIVENESS_TIMEOUT:
                st = self.states[key] = self._new(now)
                return self._view(st, now, status="timeout")
            if yaw is None:
                return self._view(st, now)
            if not st["front"]:
                if abs(yaw) < YAW_FRONT:
                    st["front"] = True
                return self._view(st, now)
            want = st["seq"][st["step"]]
            if (want == "left" and yaw > YAW_TURN) or (want == "right" and yaw < -YAW_TURN):
                st["step"] += 1
                if st["step"] >= len(st["seq"]):
                    del self.states[key]
                    return {"status": "passed"}
            return self._view(st, now)

    def missed(self, event_id, seen: set):
        """Chamado a cada quadro do evento: desafios cujo rosto sumiu do quadro são reiniciados."""
        with self.lock:
            for key in [k for k in self.states if k[0] == event_id and k not in seen]:
                st = self.states[key]
                st["misses"] += 1
                if st["misses"] >= LIVENESS_MAX_MISSES:
                    del self.states[key]


liveness = Liveness()


def run_liveness(img, bbox, key, yaw) -> dict:
    """Prova de vida para um rosto reconhecido e liberado no evento.

    passive: o modelo anti-spoofing avalia o quadro; com a média de alguns quadros decide
             real (passa), spoof (barrado) ou dúvida (desafio de virar para um lado).
    active:  sempre o desafio de virar a cabeça.
    """
    if LIVENESS == "passive" and antispoof is not None and antispoof.loaded:
        real = antispoof.real_prob(img, bbox)
        verdict, mean, n = passive.update(key, real)
        if verdict == "real":
            return {"status": "passed", "real": mean, "frames": n}
        if verdict == "spoof":
            return {"status": "spoof", "real": mean, "frames": n}
        if verdict == "checking" and not liveness.active(key):
            return {"status": "checking", "real": mean, "frames": n}
        out = liveness.update(key, yaw)          # dúvida: desafio de um lado
        out["real"] = mean
        return out
    return liveness.update(key, yaw)


# ---------- pessoas ----------

class PersonIn(BaseModel):
    name: str
    code: str | None = None


class PersonPatch(BaseModel):
    name: str | None = None
    code: str | None = None


def get_person_or_404(conn, person_id: int):
    p = row(conn, "SELECT id, name, code, created_at FROM people WHERE id = %(id)s", {"id": person_id})
    if not p:
        raise HTTPException(404, "pessoa não encontrada")
    return p


@app.get("/api/people")
def list_people(q: str | None = Query(None)):
    qq = f"%{q.strip()}%" if q and q.strip() else None
    with pool.connection() as conn:
        return rows(conn, """
            SELECT p.id, p.name, p.code, p.created_at,
                   (SELECT count(*) FROM face_embeddings fe WHERE fe.person_id = p.id) AS samples,
                   (SELECT count(*) FROM event_people ep WHERE ep.person_id = p.id) AS events
            FROM people p
            WHERE %(qq)s::text IS NULL OR p.name ILIKE %(qq)s OR p.code ILIKE %(qq)s
            ORDER BY lower(p.name)
        """, {"qq": qq})


@app.post("/api/people", status_code=201)
def create_person(p: PersonIn):
    name = clean(p.name)
    if not name:
        raise HTTPException(400, "nome obrigatório")
    with pool.connection() as conn:
        return row(conn, "INSERT INTO people (name, code) VALUES (%(n)s, %(c)s) RETURNING id, name, code",
                   {"n": name, "c": clean(p.code)})


@app.get("/api/people/{person_id}")
def get_person(person_id: int):
    with pool.connection() as conn:
        p = get_person_or_404(conn, person_id)
        p["samples"] = rows(conn, """
            SELECT id, det_score, created_at FROM face_embeddings
            WHERE person_id = %(id)s ORDER BY created_at
        """, {"id": person_id})
        p["events"] = rows(conn, """
            SELECT e.id, e.name, e.event_date, e.access, c.created_at AS checked_in_at
            FROM event_people ep JOIN events e ON e.id = ep.event_id
            LEFT JOIN checkins c ON c.event_id = e.id AND c.person_id = ep.person_id
            WHERE ep.person_id = %(id)s
            ORDER BY e.event_date DESC, e.id DESC
        """, {"id": person_id})
    return p


@app.patch("/api/people/{person_id}")
def update_person(person_id: int, body: PersonPatch):
    fields = body.model_dump(exclude_unset=True)
    with pool.connection() as conn:
        p = get_person_or_404(conn, person_id)
        name = clean(fields["name"]) if "name" in fields else p["name"]
        if not name:
            raise HTTPException(400, "nome obrigatório")
        code = clean(fields["code"]) if "code" in fields else p["code"]
        return row(conn, "UPDATE people SET name = %(n)s, code = %(c)s WHERE id = %(id)s RETURNING id, name, code",
                   {"n": name, "c": code, "id": person_id})


@app.delete("/api/people/{person_id}", status_code=204)
def delete_person(person_id: int):
    with pool.connection() as conn:
        conn.execute("DELETE FROM people WHERE id = %(id)s", {"id": person_id})


@app.delete("/api/people/{person_id}/samples/{sample_id}", status_code=204)
def delete_sample(person_id: int, sample_id: int):
    with pool.connection() as conn:
        conn.execute("DELETE FROM face_embeddings WHERE id = %(s)s AND person_id = %(p)s",
                     {"s": sample_id, "p": person_id})


@app.delete("/api/people/{person_id}/samples", status_code=204)
def delete_all_samples(person_id: int):
    with pool.connection() as conn:
        conn.execute("DELETE FROM face_embeddings WHERE person_id = %(p)s", {"p": person_id})


@app.post("/api/people/{person_id}/enroll")
def enroll(person_id: int, image: UploadFile = File(...)):
    """Recebe uma foto com exatamente um rosto e guarda o embedding (a foto é descartada)."""
    t0 = time.perf_counter()
    img = decode_image(image.file.read())
    faces = detect_faces(img)
    if len(faces) == 0:
        return {"ok": False, "reason": "nenhum rosto encontrado", "faces": 0}
    if len(faces) > 1:
        return {"ok": False, "reason": "mais de um rosto na imagem", "faces": len(faces)}
    f = faces[0]
    emb = np.asarray(f.normed_embedding, dtype=np.float32)
    with pool.connection() as conn:
        get_person_or_404(conn, person_id)
        # aviso se esse rosto já parece outra pessoa cadastrada
        other = row(conn, """
            SELECT p.name, 1 - (fe.embedding <=> %(e)s) AS sim
            FROM face_embeddings fe JOIN people p ON p.id = fe.person_id
            WHERE p.id <> %(p)s ORDER BY fe.embedding <=> %(e)s LIMIT 1
        """, {"e": emb, "p": person_id})
        sample = row(conn, "INSERT INTO face_embeddings (person_id, embedding, det_score) "
                           "VALUES (%(p)s, %(e)s, %(d)s) RETURNING id", {"p": person_id, "e": emb, "d": float(f.det_score)})
        samples = row(conn, "SELECT count(*) AS n FROM face_embeddings WHERE person_id = %(p)s",
                      {"p": person_id})["n"]
    warn = f"parece com {other['name']} (sim {other['sim']:.2f})" if other and other["sim"] >= MATCH_THRESHOLD else None
    return {"ok": True, "faces": 1, "samples": samples, "sample_id": sample["id"], "det_score": round(float(f.det_score), 3),
            "bbox": bbox_dict(f), "warning": warn, "ms": round((time.perf_counter() - t0) * 1000)}


# ---------- eventos ----------

Access = Literal["list", "all"]


class EventIn(BaseModel):
    name: str
    event_date: date | None = None
    access: Access = "list"


class EventPatch(BaseModel):
    name: str | None = None
    event_date: date | None = None
    access: Access | None = None


class ParticipantsIn(BaseModel):
    person_ids: list[int]


EVENT_COLS = """e.id, e.name, e.event_date, e.access, e.created_at,
    (SELECT count(*) FROM event_people ep WHERE ep.event_id = e.id) AS participants,
    (SELECT count(*) FROM checkins c WHERE c.event_id = e.id) AS checkins"""


def get_event_or_404(conn, event_id: int):
    ev = row(conn, f"SELECT {EVENT_COLS} FROM events e WHERE e.id = %(id)s", {"id": event_id})
    if not ev:
        raise HTTPException(404, "evento não encontrado")
    return ev


@app.get("/api/events")
def list_events(scope: Literal["upcoming", "past", "all"] = "all",
                q: str | None = Query(None),
                limit: int = Query(50, ge=1, le=500),
                offset: int = Query(0, ge=0)):
    where = ["(%(qq)s::text IS NULL OR e.name ILIKE %(qq)s)"]
    if scope == "upcoming":
        where.append(f"e.event_date >= {TODAY}")
        order = "e.event_date ASC, e.id ASC"
    elif scope == "past":
        where.append(f"e.event_date < {TODAY}")
        order = "e.event_date DESC, e.id DESC"
    else:
        order = "e.event_date DESC, e.id DESC"
    w = " AND ".join(where)
    params = {"qq": f"%{q.strip()}%" if q and q.strip() else None, "tz": APP_TZ,
              "limit": limit, "offset": offset}
    with pool.connection() as conn:
        total = row(conn, f"SELECT count(*) AS n FROM events e WHERE {w}", params)["n"]
        items = rows(conn, f"SELECT {EVENT_COLS} FROM events e WHERE {w} ORDER BY {order} "
                           "LIMIT %(limit)s OFFSET %(offset)s", params)
    return {"items": items, "total": total}


@app.post("/api/events", status_code=201)
def create_event(e: EventIn):
    name = clean(e.name)
    if not name:
        raise HTTPException(400, "nome obrigatório")
    with pool.connection() as conn:
        new = row(conn, f"""
            INSERT INTO events (name, event_date, access)
            VALUES (%(n)s, COALESCE(%(d)s, {TODAY}), %(a)s) RETURNING id
        """, {"n": name, "d": e.event_date, "a": e.access, "tz": APP_TZ})
        return get_event_or_404(conn, new["id"])


@app.patch("/api/events/{event_id}")
def update_event(event_id: int, body: EventPatch):
    fields = body.model_dump(exclude_unset=True)
    with pool.connection() as conn:
        ev = get_event_or_404(conn, event_id)
        name = clean(fields["name"]) if "name" in fields else ev["name"]
        if not name:
            raise HTTPException(400, "nome obrigatório")
        conn.execute("UPDATE events SET name = %(n)s, event_date = %(d)s, access = %(a)s WHERE id = %(id)s",
                     {"n": name, "d": fields.get("event_date") or ev["event_date"],
                      "a": fields.get("access") or ev["access"], "id": event_id})
        return get_event_or_404(conn, event_id)


@app.delete("/api/events/{event_id}", status_code=204)
def delete_event(event_id: int):
    with pool.connection() as conn:
        conn.execute("DELETE FROM events WHERE id = %(id)s", {"id": event_id})


def event_attendance(conn, ev):
    """Pessoas do evento com status. Lista: participantes (+ quem fez check-in sem estar na lista).
    Aberto: todos os cadastrados."""
    params = {"id": ev["id"], "tz": APP_TZ}
    local = "to_char(c.created_at AT TIME ZONE %(tz)s, 'DD/MM/YYYY HH24:MI:SS') AS checked_in_local"
    if ev["access"] == "list":
        people = rows(conn, f"""
            SELECT p.id AS person_id, p.name, p.code, TRUE AS listed,
                   c.id AS checkin_id, c.created_at AS checked_in_at, c.score, c.method, {local}
            FROM event_people ep JOIN people p ON p.id = ep.person_id
            LEFT JOIN checkins c ON c.event_id = ep.event_id AND c.person_id = p.id
            WHERE ep.event_id = %(id)s
            UNION ALL
            SELECT p.id, p.name, p.code, FALSE, c.id, c.created_at, c.score, c.method, {local}
            FROM checkins c JOIN people p ON p.id = c.person_id
            WHERE c.event_id = %(id)s AND NOT EXISTS (
                SELECT 1 FROM event_people ep WHERE ep.event_id = c.event_id AND ep.person_id = c.person_id)
            ORDER BY name
        """, params)
    else:
        people = rows(conn, f"""
            SELECT p.id AS person_id, p.name, p.code, TRUE AS listed,
                   c.id AS checkin_id, c.created_at AS checked_in_at, c.score, c.method, {local}
            FROM people p LEFT JOIN checkins c ON c.event_id = %(id)s AND c.person_id = p.id
            ORDER BY lower(p.name)
        """, params)
    expected = sum(1 for p in people if p["listed"])
    present = sum(1 for p in people if p["listed"] and p["checkin_id"])
    outside = sum(1 for p in people if not p["listed"])
    return people, {"expected": expected, "present": present, "absent": expected - present, "outside": outside}


@app.get("/api/events/{event_id}")
def get_event(event_id: int):
    with pool.connection() as conn:
        ev = get_event_or_404(conn, event_id)
        people, stats = event_attendance(conn, ev)
    return {"event": ev, "people": people, "stats": stats}


@app.put("/api/events/{event_id}/participants")
def set_participants(event_id: int, body: ParticipantsIn):
    """Substitui a lista de participantes do evento."""
    ids = sorted(set(body.person_ids))
    with pool.connection() as conn:
        get_event_or_404(conn, event_id)
        conn.execute("DELETE FROM event_people WHERE event_id = %(e)s AND NOT (person_id = ANY(%(ids)s::int[]))",
                     {"e": event_id, "ids": ids})
        conn.execute("""
            INSERT INTO event_people (event_id, person_id)
            SELECT %(e)s, p.id FROM people p WHERE p.id = ANY(%(ids)s::int[])
            ON CONFLICT DO NOTHING
        """, {"e": event_id, "ids": ids})
        n = row(conn, "SELECT count(*) AS n FROM event_people WHERE event_id = %(e)s", {"e": event_id})["n"]
    return {"participants": n}


class ManualCheckinIn(BaseModel):
    person_id: int


@app.post("/api/events/{event_id}/checkins", status_code=201)
def add_checkin(event_id: int, body: ManualCheckinIn):
    """Presença registrada à mão no admin (ex.: rosto não reconhecido, sem cadastro facial).
    Fica marcada como origem "manual" e sem similaridade. Respeita a lista do evento."""
    with pool.connection() as conn:
        ev = get_event_or_404(conn, event_id)
        get_person_or_404(conn, body.person_id)
        prm = {"e": event_id, "p": body.person_id}
        if ev["access"] == "list" and not row(
                conn, "SELECT 1 AS ok FROM event_people WHERE event_id = %(e)s AND person_id = %(p)s", prm):
            raise HTTPException(409, "pessoa não está na lista do evento")
        new = row(conn, """
            INSERT INTO checkins (event_id, person_id, score, method) VALUES (%(e)s, %(p)s, NULL, 'manual')
            ON CONFLICT (event_id, person_id) DO NOTHING RETURNING id, created_at
        """, prm)
        if not new:
            raise HTTPException(409, "presença já registrada")
    return {"id": new["id"], "at": new["created_at"], "method": "manual"}


@app.post("/api/events/{event_id}/participants/{person_id}", status_code=201)
def add_participant(event_id: int, person_id: int):
    """Inclui uma pessoa na lista do evento (sem mexer nas demais)."""
    with pool.connection() as conn:
        get_event_or_404(conn, event_id)
        get_person_or_404(conn, person_id)
        conn.execute("INSERT INTO event_people (event_id, person_id) VALUES (%(e)s, %(p)s) ON CONFLICT DO NOTHING",
                     {"e": event_id, "p": person_id})
    return {"event_id": event_id, "person_id": person_id, "listed": True}


@app.delete("/api/events/{event_id}/participants/{person_id}", status_code=204)
def remove_participant(event_id: int, person_id: int):
    with pool.connection() as conn:
        conn.execute("DELETE FROM event_people WHERE event_id = %(e)s AND person_id = %(p)s", {"e": event_id, "p": person_id})


@app.delete("/api/events/{event_id}/checkins/{checkin_id}", status_code=204)
def delete_checkin(event_id: int, checkin_id: int):
    with pool.connection() as conn:
        conn.execute("DELETE FROM checkins WHERE id = %(c)s AND event_id = %(e)s", {"c": checkin_id, "e": event_id})


@app.get("/api/events/{event_id}/export.csv")
def export_csv(event_id: int):
    with pool.connection() as conn:
        ev = get_event_or_404(conn, event_id)
        people, _ = event_attendance(conn, ev)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["evento", "data", "nome", "matricula", "status", "horario", "origem", "similaridade"])
    for p in people:
        status = ("presente" if p["listed"] else "presente (fora da lista)") if p["checkin_id"] else "ausente"
        w.writerow([ev["name"], ev["event_date"].strftime("%d/%m/%Y"), p["name"], p["code"] or "", status,
                    p["checked_in_local"] or "",
                    ({"face": "reconhecimento", "manual": "manual"}.get(p["method"], p["method"]) if p["checkin_id"] else ""),
                    f"{p['score']:.3f}" if p["score"] is not None else ""])
    fname = f"presenca_{ev['event_date'].isoformat()}_{event_id}.csv"
    bom = "﻿"  # ajuda o Excel a abrir em UTF-8
    return StreamingResponse(iter([bom + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=" + fname})


@app.get("/api/stats")
def stats():
    with pool.connection() as conn:
        return row(conn, f"""
            SELECT (SELECT count(*) FROM people) AS people,
                   (SELECT count(*) FROM events) AS events,
                   (SELECT count(*) FROM events WHERE event_date >= {TODAY}) AS upcoming,
                   (SELECT count(*) FROM events WHERE event_date = {TODAY}) AS today,
                   (SELECT count(*) FROM checkins WHERE (created_at AT TIME ZONE %(tz)s)::date = {TODAY}) AS checkins_today,
                   (SELECT count(*) FROM people p
                     WHERE (SELECT count(*) FROM face_embeddings fe WHERE fe.person_id = p.id) < 3) AS low_samples
        """, {"tz": APP_TZ})


# ---------- reconhecimento ----------

@app.post("/api/recognize")
def recognize(image: UploadFile = File(...),
              event_id: int | None = Query(None),
              max_faces: int = Query(5, ge=1, le=20)):
    """Detecta rostos no frame e identifica cada um. Com event_id: confere se a pessoa está liberada
    no evento e, com LIVENESS=active, só registra presença depois do desafio de giro da cabeça."""
    t0 = time.perf_counter()
    img = decode_image(image.file.read())
    h, w = img.shape[:2]
    faces = detect_faces(img)[:max_faces]
    results, seen = [], set()
    with pool.connection() as conn:
        ev = None
        if event_id is not None:
            ev = row(conn, "SELECT id, access FROM events WHERE id = %(id)s", {"id": event_id})
            if not ev:
                raise HTTPException(404, "evento não encontrado")
        for f in faces:
            emb = np.asarray(f.normed_embedding, dtype=np.float32)
            yaw, _ = face_pose(f)
            best = row(conn, """
                SELECT p.id, p.name, 1 - (fe.embedding <=> %(e)s) AS sim
                FROM face_embeddings fe JOIN people p ON p.id = fe.person_id
                ORDER BY fe.embedding <=> %(e)s LIMIT 1
            """, {"e": emb})
            item = {"bbox": bbox_dict(f), "det_score": round(float(f.det_score), 3),
                    "yaw": round(yaw, 2) if yaw is not None else None,
                    "match": None, "checkin": None, "liveness": None, "denied": None,
                    "best_score": round(float(best["sim"]), 3) if best else None}
            if best:
                sim = float(best["sim"])
                # com o rosto virado a similaridade cai um pouco: tolera durante um desafio já aberto
                in_challenge = (ev is not None and LIVENESS != "off"
                                and sim >= MATCH_THRESHOLD - LIVENESS_MATCH_SLACK
                                and liveness.active((event_id, best["id"])))
                if sim >= MATCH_THRESHOLD or in_challenge:
                    item["match"] = {"person_id": best["id"], "name": best["name"], "score": round(sim, 3)}
            if item["match"] and ev is not None:
                pid, sim = item["match"]["person_id"], item["match"]["score"]
                key = (event_id, pid)
                prm = {"e": event_id, "p": pid}
                prev = row(conn, "SELECT created_at FROM checkins WHERE event_id = %(e)s AND person_id = %(p)s", prm)
                if prev:
                    item["checkin"] = {"status": "repeat", "at": prev["created_at"]}
                elif ev["access"] == "list" and not row(
                        conn, "SELECT 1 AS ok FROM event_people WHERE event_id = %(e)s AND person_id = %(p)s", prm):
                    item["denied"] = "not_listed"
                else:
                    seen.add(key)
                    passed = LIVENESS == "off"
                    if not passed:
                        item["liveness"] = run_liveness(img, item["bbox"], key, yaw)
                        passed = item["liveness"]["status"] == "passed"
                    if passed:
                        passive.clear(key)
                        liveness.clear(key)
                        new = row(conn, """
                            INSERT INTO checkins (event_id, person_id, score) VALUES (%(e)s, %(p)s, %(s)s)
                            ON CONFLICT (event_id, person_id) DO NOTHING RETURNING created_at
                        """, {**prm, "s": sim})
                        item["checkin"] = {"status": "new" if new else "repeat",
                                           "at": new["created_at"] if new else None}
            results.append(item)
    if ev is not None and LIVENESS != "off":
        liveness.missed(event_id, seen)
    return {"width": w, "height": h, "faces": results, "threshold": MATCH_THRESHOLD,
            "liveness": LIVENESS, "ms": round((time.perf_counter() - t0) * 1000)}


@app.post("/api/analyze")
def analyze(image: UploadFile = File(...)):
    """Qualidade do enquadramento para o cadastro: posição, tamanho, luz, nitidez e orientação.
    Não consulta o banco nem guarda nada."""
    t0 = time.perf_counter()
    img = decode_image(image.file.read())
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_app.get(img)
    faces.sort(key=lambda f: -(f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    out = {"width": w, "height": h, "faces": len(faces), "frame_brightness": round(float(gray.mean()), 1),
           "face": None, "ms": 0}
    if faces:
        f = faces[0]
        x1, y1, x2, y2 = [int(max(0, v)) for v in f.bbox]
        x2, y2 = min(w, x2), min(h, y2)
        crop = gray[y1:y2, x1:x2]
        info = {"bbox": bbox_dict(f), "det_score": round(float(f.det_score), 3)}
        if crop.size > 0:
            small = cv2.resize(crop, (112, int(112 * crop.shape[0] / max(1, crop.shape[1]))))
            info["brightness"] = round(float(crop.mean()), 1)
            info["sharpness"] = round(float(cv2.Laplacian(small, cv2.CV_64F).var()), 1)
        yaw, roll = face_pose(f)
        if yaw is not None:
            info["yaw"] = round(yaw, 2)       # ~0 frente; +/- virado
            info["roll"] = round(roll, 1)
        if antispoof is not None and antispoof.loaded:
            info["real"] = round(antispoof.real_prob(img, info["bbox"]), 3)   # prob. de rosto real (anti-spoofing)
        out["face"] = info
    out["ms"] = round((time.perf_counter() - t0) * 1000)
    return out


@app.get("/api/health")
def health():
    return {"ok": True, "threshold": MATCH_THRESHOLD, "min_face_px": MIN_FACE_PX,
            "liveness": LIVENESS, "yaw_turn": YAW_TURN, "liveness_timeout": LIVENESS_TIMEOUT,
            "liveness_sides": LIVENESS_SIDES,
            "antispoof": {"loaded": bool(antispoof and antispoof.loaded),
                          "models": len(antispoof.models) if antispoof else 0,
                          "real_min": SPOOF_REAL_MIN, "fake_max": SPOOF_FAKE_MAX, "frames": SPOOF_FRAMES}}


# ---------- páginas ----------

@app.get("/", include_in_schema=False)
def page_checkin():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/cadastro", include_in_schema=False)
def page_enroll():
    return FileResponse(os.path.join(STATIC_DIR, "cadastro.html"))


@app.get("/admin", include_in_schema=False)
def page_admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


# ---------- aplicativo instalável (PWA) ----------
# Manifesto e service worker na raiz: o service worker só controla as páginas abaixo do caminho dele.

@app.get("/manifest.webmanifest", include_in_schema=False)
def pwa_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.webmanifest"), media_type="application/manifest+json",
                        headers={"Cache-Control": "no-cache"})


@app.get("/sw.js", include_in_schema=False)
def pwa_service_worker():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
