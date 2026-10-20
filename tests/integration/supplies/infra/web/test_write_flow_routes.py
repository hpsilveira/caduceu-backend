"""Fluxo de escrita pela borda: cadastrar → cotar → debitar, tudo HTTP, tudo na engine injetada.

Complementa `test_app_routes.py` (leitura e autenticação) com o que só a escrita prova: que o
`sector_id` do token, o snapshot do item e o débito em cascata atravessam rota → DI → adaptador →
SQLite do teste. Todo dado próprio (usuário, item de catálogo, unidade gestora, ata) nasce ou no
banco do teste (via `session_factory`, como sentinela que nenhum outro banco tem) ou por uma
chamada HTTP que escreve nele. Se o app atender pelo `caduceu.db` do ambiente, nada aqui se sustenta.

Os cenários inalcançáveis pelo caminho legítimo (ata vencida, por exemplo) são montados por
`UPDATE` direto na engine — mesma regra dos builders da suíte unitária: o estado é o objeto do teste.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, TypedDict, Unpack
from uuid import UUID

from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.supplies.infra.database.models import (
    ArpModel,
    DimCatalogItemModel,
    DimManagementUnitModel,
    UnitQuotaModel
)

SAS_SECTOR_ID = 2
EPA_SECTOR_ID = 3
ITEM_SAS = "SENTINELA-ESCRITA-0001"
ITEM_SAS_NEW = "SENTINELA-ESCRITA-0002"
ITEM_EPA = "SENTINELA-EPA-0001"
SENTINELA_UNIT_ID = 999_901
MISSING_UNIT_ID = 999_902
ARP_NUMBER = "SENTINELA-ESCRITA/2026"
ARP_PROCESS_SEI = "00610000.000001/2026-00"
ORDER_PROCESS_SEI = "00610000.000002/2026-00"
DEFAULT_PASSWORD = "a123456@"


def _decimal(value: object) -> Decimal:
    """Normaliza o Decimal do read model: o JSON pode devolvê-lo como string ou número."""
    return Decimal(str(value))


def _reference_rows(session_factory: sessionmaker[Session]) -> None:
    """Sentinelas de dimensão no banco do teste: catálogo por setor e unidade gestora."""
    with session_factory() as session:
        session.add_all([
            DimCatalogItemModel(
                code=ITEM_SAS,
                description="Insumo sentinela do setor SAS",
                category="SENTINELA",
                sector_id=SAS_SECTOR_ID
            ),
            DimCatalogItemModel(
                code=ITEM_SAS_NEW,
                description="Insumo sentinela recém-homologado do setor SAS",
                category="SENTINELA",
                sector_id=SAS_SECTOR_ID
            ),
            DimCatalogItemModel(
                code=ITEM_EPA,
                description="Insumo sentinela do setor EPA",
                category="SENTINELA",
                sector_id=EPA_SECTOR_ID
            ),
            DimManagementUnitModel(id=SENTINELA_UNIT_ID, name="Unidade Sentinela", cnpj="")
        ])
        session.commit()


def _login_token(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _new_user(
        client: TestClient,
        auth_headers: dict[str, str],
        *,
        username: str,
        role: str = "write",
        sector_code: str = "SAS"
    ) -> dict[str, str]:
    """Cria o usuário por `POST /auth/users` (só o admin pode) e devolve o header de quem nasceu."""
    response = client.post(
        "/api/v1/auth/users",
        headers=auth_headers,
        json={
            "username": username,
            "full_name": f"Usuário Sentinela {username}",
            "sector_code": sector_code,
            "role": role
        }
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {_login_token(client, username, DEFAULT_PASSWORD)}"}


class PostArpOverrides(TypedDict, total=False):
    """Os campos de `_post_arp` que um teste pode trocar — o único forwarder tipado do arquivo.

    `total=False` porque o cadastro padrão já é um payload válido: o teste nomeia só o que desvia.
    Os nomes são os **parâmetros do helper**, não as chaves do JSON — estas continuam literais em
    `_post_arp`, que é onde o contrato com o frontend é escrito.
    """
    arp_number: str
    item_code: str
    total_approved: str
    quota: str
    unit_id: int


def _post_arp(
        client: TestClient,
        headers: dict[str, str],
        *,
        arp_number: str = ARP_NUMBER,
        item_code: str = ITEM_SAS,
        total_approved: str = "100.00",
        quota: str = "40.00",
        unit_id: int = SENTINELA_UNIT_ID
    ) -> Response:
    """Cadastro completo (ata + item + cota) numa chamada; devolve a resposta crua."""
    payload: dict[str, Any] = {
        "arp_number": arp_number,
        "process_sei": ARP_PROCESS_SEI,
        "expiration_date": "2026-12-31",
        "items": [{
            "item_code": item_code,
            "description": "Insumo sentinela do setor SAS",
            "total_quantity_approved": total_approved,
            "unit_price": "12.50",
            "quotas": [{"unit_id": unit_id, "total_allocated": quota}]
        }]
    }
    return client.post(
        "/api/v1/supplies/arps",
        headers=headers,
        json=payload
    )


def _create_arp(
        client: TestClient,
        headers: dict[str, str],
        **fields: Unpack[PostArpOverrides]
    ) -> str:
    """O caminho feliz de `_post_arp`: devolve o ID criado e falha alto se a rota recusou."""
    response = _post_arp(client, headers, **fields)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _debit(
        client: TestClient,
        headers: dict[str, str],
        *,
        quantity: str = "15.00",
        arp_number: str = ARP_NUMBER,
        item_code: str = ITEM_SAS,
        unit_id: int = SENTINELA_UNIT_ID
    ) -> Response:
    return client.post(
        "/api/v1/supplies/request-supply",
        headers=headers,
        json={
            "arp_number": arp_number,
            "item_code": item_code,
            "quantity": quantity,
            "unit_id": unit_id,
            "process_sei_request": ORDER_PROCESS_SEI
        }
    )


def _get_arp(client: TestClient, headers: dict[str, str], arp_id: str) -> Response:
    return client.get(f"/api/v1/supplies/arps/{arp_id}", headers=headers)


def _get_item(arp: dict[str, Any], item_code: str = ITEM_SAS) -> dict[str, Any]:
    """Leitura do payload cru: as chaves são o contrato de fio, aditivo por natureza — por isso
    `dict[str, Any]` aqui, e não um TypedDict que duplicaria o schema do frontend e quebraria a
    cada campo novo."""
    return next(i for i in arp["items"] if i["item_code"] == item_code)


def _get_quota(item: dict[str, Any], unit_id: int = SENTINELA_UNIT_ID) -> dict[str, Any]:
    return next(q for q in item["quotas"] if q["unit_id"] == unit_id)


def _order_history(client: TestClient, headers: dict[str, str], arp_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/supplies/arps/{arp_id}/order-history", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_whole_register_to_debit_flow_goes_through_the_injected_engine(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """A linha de produção inteira: admin cria operador → operador cadastra a ata → debita → lê.

    Cada asserção depende de uma escrita anterior ter caído no banco do teste — inclusive o login
    do operador, que só existe porque o `POST /auth/users` do admin escreveu na engine injetada.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.escrita")

    arp_id = _create_arp(client, headers)

    arp_payload = _get_arp(client, headers, arp_id).json()
    assert arp_payload["arp_number"] == ARP_NUMBER
    assert arp_payload["is_active"] is True
    item = _get_item(arp_payload)
    assert _decimal(item["quantity_consumed"]) == Decimal("0.00")
    assert _decimal(_get_quota(item)["consumed"]) == Decimal("0.00")
    assert _get_quota(item)["unit_name"] == "Unidade Sentinela"

    debit_response = _debit(client, headers)
    assert debit_response.status_code == 201, debit_response.text

    item_after_debit = _get_item(_get_arp(client, headers, arp_id).json())
    assert _decimal(item_after_debit["quantity_consumed"]) == Decimal("15.00")
    assert _decimal(_get_quota(item_after_debit)["consumed"]) == Decimal("15.00")
    assert _decimal(_get_quota(item_after_debit)["total_allocated"]) == Decimal("40.00")

    history = _order_history(client, headers, arp_id)
    assert history["total_count"] == 1
    history_order = history["items"][0]
    assert history_order["id"] == debit_response.json()["id"]
    assert _decimal(history_order["quantity_requested"]) == Decimal("15.00")
    assert history_order["process_sei_request"] == ORDER_PROCESS_SEI
    assert history_order["unit_name"] == "Unidade Sentinela"
    # O SQLite devolve o carimbo sem fuso, o Postgres com o fuso da sessão: o contrato com o
    # frontend é um instante, então a borda responde UTC explícita nos dois bancos.
    assert datetime.fromisoformat(history_order["created_at"]).utcoffset() == timedelta(0)

    assert ARP_NUMBER in [a["arp_number"] for a in
                          client.get("/api/v1/supplies/arps", headers=headers).json()["items"]]


