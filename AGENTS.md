# AGENTS.md — caduceu-backend

Backend do sistema de gestão de Atas de Registro de Preços (ARP) da SESAP/RN —
**COADI** (Coordenadoria de Administração e Infraestrutura) / **SAS**
(Subcoordenadoria de Aquisições e Suprimentos).
FastAPI + SQLAlchemy, arquitetura **DDD + Ports & Adapters + CQRS**. Este arquivo registra as
convenções e decisões técnicas do projeto — leia-o antes de propor mudanças de código.

## Convenção de nomes: contexto + ente (context-first)

Decisão tomada em 28/09/2026 (refatoração completa aplicada): todo identificador composto segue
o padrão **contexto + ente**, nunca o contrário. Padrão antigo (ente + contexto) foi extinto.

| Conceito | Correto | Incorreto (antigo) |
|---|---|---|
| Entidade da ata (raiz do agregado) | `Arp`, `arp.py`, `ArpModel` | `PriceRegistrationAgreement`, `price_registration_agreement.py` |
| Entidade do item da ata | `ArpItem` | `ItemArp`, `ItemPriceRegistrationAgreement` |
| Entidade do pedido | `SupplyOrder` | `OrderSupply` |
| Entidade da cota | `UnitQuota` | `QuotaUnit` |
| Tabela do item | `arp_item` | `item_arp` |
| Tabela do pedido | `supply_order` | `order_supply` |
| Tabela da cota | `unit_quota` | `quota_unit` |
| Unidade Gestora (lookup) | `ManagementUnit`, `dim_management_unit` | `UnitHealth`, `unit_health`, `dim_unit_health` |
| Item do catálogo (dimensão) | `CatalogItem`, `dim_catalog_item` | `ItemCatalog`, `item_catalog`, `dim_item_catalog` |

A abreviação `Arp` é a linguagem ubíqua do domínio (termo oficial usado pela SESAP) e vale em todas
as camadas, inclusive para a raiz do agregado: `PriceRegistrationAgreement` → `Arp` e
`PriceRegistrationAgreementModel` → `ArpModel` (decisão de 14/10/2026). A exceção que mantinha o nome
completo na raiz "por já ser a raiz estabelecida" não sobrevive ao resto do código em `Arp` — a tabela
sempre foi `arp`, o port é `ArpRepository` e as rotas são `/arps`. O termo jurídico não se perde:
continua no docstring da entidade e no `arp_number` (contrato com o frontend).

A regra vale para: entidades, models ORM, tabelas, DTOs, commands/queries, handlers, schemas,
factories de DI e métodos de ports (ex.: `save_supply_order`, `execute_get_supply_order_history`).

Não valem a regra (manter como estão): nomes de comportamentos/verbo (`add_quota_unit`,
`request_supply`, `debit_quantity`), propriedades (`quota_units`, `arp_number`) e URLs/endpoints.

### Atributo no próprio contexto vs. referência — decisão de 13/10/2026

Context-first vale para **referências**. Quando o atributo é do ente que o objeto *representa*, o
prefixo é redundância e sobra só `id`/`code`. A regra vale para a camada de fio (DTOs e schemas) e,
desde 13/10/2026, também para o schema: `dim_catalog_item.code` é a PK e o adaptador não traduz mais
(`ListCatalogItemDTO(code=row.code, ...)`).

| Contexto do objeto | Atributo próprio | Referência de outro ente |
|---|---|---|
| `CatalogItem` (lookup) | `code` | — |
| `ManagementUnit` (lookup) | `id` | — |
| `Arp` (ata) | `expiration_date` | `sector_id` (referência a `dim_sector`) |
| `ArpItem` (item da ata) | — | `item_code` (vem do catálogo) |
| `UnitQuota` (cota) | — | `unit_id`, `unit_name` |

- **Coleção de lookup é sempre `items`**, independentemente do tipo — `ListManagementUnitResponseDTO`
  respondeu `units` até aqui e foi corrigido para `items`.
