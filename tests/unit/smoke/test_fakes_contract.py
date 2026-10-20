"""Contrato dos próprios fakes.

Fake com defeito é pior que ausência de fake: o teste passa (ou falha) pela razão errada.
Estes casos não testam negócio — garantem que o stub cobre o port inteiro e que o
registro de chamadas é fiel.
"""
import inspect

from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.queries.dtos import GetArpQuery
from tests.builders import ITEM_CODE, OTHER_SECTOR_ID, SECTOR_ID, UNIT_A, make_arp_with_quota
from tests.fakes.arp_repository import FakeArpRepository
from tests.fakes.query_service import FakeQueryService


def test_write_port_is_abstract_and_the_fake_covers_it_entirely() -> None:
    """Com ABC a cobertura e cobrada na instanciacao: metodo faltante seria TypeError, nao um
    NotImplementedError silencioso em meio ao fluxo de negocio."""
    assert inspect.isabstract(ArpRepository)
    assert isinstance(FakeArpRepository(), ArpRepository)


def test_seed_makes_the_arp_findable_and_operable() -> None:
    arp = make_arp_with_quota()
    fake = FakeArpRepository().seed_arp(arp)

    assert fake.find_by_arp_number(arp.arp_number) is arp
    assert fake.find_arp_by_id(arp.id) is arp
    assert fake.exists_in_catalog(ITEM_CODE, SECTOR_ID)
    assert fake.exists_management_unit(UNIT_A)


def test_fake_catalog_is_keyed_by_sector() -> None:
    fake = FakeArpRepository()
    fake.add_catalog_item(ITEM_CODE, SECTOR_ID)

    assert fake.exists_in_catalog(ITEM_CODE, SECTOR_ID)
    assert not fake.exists_in_catalog(ITEM_CODE, OTHER_SECTOR_ID)


def test_seed_can_leave_the_scenario_deliberately_incomplete() -> None:
    """`in_catalog=False` / `units_exist=False` existem para testar as pre-condicoes."""
    arp = make_arp_with_quota()
    fake = FakeArpRepository().seed_arp(arp, in_catalog=False, units_exist=False)

    assert not fake.exists_in_catalog(ITEM_CODE, SECTOR_ID)
    assert not fake.exists_management_unit(UNIT_A)


def test_save_new_arp_indexes_the_added_arp() -> None:
    arp = make_arp_with_quota()
    fake = FakeArpRepository()
    fake.save_new_arp(arp)

    assert fake.saved_arps == [arp]
    assert fake.find_arp_by_id(arp.id) is arp


def test_fake_implements_the_whole_read_port() -> None:
    """O port e abstrato de verdade, e o fake o cobre inteiro — senao nem instanciaria."""
    assert inspect.isabstract(QueryService)
    assert isinstance(FakeQueryService(), QueryService)


def test_read_port_records_the_arguments_it_received() -> None:
    fake = FakeQueryService()
    query = GetArpQuery(arp_id=make_arp_with_quota().id)

    assert fake.execute_get_arp_by_id(query, SECTOR_ID) is None
    assert fake.calls == [("execute_get_arp_by_id", (query, SECTOR_ID), {})]

    fake.execute_list_management_unit()
    assert fake.calls[1] == ("execute_list_management_unit", (), {})
