"""Dados de demonstração (prefixo "ZZ Demo") para conferir a interface. Rodar DENTRO do container:

    docker exec -i facecheck_api python - seed  < scripts/demo_seed.py
    docker exec -i facecheck_api python - clean < scripts/demo_seed.py
"""
import os
import random
import sys
from datetime import date, timedelta

import psycopg

mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
    conn.execute("DELETE FROM events WHERE name LIKE 'ZZ Demo%'")
    conn.execute("DELETE FROM people WHERE name LIKE 'ZZ Demo%'")
    if mode == "clean":
        print("demo removido")
        sys.exit(0)
    random.seed(7)
    names = ["Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Alves", "Elisa Rocha", "Fábio Nunes", "Gabriela Dias", "Henrique Prado"]
    pids = []
    for i, n in enumerate(names):
        pid = conn.execute("INSERT INTO people (name, code) VALUES (%s, %s) RETURNING id",
                           (f"ZZ Demo {n}", f"10{i + 1:03d}" if i % 3 else None)).fetchone()[0]
        pids.append(pid)
        for _ in range(random.choice([0, 1, 3, 3, 4])):     # amostras falsas só para a contagem
            conn.execute("INSERT INTO face_embeddings (person_id, embedding, det_score) VALUES (%s, %s::vector, %s)",
                         (pid, "[" + ",".join(["0"] * 511 + ["1"]) + "]", round(random.uniform(.7, .95), 3)))
    kinds = ["Treinamento de segurança", "Convenção de vendas", "Reunião geral", "Workshop de produto", "Integração de novos"]
    today = date.today()
    for i in range(25):
        d = today + timedelta(days=random.randint(-60, 40))
        if i == 0:
            d = today
        access = "all" if i % 6 == 5 else "list"
        eid = conn.execute("INSERT INTO events (name, event_date, access) VALUES (%s, %s, %s) RETURNING id",
                           (f"ZZ Demo {random.choice(kinds)} #{i + 1}", d, access)).fetchone()[0]
        listed = random.sample(pids, random.randint(3, len(pids))) if access == "list" else pids
        if access == "list":
            for p in listed:
                conn.execute("INSERT INTO event_people (event_id, person_id) VALUES (%s, %s)", (eid, p))
        if d <= today:
            for p in random.sample(listed, random.randint(0, len(listed))):
                conn.execute("INSERT INTO checkins (event_id, person_id, score) VALUES (%s, %s, %s)",
                             (eid, p, round(random.uniform(.5, .8), 3)))
    print("demo criado: 8 pessoas, 25 eventos")