- **`sector_id` é o nome em toda camada** (decisão de 14/10/2026): a ata referencia `dim_sector.id`,
  então contexto+ente é `sector_id`. O `owner_` antigo descrevia um papel, não o ente; o mesmo vale
  para `dim_catalog_item`, onde `catalog_id` virou `sector_id` — o alvo sempre foi o setor dono do
  catálogo. `validate_ownership(user_sector_id)` mantém o prefixo `user_` porque compara dois setores
  e precisa dizer qual é qual.
- **Exceções por bom senso**: `arp_number` e `unit_price` ficam como estão (número da ata é contrato
  antigo com o frontend; `unit_price` é preço *por unidade de medida*, não preço da unidade gestora —
  renomear criaria ambiguidade).

### Unidade Gestora (`ManagementUnit`) — decisão de 29/09/2026

No âmbito COADI/SAS as unidades de saúde envolvidas são chamadas de **Unidades Gestoras**
(têm autonomia financeira). O conceito antes chamado `UnitHealth`/`unit_health` virou
`ManagementUnit`/`management_unit` em todas as camadas (models, DTOs, handlers, DI, rotas,
docstrings) e a tabela `dim_unit_health` foi renomeada para `dim_management_unit`.

- **Contrato**: a URL `GET /api/v1/supplies/lookups/units` permanece; o payload seguiu a regra
  de collection única (`items`) e de atributo sem prefixo no próprio contexto — hoje responde
  `{"items": [{"id", "label"}]}` (antes `{"units": [{"unit_id", "label"}]}`).
- **`UnitQuota` permanece**: o ente "cota" não mudou (`AddUnitQuotaCommand`,
  `add/adjust_unit_quota_handler`, `save_quota`, tabela `unit_quota`).
- **`ManagementUnit` está correto e não muda**: é contexto (`Management`) + ente (`Unit`),
  como `ArpItem` = Arp + Item. A dúvida sobre a ordem foi encerrada em 29/09/2026.

### Item do catálogo (`CatalogItem`) — decisão de 29/09/2026

`ItemCatalog` era a inversão ente+contexto (mesmo padrão extinto de `ItemArp`/`OrderSupply`/
`QuotaUnit`). O conceito virou **`CatalogItem`** em todas as camadas (`DimCatalogItemModel`,
`ListCatalogItemDTO`/`ListCatalogItemResponseDTO`, `ListCatalogItemQueryHandler`,
`execute_list_catalog_item`, `get_list_catalog_item_handler`, função de rota
`list_catalog_item`) e a tabela `dim_item_catalog` foi renomeada para `dim_catalog_item`
(exigiu apagar o `caduceu.db` do dev; o lifespan conta `dim_catalog_item` para rodar o seed).

- **Contrato**: URL `GET /api/v1/supplies/lookups/items` e campos JSON `items`, `description`,
  `label` permanecem; `item_code` virou `code` porque é atributo do próprio item (regra acima), e em
  13/10/2026 o mesmo valeu para a coluna da PK (`dim_catalog_item.code`).
- **`catalog_id` virou `sector_id`** (13/10/2026): a coluna sempre apontou para `dim_sector.id` — é o
  setor dono do catálogo, então o nome anterior mentia. Acompanhou o port
  (`execute_list_catalog_item(sector_id)`) e o handler.
- **`exists_in_catalog` permanece**: nome de comportamento/verbo (exceção da regra).

### Integridade referencial — decisão de 13/10/2026

Invariantes que viviam só no domínio agora também são do banco (`create_all` as gera em ambos os
ambientes):

| Constraint | Onde | Substitui o quê |
|---|---|---|
| `FK item_code → dim_catalog_item.code` | `arp_item` | só o `exists_in_catalog()` impedia código inexistente |
| `FK unit_id → dim_management_unit.id` | `unit_quota` | só o `exists_management_unit()` impedia unidade inexistente |
| `UNIQUE (arp_id, item_code)` | `arp_item` | só o `DuplicateItemException` no domínio |
| `UNIQUE (item_id, unit_id)` | `unit_quota` | só o `DuplicateQuotaException` no domínio |

