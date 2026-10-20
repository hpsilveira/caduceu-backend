"""`Arp` — a raiz do agregado: invariantes 1, 5 e 6, mais a guarda de fronteira do agregado.

`validate_ownership` é a única porta de entrada das operações setoriais e não tem bypass —
nem para o `admin` (GLOBAL_ADMIN não lista ata nem catálogo). O teste de vencimento congela
também um efeito colateral legítimo: ao detectar que a data passou, a ata se marca inativa.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.supplies.domain.entities.arp import Arp, DuplicateItemException, InvalidArpException
from app.supplies.domain.entities.arp_item import DuplicateQuotaException
from tests.builders import (
    EXPIRATION_DATE,
    OTHER_SECTOR_ID,
    SECTOR_ID,
    TODAY,
    UNIT_A,
    UNIT_B,
    make_arp,
    make_arp_with_quota,
    make_item,
    make_item_with_quotas,
    make_quota,
)


# --- invariante 5: vencimento -------------------------------------------------
def test_arp_may_expire_on_its_creation_date_but_not_before_it() -> None:
    arp = make_arp(current_date=TODAY, expiration_date=TODAY)
    assert arp.expiration_date == TODAY

    with pytest.raises(InvalidArpException):
        make_arp(current_date=TODAY, expiration_date=date(2026, 2, 28))


def test_supply_order_after_expiration_marks_the_arp_expired() -> None:
    """Comportamento de negócio, não bug: o débito que descobre a expiração inativa a ata.

    Congelado aqui de propósito — se alguém reformular a regra, este teste falha e força a
    discussão, em vez de a mudança acontecer calada num refactor de nome.
    """
    arp = make_arp_with_quota()

    with pytest.raises(InvalidArpException):
        arp.request_supply(
            item_code="MED-4412",
            quantity=Decimal("1.00"),
            unit_id=UNIT_A,
            current_date=date(2027, 1, 1)
        )

    assert arp.is_active is False


def test_inactive_arp_does_not_allow_a_debit() -> None:
    """Estado reconstituído pelo construtor puro: é setup de estado, não atalho da factory."""
    item = make_item_with_quotas()
    arp = Arp(
        id=uuid4(),
        arp_number="ARP-002/2026",
        process_sei="01234.567890/2026-11",
        expiration_date=EXPIRATION_DATE,
        sector_id=SECTOR_ID,
        items=[item],
        is_active=False,
    )

    with pytest.raises(InvalidArpException):
        arp.request_supply(
            item_code=item.item_code,
            quantity=Decimal("1.00"),
            unit_id=UNIT_A,
            current_date=TODAY
        )

    assert item.quantity_consumed == Decimal("0.00")


# --- invariante 1: isolamento por setor, sem bypass ---------------------------
def test_validate_ownership_accepts_the_owning_sector() -> None:
    arp = make_arp(sector_id=SECTOR_ID)
    arp.validate_ownership(user_sector_id=SECTOR_ID)


def test_another_sector_cannot_operate_on_the_arp() -> None:
    arp = make_arp(sector_id=SECTOR_ID)

    with pytest.raises(BusinessRuleException):
        arp.validate_ownership(user_sector_id=OTHER_SECTOR_ID)

    with pytest.raises(BusinessRuleException):
        arp.validate_ownership(user_sector_id=0)


# --- invariante 6: unicidade de item na ata -----------------------------------
def test_items_in_the_same_arp_cannot_repeat_a_code() -> None:
    arp = make_arp()
    item = make_item()
    arp.add_item(item)

    with pytest.raises(DuplicateItemException):
        arp.add_item(make_item())
    with pytest.raises(DuplicateItemException):
        arp.add_new_item(make_item())

    assert len(arp.items) == 1


def test_add_new_item_is_the_additive_that_appends_a_new_item() -> None:
    arp = make_arp()

    arp.add_new_item(make_item(code="MED-9001"))

    assert [i.item_code for i in arp.items] == ["MED-9001"]


# --- delegação raiz > entidade interna ---------------------------------------
def test_happy_request_delegates_the_debit_to_the_arp_item() -> None:
    arp = make_arp_with_quota()
    item = arp.items[0]

    arp.request_supply(
        item_code=item.item_code,
        quantity=Decimal("10.00"),
        unit_id=UNIT_A,
        current_date=TODAY
    )

    assert item.quantity_consumed == Decimal("10.00")
    assert item.remaining_balance == Decimal("90.00")
    assert item.quota_units[0].consumed == Decimal("10.00")


def test_allocating_a_quota_on_an_item_outside_the_arp_is_refused() -> None:
    arp = make_arp()
    arp.add_item(make_item())

    with pytest.raises(EntityNotFoundException):
        arp.allocate_quota_to_item("MED-DOES-NOT-EXIST", make_quota())


def test_allocating_a_quota_through_the_root_delegates_validation_to_the_item() -> None:
    arp = make_arp()
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))])
    arp.add_item(item)

    arp.allocate_quota_to_item(item.item_code, make_quota(unit_id=UNIT_B, total=Decimal("50.00")))
    assert len(item.quota_units) == 2

    with pytest.raises(DuplicateQuotaException):
        arp.allocate_quota_to_item(item.item_code, make_quota(unit_id=UNIT_A, total=Decimal("1.00")))


# --- guarda de fronteira do agregado -----------------------------------------
def test_invariant_2_surfaces_through_the_root_when_quotas_exceed_the_total() -> None:
    """A raiz não re-valida: ela propaga a recusa do item — a invariante mora numa só classe."""
    arp = make_arp()
    item = make_item(total=Decimal("100.00"))
    arp.add_item(item)

    with pytest.raises(BusinessRuleException):
        arp.allocate_quota_to_item(item.item_code, make_quota(unit_id=UNIT_A, total=Decimal("101.00")))

    assert item.quota_units == ()


# --- coleção defensiva --------------------------------------------------------
def test_items_is_returned_as_a_defensive_tuple() -> None:
    """`items` devolve tupla: ninguém anexa item ao agregado pela beirada."""
    arp = make_arp_with_quota()
    items = arp.items

    assert isinstance(items, tuple)
    with pytest.raises(AttributeError):
        items.append(make_item())  # type: ignore[attr-defined]

    assert len(arp.items) == 1
