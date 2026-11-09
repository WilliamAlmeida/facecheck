# CLAUDE.md — guia para agentes de IA neste repositório

FaceCheck: registro de presença em eventos por reconhecimento facial. API FastAPI em container
(InsightFace + MiniFASNet em ONNX, Postgres com pgvector) e três páginas estáticas (check-in, cadastro, admin)
em HTML/JS puro com Tailwind via CDN. Instalação, variáveis e arquitetura estão no `README.md`; este arquivo
cobre o que um agente precisa para **mexer** no código sem quebrar nada.

Idioma: código comentado e interface em **português do Brasil**. Mensagens de commit em português.

## Mapa do código

| Caminho | Responsabilidade |
|---|---|
| `app/main.py` | Toda a API: esquema do banco (`SCHEMA`), reconhecimento (`/api/recognize`), prova de vida (`Liveness`, `PassiveGate`, `AntiSpoof`, `run_liveness`), pessoas, eventos, participantes, check-ins, CSV, PWA |
| `app/static/index.html` | Check-in (tela de espera → leitura contínua; estados: standby, pausado, câmera indisponível, desafio) |
| `app/static/cadastro.html` | Cadastro em 3 etapas (pessoa → fotos com helper `/api/analyze` e captura AUTO → eventos) |
| `app/static/admin.html` | Painel, eventos, pessoas; tudo que é detalhe/edição abre em modal |
| `app/static/ui.js` | Cabeçalho + drawer (`UI.mount`), `UI.dialog`, `UI.confirm`, `UI.toast`, ícones (`icon(nome)`), `api()`, formatação, PWA |
| `app/static/cam.js` | Câmera: `Cam.start/stop/grab`, seletor em modal (`Cam.openPicker`), nomes amigáveis, painel de erro (`Cam.showError`) |
| `app/static/theme.js` | Remapeia as cores do Tailwind CDN para a paleta da marca (carregar logo após o script do Tailwind) |
| `app/static/style.css` | Componentes (`.btn`, `.card`, `.chip`, `.seg`, `.row-item`, `.modal`, `.switch`, `.picker`, banners, modal) |
| `app/models/` | Modelos anti-spoofing em ONNX + `antispoof.json` (versionados; regerar com `scripts/convert_antispoof.sh`) |
| `scripts/` | `setup_db.sh`, `restart.sh`, testes, seed de demonstração, conversão dos modelos |

## Fluxo de desenvolvimento

- O container monta `./app` como volume **somente leitura**. Mudanças em HTML/CSS/JS valem na hora, sem rebuild.
- **Sempre que alterar `ui.js`, `cam.js`, `theme.js` ou `style.css`, suba o `?v=N` nas três páginas** (`index.html`,
  `cadastro.html`, `admin.html`), senão o navegador do tablet segue com a versão antiga. Use o mesmo N nas três.
- Alterou `app/main.py` ou o `.env`: `bash scripts/restart.sh` (faz `down` + `up`; o `docker-compose` v1 falha com
  `KeyError: 'ContainerConfig'` ao recriar direto). Alterou `Dockerfile`/`requirements.txt`: `docker compose up -d --build`.
- Os scripts `.sh` rodam em Linux (ou WSL). No Windows, o Git normaliza para LF via `.gitattributes`; mantenha os
  `.sh` com bit executável no índice (`git update-index --chmod=+x scripts/*.sh`).
- Para alterações grandes em arquivo, prefira escrever/editar o arquivo diretamente a passar código por heredoc no
  shell: aspas e `$` dentro de JS/HTML quebram o `bash -c`.

## Testes (rodar antes de commitar mudanças na API ou na prova de vida)

```bash
docker exec -i facecheck_api python - < scripts/api_test.py        # pessoas, eventos, lista, presença, CSV
docker exec -i facecheck_api python - < scripts/liveness_test.py   # desafio, camada passiva, modelo, ponta a ponta
bash scripts/restart.sh --test                                      # recria o container e roda o liveness_test
```

- Os testes rodam **dentro do container** (precisam do InsightFace e do banco), criam dados com prefixo `ZZ Teste`
  e apagam no final. Imagens de teste vêm dos exemplos do InsightFace (`t1.jpg`), nunca de fotos de pessoas reais.
- `scripts/demo_seed.py seed|clean` cria/remove dados `ZZ Demo` para ver a interface cheia. Sempre rode `clean` depois.
- Nova rota ou regra de negócio → acrescente uma verificação no teste correspondente (padrão `check(cond, "msg")`).
- Interface: não há testes automatizados. Confira no navegador em largura de celular (375 px) e desktop, e leia o
  console. A câmera não existe em navegadores embutidos/headless: teste o fluxo com câmera num aparelho real.