- **FK sem `relationship()` e sem cascade**: `arp_item` guarda `description` e `unit_price` congelados
  na homologação (snapshot da ata, não duplicação acidental). Com relationship + join no read model a
  ata passaria a refletir o catálogo de hoje.
- **Toda escrita que recebe cota checa a unidade antes do `INSERT`** (decisão de 15/10/2026): o caminho
  granular tinha o buraco no aditivo de item — `create_arp` e `add_unit_quota` checavam
  `exists_management_unit`, `add_arp_item` passava direto e a FK devolvia `IntegrityError`, que o
  `errors.py` não conhece: 500 para o usuário que digitou uma unidade inexistente. A FK é a rede, não a
  mensagem; quem conversa com o operador é a checagem da porta.
- **`supply_order` continua sem FK** de propósito (`arp_id`, `item_code`, `unit_id` soltos): é log de
  evento imutável referenciado por identidade, lido por join explícito no `QueryService`. Não é
  esquecimento — não amarrar o histórico ao agregado vivo.
- **`PRAGMA foreign_keys=ON`** em `config.py` (listener de `connect`, montado dentro de
  `build_engine`): o SQLite não fiscaliza FK sem isso, e o pragma é por conexão. Como a engine de
  teste é criada pelo mesmo `build_engine`, a fiscalização vale na suíte de API também. No Postgres
  o bloco não roda — a fiscalização é nativa.
- **Consequências**: o `code` da COADI e o `id` da unidade viraram chaves imutáveis (referenciadas);
  e o `seed()` **recusa** rodar com atas cadastradas, porque recarregar `dim_catalog_item` /
  `dim_management_unit` apagaria referência em uso. Recriar o dev = apagar o `caduceu.db`.

## Estrutura arquitetural

- **Bounded contexts** em `app/`: `auth`, `supplies` (contexto principal) e `shared` (kernel).
- **`auth` não segue o mapa de camadas na pasta `infra/`**: suas rotas e schemas vivem em
  `app/auth/routers.py` e `app/auth/schemas.py`, e as factories de DI em `app/auth/dependencies.py`
  na raiz do contexto (mesmo padrão de `app/supplies/dependencies.py`, que também é raiz). O mapa
  abaixo descreve `supplies`, o contexto com duas portas de entrada e três adaptadores de saída.
- **Camadas por contexto**:
  - `domain/entities/` — entidades e exceções de domínio (ricas, com factories e invariantes)
  - `application/commands/` + `application/queries/` — handlers CQRS e DTOs (dataclasses frozen)
  - `application/ports/` — contratos (repository de escrita, query service de leitura)
    - **Toda port é `ABC` com `@abstractmethod`** (decisão de 15/10/2026, que uniformizou a última
      exceção: `ArpRepository`, antes classe pura com `raise NotImplementedError`). Quem omitir um
      método falha na instanciação (`TypeError`), não em runtime no meio do fluxo de negócio. Corpo do
      contrato é `pass` — e por isso o contrato não precisa de teste próprio: a cobrança é da linguagem.
  - `infra/web/` — rotas FastAPI e schemas Pydantic (adaptador de entrada)
  - `infra/database/` — models SQLAlchemy, repositórios, query service (adaptadores de saída)
  - `infra/services/` — serviços externos (ex.: JWT)
- Handlers de command retornam **apenas o ID** do recurso criado (CQRS estrito).
- Consultas nunca tocam o modelo de domínio — usam projeções via `QueryService`.
- Exceções de domínio (`BusinessRuleException`, `EntityNotFoundException` em `app/shared/domain/exceptions.py`)
  são mapeadas para HTTP em `app/shared/infra/web/errors.py` (422 / 404), registrado no boot por
  `configure_global_exception_handlers(app)` em `app/supplies/main.py`. O mapa é do kernel compartilhado,
  não do contexto: `supplies` e `auth` abrem a mesma porta de exceção. Custou uma deprecação — o
  starlette 1.x renomeou `HTTP_422_UNPROCESSABLE_ENTITY` para `..._UNPROCESSABLE_CONTENT`, e a forma
  antiga emitia `StarletteDeprecationWarning` em toda resposta 422 da suíte.

