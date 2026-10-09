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
| Entidade do item da ata | `ArpItem` | `ItemArp`, `ItemPriceRegistrationAgreement` |
| Entidade do pedido | `SupplyOrder` | `OrderSupply` |
| Entidade da cota | `UnitQuota` | `QuotaUnit` |
| Tabela do item | `arp_item` | `item_arp` |
| Tabela do pedido | `supply_order` | `order_supply` |
| Tabela da cota | `unit_quota` | `quota_unit` |
| Unidade Gestora (lookup) | `ManagementUnit`, `dim_management_unit` | `UnitHealth`, `unit_health`, `dim_unit_health` |
| Item do catálogo (dimensão) | `CatalogItem`, `dim_catalog_item` | `ItemCatalog`, `item_catalog`, `dim_item_catalog` |

A abreviação `Arp` é a linguagem ubíqua do domínio (termo oficial usado pela SESAP) e deve ser
usada em todas as camadas — não usar a tradução completa `PriceRegistrationAgreement` em novos
identificadores (a entidade raiz `PriceRegistrationAgreement` permanece apenas por ser a raiz do
agregado já estabelecida).

A regra vale para: entidades, models ORM, tabelas, DTOs, commands/queries, handlers, schemas,
factories de DI e métodos de ports (ex.: `save_supply_order`, `execute_get_supply_order_history`).

Não valem a regra (manter como estão): nomes de comportamentos/verbo (`add_quota_unit`,
`request_supply`, `debit_quantity`), propriedades (`quota_units`, `arp_number`) e URLs/endpoints.

### Unidade Gestora (`ManagementUnit`) — decisão de 29/09/2026

No âmbito COADI/SAS as unidades de saúde envolvidas são chamadas de **Unidades Gestoras**
(têm autonomia financeira). O conceito antes chamado `UnitHealth`/`unit_health` virou
`ManagementUnit`/`management_unit` em todas as camadas (models, DTOs, handlers, DI, rotas,
docstrings) e a tabela `dim_unit_health` foi renomeada para `dim_management_unit`.

- **Contrato mantido**: a URL `GET /api/v1/supplies/lookups/units` e o campo JSON `units`
  permanecem — só a função de rota mudou de nome (`list_management_unit`).
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

- **Contrato mantido**: URL `GET /api/v1/supplies/lookups/items` e campos JSON `items`,
  `item_code`, `description`, `label`.
- **`catalog_id` permanece**: propriedade contexto+id (igual `arp_id`, `unit_id`).
- **`exists_in_catalog` permanece**: nome de comportamento/verbo (exceção da regra).

## Estrutura arquitetural

- **Bounded contexts** em `app/`: `auth`, `supplies` (contexto principal) e `shared` (kernel).
- **Camadas por contexto**:
  - `domain/entities/` — entidades e exceções de domínio (ricas, com factories e invariantes)
  - `application/commands/` + `application/queries/` — handlers CQRS e DTOs (dataclasses frozen)
  - `application/ports/` — contratos (repository de escrita, query service de leitura)
  - `infra/web/` — rotas FastAPI e schemas Pydantic (adaptador de entrada)
  - `infra/database/` — models SQLAlchemy, repositórios, query service (adaptadores de saída)
  - `infra/services/` — serviços externos (ex.: JWT)
- Handlers de command retornam **apenas o ID** do recurso criado (CQRS estrito).
- Consultas nunca tocam o modelo de domínio — usam projeções via `QueryService`.
- Exceções de domínio (`BusinessRuleException`, `EntityNotFoundException` em `app/shared/domain/exceptions.py`)
  são mapeadas para HTTP em `app/supplies/errors.py` (422 / 404).

## Regras de negócio críticas (não quebrar)

- **Isolamento por setor**: toda query/command valida `owner_sector_id` contra o setor do usuário
  autenticado (`validate_ownership` na raiz do agregado). Operadores só veem/manipulam ARPs do próprio setor.
  **Não existe bypass para admin**: o `admin` (setor `GLOBAL_ADMIN`) não lista ARPs nem itens de
  catálogo — o papel dele é administrar usuários (`is_global_admin` só libera criar usuário de qualquer setor).
- Soma das cotas de um item nunca excede `total_quantity_approved`.
- Débito em cascata: valida saldo global da ARP → cota da unidade → consolida.
- Cota ajustada nunca pode ficar menor que o já consumido pela unidade.

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
  `sector_code` resolve para `dim_catalog_item.catalog_id` através de `dim_sector.code`.
- Unidades gestoras: `app/supplies/infra/database/seed_data/management_units.csv` (colunas
  `id,name,cnpj`). **Os `id`s são estáveis** porque `unit_quota.unit_id` os referencia sem FK —
  novas unidades entram com número seguinte, nunca reaproveitar. Nomes e CNPJs levantados no CNES
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

## Contrato de API

- Prefixos: `/api/v1/supplies` e `/api/v1/auth`; login em `POST /api/v1/auth/login` (form OAuth2).
- **Campos JSON e URLs são context-first** (`arp_number`, `item_code`, `/arps/{arp_id}/items`, ...)
  e constituem contrato com o frontend — renomear classes internas nunca deve alterá-los.
- Autenticação: JWT Bearer; papel `READ` é somente leitura (403 em commands).

## Verificação

Não há suíte de testes automatizada ainda. Antes de entregar mudanças: garantir que a API sobe, o
seed roda e o fluxo funciona de ponta a ponta — login como `admin` → criação de um operador de setor
(`POST /api/v1/auth/users`, senha padrão `a123456@`) → login como esse operador → cadastro de ARP →
busca → detalhes → débito → histórico.