def test_a_debit_exceeding_the_quota_consumes_no_global_balance(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Débito em cascata na borda: a cota de 40 barra os 50 e o item de 100 não é tocado.

    O saldo global folgado é o que torna o cenário o pior caso da guarda de cota: se a consolidação
    acontecesse antes da validação, o item apareceria consumido 50 com a cota recusando. Aqui se prova
    o que só a borda prova — a rota devolve 422 **e** nada fica escrito: nem consumo, nem ordem no
    histórico. A ordem da cascata com as duas guardas vivas está em
    `test_the_global_balance_blocks_before_the_quota_even_with_a_fat_quota`.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.cascata")
    arp_id = _create_arp(client, headers, total_approved="100.00", quota="40.00")

    refused = _debit(client, headers, quantity="50.00")

    assert refused.status_code == 422
    item = _get_item(_get_arp(client, headers, arp_id).json())
    assert _decimal(item["quantity_consumed"]) == Decimal("0.00")
    assert _decimal(_get_quota(item)["consumed"]) == Decimal("0.00")
    assert _order_history(client, headers, arp_id)["total_count"] == 0


def test_the_global_balance_boundary_on_a_debit(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Consolidação da cascata em números: 60 + 40 esgota o item exatamente e o centavo a mais não.

    Com as invariantes de pé o saldo da cota nunca excede o saldo global, então este teste não
    distingue *qual* das duas guardas recusa — a ordem da cascata é provada na suíte unitária, com
    o estado corrompido que a API não permite construir. Aqui o que se fixa é a aritmética de
    `Money`/`Numeric(12,2)` vista pelo cliente: dígito a dígito, sem drift de arredondamento.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.fronteira")
    arp_id = _create_arp(client, headers, total_approved="100.00", quota="100.00")

    assert _debit(client, headers, quantity="60.00").status_code == 201
    assert _debit(client, headers, quantity="40.00").status_code == 201

    exhausted = _get_item(_get_arp(client, headers, arp_id).json())
    assert _decimal(exhausted["quantity_consumed"]) == Decimal("100.00")
    assert _decimal(_get_quota(exhausted)["consumed"]) == Decimal("100.00")

    excess = _debit(client, headers, quantity="0.01")
    assert excess.status_code == 422
    after = _get_item(_get_arp(client, headers, arp_id).json())
    assert _decimal(after["quantity_consumed"]) == Decimal("100.00")
    assert _decimal(_get_quota(after)["consumed"]) == Decimal("100.00")
    assert _order_history(client, headers, arp_id)["total_count"] == 2


def test_the_global_balance_blocks_before_the_quota_even_with_a_fat_quota(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Ordem da cascata na borda, com o estado que a API não produz.

    Com a invariante 2 de pé o saldo de uma cota nunca excede o saldo global do item, então pela API
    é indiferente qual das duas guardas recusa primeiro — a `UPDATE` que infla a cota acima do
    homologado é o mesmo truque do builder unitário inalcançável pelo caminho legítimo, e aqui ele
    vale o que os unitários não valem: provar que o adaptador reconstitui `quantity_consumed` (se
    perdesse o consumo lido do banco, o saldo global pareceria intacto e o débito passaria).
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.ordem")
    arp_id = _create_arp(client, headers, total_approved="100.00", quota="40.00")
    assert _debit(client, headers, quantity="40.00").status_code == 201

    with session_factory() as session:
        session.execute(
            update(UnitQuotaModel)
            .where(UnitQuotaModel.unit_id == SENTINELA_UNIT_ID)
            .values(total_allocated=Decimal("200.00"))
        )
        session.commit()

    refused = _debit(client, headers, quantity="100.00")

    assert refused.status_code == 422
    assert "saldo global" in refused.json()["detail"].lower()
    item = _get_item(_get_arp(client, headers, arp_id).json())
    assert _decimal(item["quantity_consumed"]) == Decimal("40.00")
    assert _decimal(_get_quota(item)["consumed"]) == Decimal("40.00")


def test_a_quota_exceeding_the_approved_total_leaves_no_partial_arp(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """A invariante 2 é checada antes do `save_new_arp`: a ata nem chega a existir."""
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.estouro")

    refused = _post_arp(client, headers, total_approved="10.00", quota="20.00")

    assert refused.status_code == 422
    assert client.get("/api/v1/supplies/arps", headers=headers).json()["items"] == []


def test_an_item_outside_the_sector_catalog_is_refused(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Controle positivo junto: o mesmo cadastro passa com o código do SAS e falha com o do EPA.

    Sem o primeiro, o 404 poderia ser o adaptador devolvendo falso para qualquer código — é a
    dupla que prova que o `sector_id` chegou ao `WHERE` de `exists_in_catalog`.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.catalogo")

    _create_arp(client, headers, item_code=ITEM_SAS)
    refused = _post_arp(client, headers, arp_number="SENTINELA-EPA/2026", item_code=ITEM_EPA)

    assert refused.status_code == 404
    arps = client.get("/api/v1/supplies/arps", headers=headers).json()["items"]
    assert [a["arp_number"] for a in arps] == [ARP_NUMBER]


def test_an_arp_from_another_sector_is_neither_readable_nor_debitable(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Isolamento de setor nos dois lados da fronteira: leitura some (404) e escrita recusa (422)."""
    _reference_rows(session_factory)
    sas_headers = _new_user(client, auth_headers, username="operador.sas")
    epa_headers = _new_user(
        client,
        auth_headers,
        username="operador.epa",
        sector_code="EPA"
    )
    arp_id = _create_arp(client, sas_headers)

    assert _get_arp(client, sas_headers, arp_id).status_code == 200
    assert _get_arp(client, epa_headers, arp_id).status_code == 404

    debit_response = _debit(client, epa_headers)
    assert debit_response.status_code == 422
    assert "setor" in debit_response.json()["detail"]
    assert _decimal(_get_item(_get_arp(client, sas_headers, arp_id).json())["quantity_consumed"]) == Decimal("0.00")


def test_an_expired_arp_blocks_the_debit_and_leaves_the_balance_untouched(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Vencimento pela borda, com o relógio real do handler de aplicação.

    A data é reescrita só no banco do teste: não há como injetar `current_date` pelo HTTP, e
    `Arp.create` recusa vencimento no passado, então esse é o único jeito de chegar na regra.
    O `is_active=False` que o domínio calcula ao detectar a expiração não é persistido — a
    exceção aborta antes do `save_supply_order` e o rollback fecha a sessão.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.vencida")
    arp_id = _create_arp(client, headers)
    assert _debit(client, headers).status_code == 201

    with session_factory() as session:
        session.execute(
            update(ArpModel)
            .where(ArpModel.id == UUID(arp_id))
            .values(expiration_date=date(2020, 1, 1))
        )
        session.commit()

    refused = _debit(client, headers, quantity="5.00")

    assert refused.status_code == 422
    assert "expirada" in refused.json()["detail"]
    item = _get_item(_get_arp(client, headers, arp_id).json())
    assert _decimal(item["quantity_consumed"]) == Decimal("15.00")
    with session_factory() as session:
        assert session.execute(
            select(ArpModel.is_active).where(ArpModel.id == UUID(arp_id))
        ).scalar_one() is True


def test_a_quota_adjustment_below_what_was_consumed_is_refused(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Piso da cota consumida na borda: 20 é recusado depois de consumir 30, 30 é aceito."""
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.ajuste")
    arp_id = _create_arp(client, headers, quota="40.00")
    assert _debit(client, headers, quantity="30.00").status_code == 201

    url = f"/api/v1/supplies/arps/{arp_id}/items/{ITEM_SAS}/quotas/{SENTINELA_UNIT_ID}"

    refused = client.patch(url, headers=headers, json={"new_total": "20.00"})
    assert refused.status_code == 422
    quota = _get_quota(_get_item(_get_arp(client, headers, arp_id).json()))
    assert _decimal(quota["total_allocated"]) == Decimal("40.00")

    accepted = client.patch(url, headers=headers, json={"new_total": "30.00"})
    assert accepted.status_code == 204, accepted.text
    assert _decimal(_get_quota(_get_item(_get_arp(client, headers, arp_id).json()))["total_allocated"]) == Decimal("30.00")


def test_granular_writes_refuse_a_repeated_item_and_an_unknown_unit_on_every_path(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Escritas granulares sobre uma ata existente: duplicidade de item (422) e a FK de unidade nos
    dois caminhos que recebem cota — a avulsa e a cota inicial que vem junto do item novo. O segundo
    não checava nada: virava 500 de `IntegrityError`, porque erro de integração não é regra de negócio.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.granular")
    arp_id = _create_arp(client, headers)

    duplicate = client.post(
        f"/api/v1/supplies/arps/{arp_id}/items",
        headers=headers,
        json={
            "item_code": ITEM_SAS,
            "description": "Insumo sentinela do setor SAS",
            "total_quantity_approved": "10.00",
            "unit_price": "12.50",
            "quotas": []
        }
    )
    assert duplicate.status_code == 422
    assert len(_get_arp(client, headers, arp_id).json()["items"]) == 1

    missing_unit = client.post(
        f"/api/v1/supplies/arps/{arp_id}/items/{ITEM_SAS}/quotas",
        headers=headers,
        json={"unit_id": MISSING_UNIT_ID, "total_allocated": "5.00"}
    )
    assert missing_unit.status_code == 404
    assert len(_get_item(_get_arp(client, headers, arp_id).json())["quotas"]) == 1

    bad_quota_payload: dict[str, Any] = {
        "item_code": ITEM_SAS_NEW,
        "description": "Insumo sentinela recém-homologado do setor SAS",
        "total_quantity_approved": "10.00",
        "unit_price": "12.50",
        "quotas": [{"unit_id": MISSING_UNIT_ID, "total_allocated": "10.00"}]
    }
    item_with_bad_quota = client.post(
        f"/api/v1/supplies/arps/{arp_id}/items",
        headers=headers,
        json=bad_quota_payload
    )
    assert item_with_bad_quota.status_code == 404
    # O aditivo é atômico: o item não entra pela metade quando a cota dele é recusada.
    assert [i["item_code"] for i in _get_arp(client, headers, arp_id).json()["items"]] == [ITEM_SAS]


def test_a_duplicate_arp_number_is_refused_with_422(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """O `unique` de `arp.arp_number` virando mensagem legível: antes era 500 de erro interno.

    O índice sempre existiu — o que faltava era a checagem na porta, porque `IntegrityError` não é
    regra de negócio e caía no handler genérico. Controle positivo: o operador continua conseguindo
    cadastrar a *próxima* ata, e a busca devolve exatamente a primeira, não uma meia escrita.
    """
    _reference_rows(session_factory)
    headers = _new_user(client, auth_headers, username="operador.duplicidade")
    arp_id = _create_arp(client, headers)

    repetido = _post_arp(client, headers)
    other_number = _post_arp(client, headers, arp_number="SENTINELA-ESCRITA/2027")

    assert repetido.status_code == 422
    assert ARP_NUMBER in repetido.json()["detail"]
    assert other_number.status_code == 201, other_number.text

    arps = client.get("/api/v1/supplies/arps", headers=headers).json()["items"]
    assert len(arps) == 2
    assert ARP_NUMBER in [a["arp_number"] for a in arps]
    assert _get_arp(client, headers, arp_id).json()["arp_number"] == ARP_NUMBER


def test_the_read_role_is_refused_on_every_command_route(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """O contrato de somente leitura vale para os cinco comandos, não só para `POST /arps`.

    Controle positivo embutido: o operador do mesmo setor executa as mesmas cinco ações e passa —
    sem ele, um adaptador que devolvesse 403 para todo mundo deixaria a suíte verde. A leitura da
    ata do setor permanece liberada para o leitor.
    """
    _reference_rows(session_factory)
    operator_headers = _new_user(client, auth_headers, username="operador.leitura")
    arp_id = _create_arp(client, operator_headers)
    reader_headers = _new_user(
        client,
        auth_headers,
        username="leitor.sentinela",
        role="read"
    )

    quotas_url = f"/api/v1/supplies/arps/{arp_id}/items/{ITEM_SAS}/quotas"
    actions: list[tuple[str, str, dict[str, Any]]] = [
        ("post", "/api/v1/supplies/arps", {
            "arp_number": "SENTINELA-READ/2026",
            "process_sei": ARP_PROCESS_SEI,
            "expiration_date": "2026-12-31",
            "items": []
        }),
        ("post", f"/api/v1/supplies/arps/{arp_id}/items", {
            "item_code": ITEM_EPA,
            "description": "Insumo sentinela do setor EPA",
            "total_quantity_approved": "10.00",
            "unit_price": "12.50",
            "quotas": []
        }),
        ("post", quotas_url, {"unit_id": SENTINELA_UNIT_ID, "total_allocated": "5.00"}),
        ("patch", f"{quotas_url}/{SENTINELA_UNIT_ID}", {"new_total": "50.00"}),
        ("post", "/api/v1/supplies/request-supply", {
            "arp_number": ARP_NUMBER,
            "item_code": ITEM_SAS,
            "quantity": "1.00",
            "unit_id": SENTINELA_UNIT_ID,
            "process_sei_request": ORDER_PROCESS_SEI
        })
    ]

    for method, url, body in actions:
        refused = getattr(client, method)(url, headers=reader_headers, json=body)
        assert refused.status_code == 403, (method, url, refused.text)

    assert _debit(client, operator_headers, quantity="1.00").status_code == 201
    assert client.patch(f"{quotas_url}/{SENTINELA_UNIT_ID}",
                        headers=operator_headers, json={"new_total": "35.00"}).status_code == 204
    assert _get_arp(client, reader_headers, arp_id).status_code == 200
    assert _decimal(_get_item(_get_arp(client, operator_headers, arp_id).json())["quantity_consumed"]) == Decimal("1.00")