## Regras de negócio críticas (não quebrar)

- **Isolamento por setor**: toda query/command valida `sector_id` da ata contra o setor do usuário
  autenticado (`validate_ownership` na raiz do agregado). Operadores só veem/manipulam ARPs do próprio setor.
  **Não existe bypass para admin**: o `admin` (setor `GLOBAL_ADMIN`) não lista ARPs nem itens de
  catálogo — o papel dele é administrar usuários (`is_global_admin` só libera criar usuário de qualquer setor).
- Soma das cotas de um item nunca excede `total_quantity_approved`.
- Débito em cascata: valida saldo global da ARP → cota da unidade → consolida.
- Cota ajustada nunca pode ficar menor que o já consumido pela unidade.
- **`arp_number` é único no sistema, não por setor** (decisão de 15/10/2026): o índice `unique` em
  `arp.arp_number` sempre foi a regra de fato — o que faltava era torná-la legível. A checagem é da
  porta (`exists_arp_number`), porque dois agregados vivos podem carregar o mesmo número na memória:
  unicidade é invariante de repositório, não do agregado. Roda **primeiro** no `CreateArpCommandHandler`,
  antes de vencimento/catálogo/soma, para o operador saber de qual repetição trata. Sem ela o
  `IntegrityError` caía no handler genérico e virava **500**; agora é 422 com o número na mensagem.
  Consequência aceita: a janela entre checar e inserir é uma corrida, e quem perde a corrida ainda vê
  o índice — por isso a checagem não substitui o `unique`, ela só dá rosto a ele.

## Ambiente de desenvolvimento (devcontainer)

- Nada é instalado no host além do VS Code + Docker. Todo o ambiente roda no devcontainer
  (`/workspaces/caduceu-backend`).
- O `.venv` é criado pelo `postCreateCommand` do devcontainer — symlinks apontam para
  `/usr/local/bin/python`, que só existe **dentro do container**. Fora dele o venv não funciona.
- A API **não sobe automaticamente** com o container. Para rodar:
  `uvicorn app.supplies.main:app --reload` (porta 8000, encaminhada pelo VS Code).
- Banco: SQLite em `./caduceu.db` (dev) via `DATABASE_URL` (Postgres em produção).
  O lifespan do FastAPI executa `create_all` e roda o seed apenas se `dim_catalog_item` estiver vazia.
- Para recriar o banco do zero: apagar `caduceu.db` e reiniciar a API (o seed recria tudo).
- O seed carrega **apenas dados de referência** (decisão de 08/10/2026): setores, unidades gestoras,
  catálogo de insumos e o usuário `admin`. Não cria mais ARPs de exemplo nem operadores — as atas
  são cadastradas pela API e os usuários pelo admin em `POST /api/v1/auth/users`.
- Catálogo de insumos: `app/supplies/infra/database/seed_data/catalog_items.csv` (colunas
  `item_code,description,category,sector_code`), exportado da planilha oficial da COADI. O
  `sector_code` resolve para `dim_catalog_item.sector_id` através de `dim_sector.code`.