## Convenções de código

**Backend (`app/main.py`)**
- Conexões via `pool.connection()` com `row_factory=dict_row`; parâmetros nomeados `%(nome)s`; helpers `row()`/`rows()`.
- Mudança de esquema = instrução **idempotente** acrescentada ao fim de `SCHEMA` (`CREATE TABLE IF NOT EXISTS`,
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Não há ferramenta de migração; o esquema roda a cada subida.
- Regras de negócio ficam no servidor: lista do evento, check-in único por pessoa/evento, prova de vida. O front só
  mostra estados; nunca confie em flag vinda do navegador para liberar presença.
- Endpoints que recebem imagem usam `UploadFile` + `decode_image`; a imagem **nunca** é gravada em disco ou banco.
- Configuração só por variável de ambiente (`os.getenv` com padrão), documentada no `.env.example` e no README.

**Frontend (`app/static/`)**
- Sem framework e sem build: HTML + JS puro + Tailwind CDN. Classes `indigo-*`/`violet-*` = vermelho da marca,
  `slate-*` = cinza neutro (ver `theme.js`); cores fixas novas devem vir da mesma paleta.
- **Sem emojis** na interface: ícones monocromáticos via `icon('nome', tamanho)` de `ui.js` (adicione novos em `PATHS`).
- Nunca `alert`/`confirm`/`prompt` nativos: use `UI.dialog`, `UI.confirm` (com `danger: true` para exclusões) e `UI.toast`.
  `<select>` só escondido; escolhas abrem em modal (`Cam.openPicker`, `openEventPicker`). Checkbox de opção = `.switch`.
- Chamadas à API via `api(path, { method, json })`; escapar texto do usuário com `esc()`.
- Textos curtos e em pt-BR; o operador pode ser leigo. Estados de erro explicam a causa e o que fazer.
- Preferências por aparelho (evento, câmera, intervalo, som, AUTO) ficam em `localStorage` com prefixo `fc_`.
- Tudo que depende da câmera recebe a classe `cam-hide` (some quando a câmera falha ou no standby).
- Páginas bloqueiam seleção de texto e menu de toque longo (quiosque); campos de texto e `.selectable` ficam livres.

## Privacidade, segurança e licenças

- Biometria é dado sensível: **nenhuma foto é guardada** (só embeddings). Não adicione logs, caches ou uploads que
  persistam quadros da câmera. Não imprima embeddings em logs.
- Nunca versione `.env`. `.env.example` usa placeholders (`TROQUE_AQUI`). Não escreva no repositório domínios,
  nomes de containers/redes de um ambiente específico, nomes de clientes ou de pessoas reais: isso fica no `.env`
  local e fora do Git. Ao gerar dados de exemplo, use nomes claramente fictícios.
- A aplicação **não tem autenticação**. Qualquer exposição pública precisa de uma camada de acesso na frente.
- Os modelos pré-treinados do InsightFace (`buffalo_l`) têm licença **não comercial**. Não apresente o projeto como
  pronto para uso comercial sem tratar isso. Os modelos anti-spoofing (MiniFASNet) são Apache 2.0.
- Ao reconverter modelos anti-spoofing, não execute código do repositório de origem: `convert_antispoof.py` usa a
  arquitetura própria em `scripts/minifasnet.py` e lê os pesos com `weights_only=True`.

## Armadilhas conhecidas

- O `#` da URL (`/admin#evento=ID`) não recarrega a página: o admin trata `hashchange`. Para ver estáticos novos,
  recarregue com cache limpo (ou mude o `?v=`).
- Serviço worker (`/sw.js`) e manifesto são servidos na **raiz** pela API (escopo do PWA). O SW não guarda páginas em
  cache de propósito; não transforme em cache offline sem rever a atualização.
- Em tela cheia, o cabeçalho só some com `body.kiosk-running` (leitura do check-in rodando). Em qualquer outra tela
  ele precisa continuar visível, senão não há como abrir o menu.
- `LIVENESS=passive` sem `app/models/antispoof.json` cai para o desafio ativo em todo check-in (com aviso no log).
- Similaridade ArcFace cai com o rosto virado; o `LIVENESS_MATCH_SLACK` tolera isso só durante um desafio já aberto.
- Modais ficam na *top layer* do navegador: o toast é movido para dentro do modal aberto (`UI.toast` já faz isso).
