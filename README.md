# FaceCheck

Registro de presença em eventos por reconhecimento facial, usando um navegador com câmera
(tablet, celular ou PC) e uma API própria. A pessoa olha para a câmera, o sistema reconhece o rosto,
confere se ela está liberada no evento, faz a prova de vida e registra a presença.

Nenhuma foto é guardada: o banco armazena só o vetor numérico do rosto (embedding) e o horário do check-in.

> Protótipo para validar a ideia. Leia [Limites e cuidados](#limites-e-cuidados) e
> [Licenças de terceiros](#licenças-de-terceiros) antes de usar em produção.

## Funcionalidades

- **Check-in** em tela cheia: tela de espera com evento e câmera, botão Iniciar/Parar, leitura contínua com
  intervalo configurável, pausa automática com o menu aberto ou a aba em segundo plano.
- **Cadastro em 3 etapas**: pessoa (com busca e aviso de nome duplicado) → fotos (poses de frente e dos dois lados,
  captura automática, som de confirmação, helper de enquadramento ao vivo) → inclusão nos próximos eventos.
- **Eventos com lista de participantes** ou abertos a todos os cadastrados; quem está fora da lista é barrado.
- **Admin**: painel com indicadores, eventos (busca, filtros, paginação), pessoas, presença por evento, presença
  manual, desfazer presença e exportação CSV com presentes, ausentes e origem (reconhecimento/manual).
- **Prova de vida (anti-foto)**: modelo anti-spoofing passivo em todo quadro e desafio de virar o rosto só na dúvida.
- **Aplicativo instalável (PWA)** que abre sempre em tela cheia.

## Como funciona

```
navegador (câmera)  ──JPEG 640px a cada ~0,6 s──▶  API FastAPI (container)
                                                     ├─ InsightFace buffalo_l: detecção (SCRFD) + embedding (ArcFace)
                                                     ├─ MiniFASNet (ONNX): probabilidade de rosto real
                                                     └─ Postgres + pgvector: busca do rosto mais parecido
```

Tudo roda na CPU. Em um processador de desktop comum, cada quadro leva ~100–250 ms no servidor
(o anti-spoofing soma ~12 ms por rosto).

## Requisitos

- Docker com Docker Compose (v1 `docker-compose` ou v2 `docker compose`).
- PostgreSQL 14+ com a extensão **pgvector** (ex.: imagem `pgvector/pgvector:pg16`), acessível por uma rede Docker.
- CPU x86_64; 2 GB de RAM livres para o container.
- **HTTPS** para usar a câmera em outro aparelho (o navegador só libera câmera em `https://` ou `localhost`).

## Instalação

```bash
git clone <url-do-repositório> facecheck && cd facecheck

# 1. rede Docker compartilhada com o Postgres (pule se já existir uma)
docker network create facecheck_net
docker network connect facecheck_net <container-do-postgres>   # se o Postgres já existir

# 2. banco + .env (o script lê a senha do container e gera o .env)
PG_CONTAINER=<container-do-postgres> bash scripts/setup_db.sh
#    ou manualmente: cp .env.example .env, ajuste DATABASE_URL e rode no Postgres:
#    CREATE DATABASE facecheck;  \c facecheck  CREATE EXTENSION vector;

# 3. confira no .env: DATABASE_URL (host = nome do container do Postgres) e DOCKER_NETWORK

# 4. build e subida (a primeira vez baixa ~300 MB de modelos para dentro da imagem)
docker compose up -d --build
docker logs -f facecheck_api        # espere "Application startup complete"
```

Acesse `http://localhost:8090`. As tabelas são criadas automaticamente na primeira subida.

| Página | O que faz |
|---|---|
| `/` | Check-in |
| `/cadastro` | Cadastro de pessoas e fotos (`/cadastro?person=ID` vai direto às fotos) |
| `/admin` | Painel, eventos, participantes, presenças e pessoas (`/admin#evento=ID`, `/admin#pessoa=ID`) |
| `/docs` | Documentação interativa da API (Swagger) |

**Atualizar depois de mudanças:** a pasta `app/` é montada como volume, então HTML/CSS/JS não precisam de rebuild
(suba o `?v=` nos `<link>`/`<script>` para furar o cache). Mudou `app/main.py` ou o `.env`: recrie o container
(`bash scripts/restart.sh`, que também contorna uma limitação do `docker-compose` v1 ao recriar).

## Configuração (`.env`)

| Variável | Padrão | Para que serve |
|---|---|---|
| `DATABASE_URL` | — | Conexão com o Postgres (`postgresql://usuario:senha@host:5432/facecheck`) |
| `DOCKER_NETWORK` | `facecheck_net` | Rede Docker externa onde o Postgres está |
| `APP_PORT` | `8090` | Porta local da aplicação |
| `PUBLIC_PORT` | `8000` | Porta extra opcional (túnel ou proxy reverso) |
| `MATCH_THRESHOLD` | `0.45` | Similaridade mínima para reconhecer. Suba se houver confusão entre pessoas; baixe se não reconhecer |
| `MIN_FACE_PX` | `60` | Rostos menores que isso (no quadro de 640 px) são ignorados, como pessoas ao fundo |
| `APP_TZ` | `America/Sao_Paulo` | Fuso para "hoje", filtros de data e horários do CSV |
| `LIVENESS` | `passive` | Prova de vida: `passive`, `active` ou `off` (ver abaixo) |
| `SPOOF_REAL_MIN` | `0.80` | Média ≥ isso = rosto real. Baixe se pessoas reais caírem muito no desafio |
| `SPOOF_FAKE_MAX` | `0.40` | Média ≤ isso = foto/tela. Suba se fotos de celular estiverem passando |
| `SPOOF_FRAMES` | `2` | Quadros usados para decidir (janela de 3 s) |
| `LIVENESS_SIDES` | `1` (passive) / `2` (active) | Lados a virar no desafio |
| `LIVENESS_YAW_TURN` | `0.25` | Quanto virar o rosto (~25°) |
| `LIVENESS_YAW_FRONT` | `0.12` | Quão de frente precisa estar no início do desafio |
| `LIVENESS_TIMEOUT` | `8` | Segundos para completar o desafio |

No check-in, o menu lateral também tem ajustes por aparelho (salvos no navegador): intervalo entre leituras
(0,2 a 2 s), câmera e espelhamento da imagem.

## Eventos e participantes

| Modo do evento | Quem registra presença |
|---|---|
| **Somente a lista** (padrão) | Só quem está na aba Participantes. Os demais são barrados com "não está na lista". Lista vazia barra todos. |
| **Todos os cadastrados** | Qualquer pessoa com rosto cadastrado. |

O detalhe do evento mostra esperados, presentes e ausentes. Pelo menu da engrenagem: editar, exportar CSV e excluir.
Presença manual (botão `+` em quem está ausente) fica marcada como **manual** no relatório. Quem sai da lista depois
do check-in continua no relatório como "presente (fora da lista)".

## Prova de vida

| Modo | Comportamento | Tempo por pessoa |
|---|---|---|
| `passive` | O modelo anti-spoofing avalia cada quadro sem a pessoa fazer nada. Pela média de 2 quadros: **real** → registra; **foto/tela** → barra; **dúvida** → pede para virar o rosto para um lado sorteado. | ~1–1,5 s (dúvida: ~3 s) |
| `active` | Sempre o desafio: olhar de frente e virar para os dois lados em ordem sorteada, em até 8 s. | ~4–5 s |
| `off` | Sem proteção contra foto. | ~1 s |

- **Camada passiva:** modelos MiniFASNet do Silent-Face-Anti-Spoofing convertidos para ONNX em `app/models/`.
  Para reconverter: `bash scripts/convert_antispoof.sh` (container descartável com PyTorch CPU; lê só os pesos,
  com `weights_only=True`, e a arquitetura vem de `scripts/minifasnet.py`).
- **Desafio:** o ângulo vem dos 5 pontos do detector (nariz em relação ao meio dos olhos). Uma foto ou tela parada,
  mesmo inclinada, mantém essa razão constante. Validado no servidor.
- O valor `real` aparece na linha de status do check-in e no cadastro: use-o para calibrar `SPOOF_REAL_MIN` e
  `SPOOF_FAKE_MAX` com a câmera, a luz do local e tentativas reais com foto e tela.

## Acesso por celular ou tablet

A câmera só funciona em contexto seguro (`https://` ou `localhost`). Para usar em outro aparelho, publique a
aplicação atrás de HTTPS, por exemplo:

- **Proxy reverso com certificado** (Nginx, Caddy, Traefik) apontando para `APP_PORT` ou `PUBLIC_PORT`.
- **Túnel** (ex.: Cloudflare Tunnel) com um hostname apontando para `http://localhost:<PUBLIC_PORT>`.
  Atenção: assim o sistema fica acessível pela internet sem login; proteja o acesso (ex.: Cloudflare Access).
- **Rede local no WSL2** (só para testes): `scripts/expose_lan.ps1` (como administrador) cria o encaminhamento da
  porta e a regra de firewall. Sem HTTPS, o Chrome do Android só libera a câmera com a flag
  `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.

## Instalar como aplicativo

Com o sistema aberto em HTTPS no Chrome do aparelho: menu lateral → **Instalar aplicativo** (ou menu ⋮ do Chrome →
"Instalar app"). Instalado, o FaceCheck abre sempre em tela cheia, em todas as telas, com atalhos para Check-in,
Cadastro e Admin no toque longo do ícone.

O service worker (`/sw.js`) não guarda páginas em cache: tudo vem sempre do servidor. Sem conexão, mostra uma tela
"Sem conexão com o servidor".

## Testes

```bash
bash scripts/restart.sh --test                                    # recria o container e testa a prova de vida
docker exec -i facecheck_api python - < scripts/liveness_test.py  # desafio, camada passiva, modelo, ponta a ponta
docker exec -i facecheck_api python - < scripts/api_test.py       # pessoas, eventos, lista, presença, CSV
docker exec -i facecheck_api python - seed  < scripts/demo_seed.py   # dados "ZZ Demo" para ver a interface
docker exec -i facecheck_api python - clean < scripts/demo_seed.py   # remove os dados "ZZ Demo"
```

Os testes criam dados com prefixo `ZZ Teste` e apagam no final. Usam as imagens de exemplo do InsightFace.

## API

| Método e rota | O que faz |
|---|---|
| `POST /api/recognize?event_id=` | Reconhece os rostos de um quadro e, com evento, aplica lista, prova de vida e registra presença |
| `POST /api/analyze` | Qualidade do enquadramento para o cadastro (posição, luz, nitidez, ângulo, foto/tela) |
| `GET/POST /api/people` · `GET/PATCH/DELETE /api/people/{id}` | Pessoas (nome, matrícula) |
| `POST /api/people/{id}/enroll` | Adiciona uma amostra facial a partir de uma foto |
| `DELETE /api/people/{id}/samples[/{amostra}]` | Apaga uma ou todas as amostras |
| `GET/POST /api/events` · `GET/PATCH/DELETE /api/events/{id}` | Eventos (`scope`, `q`, `limit`, `offset` na listagem) |
| `PUT /api/events/{id}/participants` | Substitui a lista de participantes |
| `POST/DELETE /api/events/{id}/participants/{pessoa}` | Inclui ou tira uma pessoa da lista |
| `POST /api/events/{id}/checkins` · `DELETE …/checkins/{id}` | Presença manual e desfazer presença |
| `GET /api/events/{id}/export.csv` | Relatório do evento (separador `;`, UTF-8 com BOM para o Excel) |
| `GET /api/stats` · `GET /api/health` | Indicadores do painel e estado do serviço |

## Estrutura

```
app/
  main.py            API, reconhecimento, prova de vida, esquema do banco
  models/            modelos anti-spoofing (ONNX) e manifesto
  static/            páginas (index, cadastro, admin), ui.js, cam.js, theme.js, style.css, PWA, ícones
scripts/
  setup_db.sh        cria o banco e o .env
  restart.sh         recria o container (e roda o teste de prova de vida com --test)
  api_test.py, liveness_test.py, smoke_test.sh, demo_seed.py
  convert_antispoof.sh/.py, minifasnet.py   conversão dos modelos anti-spoofing
  expose_lan.ps1     exposição na rede local (WSL2, testes)
Dockerfile, docker-compose.yml, .env.example
```

## Limites e cuidados

- **Anti-spoofing por software:** barra foto e tela parada. Um vídeo preparado da pessoa virando o rosto, numa tela
  que o modelo não reconheça, ainda pode passar. Para segurança alta, use câmera com infravermelho ou profundidade.
- **Escala:** a detecção roda no servidor (um quadro a cada ~0,6 s por terminal). Para muitos terminais
  simultâneos, considere detectar o rosto no navegador e enviar só o recorte, ou usar GPU.
- **Sem autenticação:** as páginas e a API não têm login. Não exponha na internet sem uma camada de acesso.
- **LGPD:** biometria é dado pessoal sensível. Defina a base legal, informe as pessoas, estabeleça a retenção,
  ofereça alternativa (lista, QR code, presença manual) e restrinja o acesso ao admin.

## Licenças de terceiros

| Componente | Licença | Observação |
|---|---|---|
| [InsightFace](https://github.com/deepinsight/insightface) (biblioteca) | MIT | |
| Modelos pré-treinados InsightFace (`buffalo_l`) | **Somente pesquisa não comercial** | Baixados no build da imagem. Uso comercial exige licença com a InsightFace ou outro modelo de reconhecimento. |
| [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) (MiniFASNet) | Apache 2.0 | Pesos convertidos para ONNX em `app/models/` |
| FastAPI, ONNX Runtime, OpenCV, psycopg, pgvector | MIT / Apache 2.0 / BSD | |
| Tailwind CSS (CDN), fonte Inter (Google Fonts) | MIT / OFL | Carregados da internet pelo navegador |