- Unidades gestoras: `app/supplies/infra/database/seed_data/management_units.csv` (colunas
  `id,name,cnpj`). **Os `id`s são estáveis** porque `unit_quota.unit_id` os referencia **com FK**
  (desde 13/10/2026) — novas unidades entram com número seguinte, nunca reaproveitar. Nomes e CNPJs levantados no CNES
  em 08/10/2026 (todas as unidades são **filiais da SESAP**, raiz `08.241.754/0001-45`; os CNPJs
  antigos do seed de dev, raiz `08.241.739`, eram inverificáveis e foram substituídos). Pendências:
  **HDMC** (sigla da planilha COADI, ainda sem correspondência no CNES), **HMPMC** (candidato forte:
  Hospital Regional da Mulher Parteira Maria Correia, Mossoró, CNES 4093577 — sigla não confirmada
  em fonte pública, deixar `cnpj` vazio até a COADI confirmar), **HETFF** (Telecila Freitas Fontes,
  Caicó, CNES 6778550) e **Ruy Pereira Dos Santos** (CNES 5314267, Natal) — fichas do CNES sem
  CNPJ próprio de unidade, `cnpj` vazio. A sigla correta da unidade de Mossoró é **HRTVM**
  (corrigida em relação ao seed antigo, que dizia HRTM); "Ruy Pereira Marinho" (seed antigo) não
  existe no CNES — o nome real é Ruy Pereira **Dos Santos**.
- Senha inicial do admin: variável de ambiente `CADUCEU_ADMIN_PASSWORD` (default de dev `admin123`),
  sempre com `must_change_password=True`.
- Senha padrão dos usuários criados pelo admin: variável `CADUCEU_DEFAULT_USER_PASSWORD`
  (`app/auth/config.py:10`, default de dev `a123456@`), lida pela rota `POST /api/v1/auth/users`
  (`app/auth/infra/web/routers.py:66`) — não pelo seed. Também sempre com `must_change_password=True`,
  e o `render.yaml` a declara `sync: false`: sem o valor no painel, o ambiente usa o default que o
  README publica.

## Contrato de API

- Prefixos: `/api/v1/supplies` e `/api/v1/auth`; login em `POST /api/v1/auth/login` (form OAuth2).
- **Campos JSON e URLs são contexto-first nas referências** (`arp_number`, `item_code`, `unit_id`,
  `/arps/{arp_id}/items`, ...) e constituem contrato com o frontend — renomear classes internas nunca
  deve alterá-los. Atributo do próprio ente responde sem prefixo (`code`, `id`); ver
  *Atributo no próprio contexto vs. referência*.
- Autenticação: JWT Bearer; papel `READ` é somente leitura (403 em commands). **Implementado como
  dependência** (15/10/2026): `get_current_writer` em `app/auth/dependencies.py` depende de
  `get_current_user` e recusa o papel `READ` antes do handler; as cinco rotas de comando usam-na, e
  as cinco de leitura seguem com `get_current_user`. Autorização separada da autenticação porque a
  regra é a mesma para todas — a checagem inline em `create_arp` era o preço de esquecer uma rota.
  Um novo comando que use `get_current_user` em vez de `get_current_writer` reabre o buraco, e o
  teste `test_the_read_role_is_refused_on_every_command_route` só pega as rotas que ele conhece.

## Testes

Suíte em `tests/`, rodando com `pytest` no devcontainer (`.venv/bin/pytest`, da raiz do repo).
Config em `pyproject.toml` (`pythonpath = ["."]` resolve os namespace packages sem hack de
`sys.path`); deps de teste em `requirements-dev.txt` — **nunca** em `requirements.txt`, que é
`pip freeze` puro e é o `buildCommand` do Render.

- **Identificador em inglês, prosa em português** (decisão de 15/10/2026): **todo** identificador de
  `tests/` fala inglês, como o código em `app/` — nome de função de teste, helper de módulo, constante
  de módulo (`SENTINELA_UNIT_ID`, `ARP_PROCESS_SEI`), parâmetro e variável local. O relatório de falha
  passa a cruzar com o nome da regra que ele protege. Docstring, comentário e mensagem de asserção
  ficam em português, que é a língua do resto do projeto — e os *valores* dos dados sentinela também
  (`"Insumo sentinela do setor SAS"` é dado, não nome). Renomear identificador nunca toca o JSON
  enviado nem a URL: o contrato com o frontend é a *chave* do dicionário, não a variável que preenche
  o valor, por isso a renomeação é por token de código e não por busca textual na string.
