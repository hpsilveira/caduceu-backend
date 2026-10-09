# Caduceu Backend

Microserviço backend do **Caduceu**, sistema de gestão da execução de **Atas de Registro de Preços (ARP)**
da SESAP/RN (COADI/SAS). Controla saldos de ARPs, cotas por unidade gestora e o histórico de débitos
(pedidos de fornecimento), com isolamento por setor operacional.

Desenvolvido com **DDD**, **Ports & Adapters (Hexagonal)** e **CQRS**, seguindo os princípios SOLID.

## Domínio

O núcleo do negócio é o agregado `PriceRegistrationAgreement` (a ARP):

- **ArpItem** — item homologado na ata, com quantidade total aprovada, preço unitário e saldo consumido
- **UnitQuota** — cota de um item alocada a uma unidade gestora (unidade de saúde com autonomia
  financeira), com teto e consumo próprios
- **SupplyOrder** — registro histórico/transacional de cada débito executado contra a ARP

Regras de negócio garantidas no domínio:

- **Isolamento por setor** — cada ARP pertence a um setor (`owner_sector_id`); operadores só
  visualizam e manipulam atas do próprio setor
- A soma das cotas de um item nunca excede a quantidade total aprovada
- O débito valida em cascata: saldo global da ARP → cota da unidade → consolidação
- Uma cota ajustada nunca pode ficar menor que o valor já consumido pela unidade

## Arquitetura

```
app/
├── auth/                  # Contexto de autenticação e autorização
│   ├── domain/            # Entidades (User) e value objects (TokenClaims)
│   ├── application/       # Commands, queries e ports
│   └── infra/             # Web (rotas/schemas), database, services (JWT)
├── supplies/              # Contexto principal (ARP, itens, cotas, pedidos)
│   ├── domain/entities/   # ArpItem, SupplyOrder, UnitQuota, PriceRegistrationAgreement
│   ├── application/
│   │   ├── commands/      # Handlers de escrita (CQRS) + DTOs
│   │   ├── queries/       # Handlers de leitura (CQRS) + DTOs
│   │   └── ports/         # Contratos: ArpRepository, QueryService
│   └── infra/
│       ├── web/           # Adaptador de entrada: rotas FastAPI + schemas Pydantic
│       └── database/      # Adaptadores de saída: models SQLAlchemy, repositório, query service
└── shared/                # Kernel compartilhado: enums, exceções, value objects
```

Princípios aplicados:

- **CQRS estrito** — handlers de command retornam apenas o ID do recurso criado; consultas nunca
  tocam o modelo de domínio, usam projeções via `QueryService`
- **Ports & Adapters** — a aplicação depende de contratos (`application/ports`); a infraestrutura
  fornece implementações (`infra/database`), injetadas via `dependencies.py`
- **Domínio rico** — entidades com factory methods, invariantes e exceções de negócio próprias,
  mapeadas para HTTP (422 `BusinessRuleException` / 404 `EntityNotFoundException`)

## Stack

| Camada | Tecnologia |
|---|---|
| Web | FastAPI, Pydantic v2, Uvicorn |
| Persistência | SQLAlchemy 2.x (ORM tipado), SQLite (dev) / PostgreSQL (prod) |
| Autenticação | JWT (`python-jose`), `bcrypt` |
| Ambiente | Dev Containers (Docker), Python 3.14 |

## Como rodar

### Com Dev Container (recomendado)

Nada é instalado no host além do VS Code + Docker. O ambiente é criado pelo
`.devcontainer/devcontainer.json` (`postCreateCommand` cria o `.venv` e instala as dependências).

1. Abra a pasta do projeto no VS Code
2. `Reopen in Container` (Dev Containers)
3. Abra o terminal integrado (já dentro do container) e suba a API:

```bash
uvicorn app.supplies.main:app --reload
```

A API sobe em `http://localhost:8000` (porta encaminhada automaticamente pelo VS Code).

> **Observação:** o container não sobe a API sozinho — não há `postStartCommand`. O banco de dados
> `caduceu.db` é criado no *lifespan* do FastAPI na primeira execução do servidor.

