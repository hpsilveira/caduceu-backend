"""O `created_at` do pedido atravessa os adaptadores como instante UTC, não como hora de parede.

SQLite não tem tipo com fuso: o `DateTime(timezone=True)` grava o *relógio de parede* do `datetime`
que recebe e devolve um `naive`; o Postgres grava o instante e devolve um `aware` com o fuso da
sessão. Sem normalizar nas duas pontas, a mesma linha sai `...+00:00` num banco e sem offset no
outro, e o `Date.parse` do navegador lê a string sem offset como hora **local** — o histórico do dev
aparece horas deslocado sem que nada esteja errado no SQLite. Por isso a escrita converte para UTC
antes do `INSERT` e a leitura devolve sempre offset explícito.

É o começo do teste do adaptador isolado: `SqlAlchemyArpRepository` e `SqlAlchemyQueryService`
direto na engine injetada, sem a borda HTTP — o round-trip que importa é entre eles.
"""
from datetime import datetime, timedelta, timezone
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.supplies.application.queries.dtos import GetSupplyOrderHistoryQuery
from app.supplies.infra.database.config import init_db
from app.supplies.infra.database.models import (
    DimCatalogItemModel,
    DimManagementUnitModel,
    DimSectorModel
)
from app.supplies.infra.database.sqlalchemy_arp_repository import SqlAlchemyArpRepository
from app.supplies.infra.database.sqlalchemy_query_service import SqlAlchemyQueryService
from tests.builders import (
    ITEM_CODE,
    ITEM_DESCRIPTION,
    SECTOR_ID,
    UNIT_A,
    make_arp_with_quota,
    make_order
)

# 12:00 às 15:00 UTC. Mesmo instante, fusos diferentes — é exatamente o que o banco precisa preservar.
SAME_INSTANT_UTC = datetime(2026, 3, 1, 15, 0, 0, tzinfo=timezone.utc)
SAME_INSTANT_MINUS_3 = SAME_INSTANT_UTC.astimezone(timezone(timedelta(hours=-3)))


@pytest.fixture(autouse=True)
def _schema(engine: Engine) -> Iterator[Engine]:
    """O fixture `client` é quem dispara o lifespan; aqui não há HTTP, então o schema é criado à mão.

    `init_db` é o código de produção (o mesmo que o lifespan chama), não um `create_all` do teste —
    a fiscalização de FK que o `build_engine` do conftest liga precisa encontrar as tabelas.
    """
    init_db(engine)
    yield engine


def _dimension_rows(session_factory: sessionmaker[Session]) -> None:
    """Referências que as FK exigem, escritas na engine do teste: setor, catálogo e unidade."""
    with session_factory() as session:
        session.add(
            DimSectorModel(id=SECTOR_ID, code="SAS", name="Subcoordenadoria de Aquisições", is_active=True)
        )
        # Mappers sem `relationship()` não são ordenados por dependência de FK: sem este flush o
        # INSERT do catálogo sai na frente e o `PRAGMA foreign_keys=ON` do `build_engine` recusa.
        session.flush()
        session.add_all([
            DimCatalogItemModel(
                code=ITEM_CODE,
                description=ITEM_DESCRIPTION,
                category="TESTE",
                sector_id=SECTOR_ID
            ),
            DimManagementUnitModel(id=UNIT_A, name="Unidade Sentinela", cnpj="")
        ])
        session.commit()


def test_an_order_born_in_a_negative_offset_is_read_back_as_the_same_utc_instant(session_factory: sessionmaker[Session]) -> None:
    """A coluna `supply_order.created_at` é UTC de contrato: entra qualquer fuso, sai o instante.

    Sem a conversão na escrita, o SQLite gravaria `12:00` (a hora de parede do `-03`) e a leitura
    normalizada a accusaria de UTC — `12:00+00:00`, três horas antes do pedido real. O offset
    explícito na saída é o que impede o frontend de interpretar a hora como local.
    """
    _dimension_rows(session_factory)
    assert SAME_INSTANT_MINUS_3 == SAME_INSTANT_UTC
    arp = make_arp_with_quota()
    order = make_order(arp_id=arp.id, created_at=SAME_INSTANT_MINUS_3)

    with session_factory() as session:
        repository = SqlAlchemyArpRepository(session)
        repository.save_new_arp(arp)
        repository.save_supply_order(arp, order)

    with session_factory() as session:
        history = SqlAlchemyQueryService(session).execute_get_supply_order_history(
            GetSupplyOrderHistoryQuery(arp_id=arp.id),
            sector_id=SECTOR_ID
        )

    stamped = history.items[0].created_at
    assert stamped == "2026-03-01T15:00:00+00:00"
    assert datetime.fromisoformat(stamped) == SAME_INSTANT_UTC