- **Layout espelha contexto + camada**: `tests/unit/<contexto>/<camada>/test_<unid>.py` e
  `tests/integration/<contexto>/<camada>/test_<unid>.py`, sem `__init__.py` em `tests/` (igual a
  `app/`). Consequência: basename de arquivo de teste precisa ser único no projeto.
- **Fakes substituem os ports**: `tests/fakes/arp_repository.py` (subclass da ABC `ArpRepository`,
  com *recording* por método) e `tests/fakes/query_service.py` (implementa a ABC `QueryService`
  e registra os argumentos — é assim que se prova que o `sector_id` chegou ao adaptador).
  Os `save_*` do fake só registram: não re-validam regra nem replicam a escrita, porque o fake
  guarda a **mesma instância** que o handler muta in-place.
- **`tests/builders.py`** tem as factories de cenário (`make_arp`, `make_item_with_quotas`,
  `make_arp_with_quota(consumed=...)`, `make_order`) e datas/ids fixos (`TODAY`,
  `FIXED_CREATED_AT`, `SECTOR_ID`). Builders exercitam as factories `create` do domínio; o
  construtor puro de reconstituição só aparece quando o *estado* é o objeto do teste (ex.:
  `is_active=False`) ou quando o cenário é inalcançável pelo caminho legítimo (ex.: saldo global
  menor que saldo de cota — impossível com a invariante 2 respeitada, e por isso ele prova a
  **ordem** da cascata).
- **Builder de teste é tipado** (decisão de 20/10/2026): sem `**kwargs` cru, sem
  `params = {...}; params.update(overrides); Cmd(**params)`. A factory que **constrói valor** recebe
  parâmetros nomeados tipados (`make_command(fake, arp, *, item_code: str = NEW_CODE, ...)`) — o
  `params.update()` escondia qual valor efetivo chegava ao comando, e é exatamente com esse valor que
  o fake é semeado (`fake.add_catalog_item(item_code, sector_id)`), então a forma antiga deixava verde
  um teste com catálogo errado. `Unpack[TypedDict]` só no forwarder puro
  (`_create_arp(client, headers, **fields: Unpack[PostArpOverrides])`); genérico com `TypeVar` sobre o
  dicionário não pega chave errada e foi descartado. Parâmetro de fixture é anotado com o tipo
  concreto (`fake_arp_repository: FakeArpRepository`, `session_factory: sessionmaker[Session]`) — o
  pytest injeta por nome, a anotação não interfere na resolução. Leitura de payload cru fica em
  `dict[str, Any]`: a chave é contrato de fio e é aditiva, um TypedDict ali duplicaria o schema do
  frontend e quebraria a cada campo novo. A trava é o mypy do item 1 de *Verificação*, não a revisão.
- **Regra de import**: teste unitário não importa `app.*.infra.*`, `app.supplies.main` nem
  `app.auth`. Não é estética — `app/auth/config.py` lê `os.environ["AUTH_SECRET_KEY"]` sem default,
  então um import acidental transformaria a suíte em suíte que depende de `.env`. (A engine já não é
  motivo: nada em `infra/database/config.py` abre banco no import desde 15/10/2026.) A prova é
  executável: `tests/unit/smoke/test_import_wiring.py` roda o import num **processo limpo** via
  `subprocess` — checar `sys.modules` do próprio pytest não valeria nada depois que a suíte de
  integração passou a importar `sqlalchemy` no mesmo processo.
- **Time is a parameter**: o domínio não lê o relógio do sistema. `Arp.create`/`Arp.request_supply`
  já recebiam `current_date`; desde 15/10/2026 `SupplyOrder.create` recebe `created_at: datetime`
  obrigatório e só `RequestSupplyCommandHandler.handle` tem o fallback `datetime.now(timezone.utc)`
  (mesma forma do `current_date` em `create_arp_handler`). Pendência: `login_handler` do contexto
  `auth` ainda usa `datetime.now` para expiração de JWT — relógio real é legítimo ali.