### Sem Dev Container

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.supplies.main:app --reload
```

## Banco de dados e seed

- **Desenvolvimento:** SQLite em `./caduceu.db`, criado automaticamente no startup
  (variável de ambiente `DATABASE_URL`, default `sqlite:///./caduceu.db`)
- **Produção:** PostgreSQL via `DATABASE_URL` (pool configurado automaticamente quando não é SQLite)
- O seed roda apenas se o catálogo (`dim_catalog_item`) estiver vazio e carrega **somente dados de
  referência**: setores, unidades gestoras, o catálogo de insumos da COADI e o usuário `admin`.
  Nenhuma ARP é criada pelo seed — as atas são cadastradas pela API (`POST /api/v1/supplies/arps`).

Para recriar o banco do zero: apague `caduceu.db` e reinicie a API.

### Variáveis de ambiente

Em desenvolvimento elas podem vir de um arquivo `.env` na raiz do projeto (lido por
`python-dotenv`, ignorado pelo git) — cada ambiente gera o seu, nada de chave vai para o repositório.

| Variável | Default | Descrição |
|---|---|---|
| `AUTH_SECRET_KEY` | — **(obrigatória)** | Chave que assina os JWTs. Não tem default no código: sem ela a API não sobe. Gere uma por ambiente (`openssl rand -hex 32`) e mantenha fora do git — conhecê-la permite forjar tokens de qualquer usuário e setor |
| `DATABASE_URL` | `sqlite:///./caduceu.db` (só fora do Render) | Conexão com o banco. **No Render (`RENDER=true`) é obrigatória** — o app não sobe sem ela, para nunca gravar dados em SQLite efêmero |
| `CADUCEU_CORS_ORIGINS` | vazio → `*` (apenas dev) | Lista separada por vírgula das origens do frontend autorizadas (ex.: `https://caduceu-sesap.vercel.app`). Em produção, o wildcard é inaceitável com `allow_credentials` |
| `CADUCEU_ADMIN_PASSWORD` | `admin123` | Senha inicial do `admin` criada pelo seed — **sempre defina em produção** |

### Deploy (Render)

- Build: `pip install -r requirements.txt` (versões pinadas; Python 3.14 via `.python-version`)
- Start: `uvicorn app.supplies.main:app --host 0.0.0.0 --port $PORT` (Render injeta `PORT`; o default do uvicorn binda `127.0.0.1` e não funciona lá)
- Health check: `GET /health` (sem autenticação, não toca o banco)
- O seed roda automaticamente no primeiro boot (catálogo vazio); restarts e redeploys não repetem o seed

### Catálogo de insumos

O catálogo vem de `app/supplies/infra/database/seed_data/catalog_items.csv`, exportado da planilha
oficial da COADI (UTF-8, separado por vírgula, com cabeçalho):

```csv
item_code,description,category,sector_code
3046000000027,"CANUDO FLEXÍVEL, BIODEGRADÁVEL, BRANCO, PCT C/ 100",DESCARTÁVEIS,SAS
```

`sector_code` precisa corresponder a um setor existente (`SAS`, `EPA`): é ele que define a qual
catálogo setorial o item pertence (`dim_catalog_item.catalog_id`).

### Unidades gestoras

As unidades vêm de `app/supplies/infra/database/seed_data/management_units.csv` (UTF-8, com
cabeçalho):

```csv
id,name,cnpj
1,Hospital Monsenhor Walfredo Gurgel (HMWG),08241754010299
```

Nomes e CNPJs foram levantados no **CNES** — cada unidade estadual é uma filial da SESAP
(raiz `08.241.754/0001-45`), com CNPJ de filial próprio. O `cnpj` fica vazio nas unidades cuja
ficha do CNES não exibe CNPJ próprio ou cuja identificação ainda depende de confirmação com a
COADI (`HDMC`, `HMPMC`, `HETFF`, `Ruy Pereira Dos Santos`).