- **Composition root injetável** (decisão de 15/10/2026): `config.py` expõe `build_engine(url)`,
  `build_session_factory(engine)` e `default_session_factory()`; **nenhum deles roda no import**. A
  fábrica vive em `app.state.session_factory` e `get_db_session(request)` é a única porta do banco para
  a requisição (supplies **e** auth) — por isso `create_app(session_factory=<engine de teste>)` basta
  para apontar a aplicação inteira para outro banco, sem `dependency_overrides` e sem reatribuir nome
  de módulo. Com `bootstrap=None` o app sobe ainda sem `init_db` nem seed. O `app` de módulo
  (`app = create_app()`) continua sendo o que o uvicorn importa, com a engine do `DATABASE_URL`.
- **Suíte de API** (`tests/integration/`, `TestClient` — exige `httpx2`, que o starlette 1.x pede no
  lugar do `httpx`): o conftest define `AUTH_SECRET_KEY` antes de qualquer import de `app.*` e monta a
  engine com `build_engine` num arquivo SQLite de `tmp_path` — usar o código de produção é o que traz o
  `PRAGMA foreign_keys=ON` para o teste. O lifespan roda de verdade (`with TestClient(...)`), então o
  seed popula o banco do teste a partir dos CSVs. Prova de que a injeção pega: um marcador escrito
  direto na engine de teste aparece na resposta HTTP; não basta comparar contagens, porque o dev tem o
  mesmo seed.
- **Todo teste de rota escreve sua sentinela na engine injetada** (regra de 15/10/2026, exigida por
  mutação): com `factory = default_session_factory()` no lugar do argumento, três testes continuavam
  verdes por coincidência — admin e senha do seed são os mesmos em qualquer banco. Agora o login só
  vale com a hash reescrita *na engine do teste*, o usuário sentinela nasce e morre nela, e a rota de
  leitura só vê a linha que o teste inseriu nela. Dois casos são independentes de banco **de projeto**
  e o docstring diz por quê: `/health` com `bootstrap=None` (nenhum schema existe) e o 401 sem token,
  recusado na autenticação antes de qualquer `SELECT`. A mutação passou de "3 falham / 3 passam" para
  "6 falham / 2 passam" — os 2 exatamente esses.
- **Fluxo de escrita coberto pela borda** (`tests/integration/supplies/infra/web/test_write_flow_routes.py`,
  15/10/2026): admin cria o operador em `POST /auth/users`, o operador cadastra a ata, debita e lê saldos e
  histórico. As dimensões (item de catálogo por setor, unidade gestora) entram como sentinela escrita na
  engine do teste — o `PRAGMA foreign_keys=ON` as exige antes de qualquer asserção. Recusas cobertas: cota
  que estoura o homologado, item fora do catálogo do setor, ata de setor alheio (404 na leitura, 422 na
  escrita), ata vencida, cota ajustada abaixo do consumido, item duplicado, unidade inexistente nos dois
  caminhos que recebem cota (a avulsa e a cota inicial que vem com o item novo), número de
  ata repetido, papel `read` nos cinco comandos. Mutação em cada guarda: injeção (falham os 12 do arquivo —
  e os 6 dependentes de banco de `test_app_routes.py`), `validate_ownership` do débito, cota da
  unidade, `exists_in_catalog`, `exists_arp_number` (com a checagem desligada a borda devolve o 500 do
  `IntegrityError`), `exists_management_unit` do aditivo (sem ela o `INSERT` de `unit_quota` estoura a FK),
  vencimento, piso de consumido, `get_current_writer` — todas mortas por um
  teste específico.
- **Duas guardas que a borda não distingue**: (a) o saldo global do item nunca é a primeira recusa com as
  invariantes de pé, porque `soma das cotas ≤ total homologado` implica `saldo da cota ≤ saldo global`; só
  se distingue corrompendo o estado com `UPDATE` direto na engine — é o que
  `test_the_global_balance_blocks_before_the_quota_even_with_a_fat_quota` faz de propósito, e também
  o que prova que o adaptador reconstitui `quantity_consumed`. (b) A soma das
  cotas checada em `create_arp_handler` é **inalcançável**: `ArpItem.add_quota_unit` compara a soma acumulada
  contra o homologado a cada cota e lança antes de o laço terminar, então a mensagem do handler nunca chega
  ao cliente — mutação que desliga a checagem não mata teste nenhum, e isso é esperado, não buraco. Os dois
  níveis ficam cobertos porque é o que torna segura uma eventual unificação; o docstring do teste unitário
  é onde essa inalcançabilidade está registrada.
- **Carimbo de tempo é UTC nos dois bancos** (decisão de 15/10/2026): o SQLite não tem tipo com fuso —
  `DateTime(timezone=True)` grava a *hora de parede* do `datetime` recebido e devolve `naive`; o Postgres
  grava o instante e devolve `aware` com o fuso da sessão. Duas pontas, duas consequências: a escrita
  converte (`order.created_at.astimezone(timezone.utc)` no `save_supply_order`, para a coluna guardar o
  relógio UTC que a leitura pressupõe) e a leitura normaliza (`_iso_utc` no `QueryService` devolve
  `...+00:00` sempre — sem offset no JSON, o `Date.parse` do navegador trata a hora como local e o
  histórico sai deslocado conforme o banco). Prova: `test_supply_order_created_at_round_trip.py` escreve
  uma ordem nascida em `-03:00` e lê o mesmo instante em UTC pela borda do adaptador; com a conversão da
  escrita desligada a suíte devolve `12:00:00+00:00` — o offset presente e a hora errada, o pior tipo de
  erro porque parece correto; com a normalização da leitura desligada caem também os dois testes de rota
  que asserem o offset. É o começo do teste do adaptador isolado.
- Falta ainda: o resto do adaptador SQLAlchemy isolado (`save_new_arp`, `save_item_addition`, os ajustes
  de cota e o `find_*` reconstituindo agregado) — só o round-trip do carimbo tem esse formato hoje.

## Verificação

Antes de entregar mudanças:

1. `.venv/bin/pytest -W always` e `.venv/bin/mypy`, ambos verdes, da raiz do repo no devcontainer.
   O mypy é o portão da regra *Builder de teste é tipado*: escopo em `tests/`
   (`files = ["tests"]`, `follow_imports = "silent"` — o `app/` é lido para inferir tipo, não para
   reportar), com `disallow_untyped_defs = true` para que `**kwargs` sem tipo volte a ser erro. Ruído
   de tipo se corrige no código do teste, não com `# type: ignore` largo. Os pins do verificador vivem
   em `requirements-dev.txt`, nunca no `requirements.txt`.
2. Código novo ou alterado em `domain/` ou `application/` exige teste **escrito antes** (TDD) no
   espelho `tests/unit/`. A ordem é a do increment: teste vermelho contra o port fakeado →
   implementação mínima (regra em `domain/`, orquestração em `application/`) → refactor no verde.
   Um teste que precisa de `sqlalchemy`/`fastapi` não é unit — vai para `tests/integration/`.
3. Nenhuma mudança que toque as **Regras de negócio críticas** entra sem o teste que a protege
   (isolamento de setor, soma das cotas, débito em cascata, piso de cota consumida, vencimento,
   duplicidades — item, cota e número da ata —, `Money`). Proteção comprovada: desativar qualquer uma dessas guardas no código
   faz a suíte falhar — foi verificado por mutação em 15/10/2026.
4. O fluxo de escrita já é coberto pela suíte de API, então o smoke manual perdeu o papel de
   substituto e ficou só com o de infraestrutura: subir com `uvicorn app.supplies.main:app` e ver o
   lifespan criar schema/seed **no banco do dev** — é o único caminho que exercita o `DATABASE_URL`
   real, o pool do Postgres no Render e o `admin123`/`a123456@` de verdade.