Os `id`s são estáveis e referenciados pelas cotas (`unit_quota.unit_id`) — ao cadastrar novas
unidades, numere em diante sem reaproveitar.

### Primeiro acesso

O seed cria apenas o `admin` (papel `admin`, setor `GLOBAL_ADMIN`) com `must_change_password=True`.
O bootstrap de um ambiente novo é:

1. `POST /api/v1/auth/login` como `admin` e depois `POST /api/v1/auth/change-password` (troca obrigatória)
2. `POST /api/v1/auth/users` para criar os operadores de cada setor (senha padrão `a123456@`,
   também com troca obrigatória no primeiro acesso)
3. Entrar como operador do setor e cadastrar as ARPs

> **O isolamento por setor vale também para o admin:** como `GLOBAL_ADMIN` não é dono de nenhuma ARP
> nem de catálogo setorial, o `admin` não lista itens nem atas (`/lookups/items` e `/arps` voltam
> vazios). O papel dele é administrar usuários; a operação é feita pelos usuários de setor.

Papéis (`UserRole`): `read` (visualizador — somente leitura, 403 em commands),
`write` (operador), `admin` (gestor).

## API

Documentação interativa em `/docs` (Swagger UI) e `/redoc`.

### Autenticação — `/api/v1/auth`

| Método | Rota | Descrição |
|---|---|---|
| POST | `/login` | Login (OAuth2 form: `username`, `password`) → retorna JWT Bearer |
| POST | `/change-password` | Troca de senha do usuário autenticado |
| POST | `/users` | Criação de usuário (somente `admin`) |
| GET | `/sectors` | Lista setores ativos |

### Suprimentos — `/api/v1/supplies`

**Commands (escrita):**

| Método | Rota | Descrição |
|---|---|---|
| POST | `/arps` | Cadastra uma nova ARP completa (com itens e cotas) |
| POST | `/arps/{arp_id}/items` | Adiciona um item homologado a uma ARP ativa |
| POST | `/arps/{arp_id}/items/{item_code}/quotas` | Cria cota de um item para uma unidade |
| PATCH | `/arps/{arp_id}/items/{item_code}/quotas/{unit_id}` | Ajusta o teto da cota de uma unidade |
| POST | `/request-supply` | Executa o débito de saldo (pedido de fornecimento) |

**Queries (leitura):**

| Método | Rota | Descrição |
|---|---|---|
| GET | `/arps` | Busca ARPs do setor (filtro `query`, paginado) |
| GET | `/arps/{arp_id}` | Detalhes completos de uma ARP (itens e cotas) |
| GET | `/arps/{arp_id}/order-history` | Histórico de pedidos, paginado (filtro `unit_id`) |
| GET | `/lookups/items` | Catálogo de itens do setor (para selects) |
| GET | `/lookups/units` | Unidades gestoras (para selects) |

Todas as rotas exigem `Authorization: Bearer <token>`. Responses de escrita seguem o padrão
`{ "id": "<uuid>", "message": "..." }`.

Exemplo — débito de saldo (o token precisa ser de um usuário do setor dono da ARP):

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=<usuario>&password=<senha>" | jq -r .access_token)

# 2. Débito
curl -X POST http://localhost:8000/api/v1/supplies/request-supply \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"arp_number":"<numero-da-arp>","item_code":"<codigo-do-item>","quantity":100,
       "unit_id":1,"process_sei_request":"00610011.000999/2026-77"}'
```

## Convenções de código

Os identificadores compostos seguem o padrão **contexto + ente** (`ArpItem`, `SupplyOrder`,
`UnitQuota`) — nunca ente + contexto. Campos JSON e URLs são parte do contrato com o frontend e
não devem ser alterados por renomeações internas.

As convenções completas, decisões de arquitetura e regras de negócio estão documentadas em
[`AGENTS.md`](AGENTS.md).

## Status

Sem suíte de testes automatizada no momento. A verificação de mudanças é feita por smoke test
manual do fluxo: login → busca de ARPs → detalhes → débito → histórico.
