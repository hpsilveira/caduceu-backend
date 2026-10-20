"""`ArpItem` — invariantes 2, 3, 4 e 6 do AGENTS.md.

O item é a peça onde as regras de saldo se encontram: a soma das cotas não pode passar do
homologado (2), o débito valida em cascata global → cota → consolidação (3), a cota ajustada
não pode ficar abaixo do que a unidade já consumiu (4) e uma unidade não pode ter duas cotas
no mesmo item (6). Todo teste de falha também asserta que **nada foi consolidado**: a ordem
dos passos da cascata é parte do contrato, não detalhe de implementação.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.shared.domain.value_objects.shared_vo import Money
from app.supplies.domain.entities.arp_item import (
    ArpItem,
    DuplicateQuotaException,
    InsufficientBalanceException,
    InvalidItemException,
)
from app.supplies.domain.entities.unit_quota import QuotaExceededException, UnitQuota
from tests.builders import (
    ITEM_CODE,
    ITEM_DESCRIPTION,
    UNIT_A,
    UNIT_B,
    make_item,
    make_item_with_quotas,
    make_money,
    make_quota,
)


# --- factory -----------------------------------------------------------------
def test_item_with_non_positive_data_is_refused_by_the_factory() -> None:
    with pytest.raises(InvalidItemException):
        make_item(total=Decimal("0.00"))
    with pytest.raises(InvalidItemException):
        make_item(total=Decimal("-1.00"))
    with pytest.raises(InvalidItemException):
        make_item(price=make_money("0.00"))


def test_total_value_approved_is_price_times_the_approved_quantity() -> None:
    item = make_item(total=Decimal("100.00"), price=make_money("3.50"))

    assert item.total_value_approved == Money(amount=Decimal("350.00"))


# --- invariante 6: uma cota por unidade ------------------------------------
def test_add_quota_unit_refuses_a_repeated_unit() -> None:
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("40.00"))])

    with pytest.raises(DuplicateQuotaException):
        item.add_quota_unit(make_quota(unit_id=UNIT_A, total=Decimal("10.00")))

    assert len(item.quota_units) == 1


# --- invariante 2: soma das cotas <= homologado -----------------------------
def test_allocation_exceeding_the_approved_total_is_refused() -> None:
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("70.00"))], total=Decimal("100.00"))

    with pytest.raises(BusinessRuleException):
        item.add_quota_unit(make_quota(unit_id=UNIT_B, total=Decimal("30.01")))

    assert len(item.quota_units) == 1


def test_exact_boundary_of_the_quota_sum_is_allowed() -> None:
    """Distribuir 100% do homologado entre unidades é o cenário desejado, não um estouro."""
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("70.00"))], total=Decimal("100.00"))

    item.add_quota_unit(make_quota(unit_id=UNIT_B, total=Decimal("30.00")))

    assert sum(q.total_allocated for q in item.quota_units) == Decimal("100.00")


# --- invariante 3: ordem da cascata de débito -------------------------------
def test_debit_with_non_positive_quantity_is_refused() -> None:
    item = make_item_with_quotas()
    for quantity in (Decimal("0.00"), Decimal("-5.00")):
        with pytest.raises(InvalidItemException):
            item.debit_quantity(quantity, UNIT_A)


def test_insufficient_global_balance_blocks_the_debit_before_touching_the_quota() -> None:
    """Prova do passo 1 da cascata.

    Aqui o agregado é montado pelo construtor puro, e não pela factory, de propósito: com a
    invariante 2 respeitada, o saldo global nunca é menor que o saldo de uma cota, então esse
    estado é inalcançável pelo caminho legítimo. É justamente por isso que ele prova a *ordem*
    das checagens — a parede de fora da ata é o saldo global, não a cota da unidade.
    """
    quota = UnitQuota(
        id=uuid4(),
        unit_id=UNIT_A,
        total_allocated=Decimal("50.00"),
        consumed=Decimal("0.00"),
    )
    item = ArpItem(
        id=uuid4(),
        item_code=ITEM_CODE,
        description=ITEM_DESCRIPTION,
        total_quantity_approved=Decimal("100.00"),
        quantity_consumed=Decimal("95.00"),
        unit_price=make_money("3.50"),
        quota_units=[quota],
    )

    with pytest.raises(InsufficientBalanceException):
        item.debit_quantity(Decimal("10.00"), UNIT_A)

    assert item.quantity_consumed == Decimal("95.00")
    assert quota.consumed == Decimal("0.00")


def test_debit_for_a_unit_without_quota_is_refused_without_consuming_global_balance() -> None:
    """Passo 2: a unidade precisa ter cota autorizada antes de qualquer débito ser registrado."""
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))])

    with pytest.raises(EntityNotFoundException):
        item.debit_quantity(Decimal("10.00"), UNIT_B)

    assert item.quantity_consumed == Decimal("0.00")
    assert item.remaining_balance == Decimal("100.00")


def test_overflowing_quota_blocks_the_global_balance_consolidation() -> None:
    """Passos 3 → 4: se a cota recusou, a ata não pode ter registrado o consumo."""
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("20.00"))], total=Decimal("100.00"))

    with pytest.raises(QuotaExceededException):
        item.debit_quantity(Decimal("30.00"), UNIT_A)

    assert item.quantity_consumed == Decimal("0.00")
    assert item.quota_units[0].consumed == Decimal("0.00")


def test_happy_debit_consolidates_item_and_quota_together() -> None:
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))], total=Decimal("100.00"))

    item.debit_quantity(Decimal("30.00"), UNIT_A)

    assert item.quantity_consumed == Decimal("30.00")
    assert item.remaining_balance == Decimal("70.00")
    assert item.quota_units[0].consumed == Decimal("30.00")
    assert item.quota_units[0].remaining_balance == Decimal("20.00")


# --- invariantes 2 e 4 no ajuste de cota ------------------------------------
def test_adjustment_for_a_unit_without_quota_is_refused() -> None:
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))])

    with pytest.raises(EntityNotFoundException):
        item.adjust_quota_allocation(UNIT_B, Decimal("10.00"))


def test_adjustment_exceeding_the_quota_sum_is_refused() -> None:
    item = make_item_with_quotas(
        quotas=[(UNIT_A, Decimal("40.00")), (UNIT_B, Decimal("40.00"))],
        total=Decimal("100.00")
    )

    with pytest.raises(BusinessRuleException):
        item.adjust_quota_allocation(UNIT_A, Decimal("60.01"))

    assert item.quota_units[0].total_allocated == Decimal("40.00")


def test_adjusted_quota_cannot_drop_below_what_was_already_consumed() -> None:
    """Invariante 4 — a mais crítica do repo: o ajuste não pode invalidar o histórico.

    `consumed` é fato registrado (com `supply_order` no log imutável); reduzir o teto abaixo
    dele deixaria a unidade devendo saldo que já retirou da ata.
    """
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))], total=Decimal("100.00"))
    item.debit_quantity(Decimal("20.00"), UNIT_A)

    with pytest.raises(BusinessRuleException):
        item.adjust_quota_allocation(UNIT_A, Decimal("19.99"))

    assert item.quota_units[0].total_allocated == Decimal("50.00")


def test_adjustment_boundary_equal_to_the_consumed_is_allowed() -> None:
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))], total=Decimal("100.00"))
    item.debit_quantity(Decimal("20.00"), UNIT_A)

    item.adjust_quota_allocation(UNIT_A, Decimal("20.00"))

    assert item.quota_units[0].total_allocated == Decimal("20.00")
    assert item.quota_units[0].remaining_balance == Decimal("0.00")


def test_happy_adjustment_mutates_the_same_quota_instance_in_the_aggregate() -> None:
    """`adjust_quota_allocation` escreve via `object.__setattr__` — a coleção não é recriada."""
    item = make_item_with_quotas(quotas=[(UNIT_A, Decimal("50.00"))], total=Decimal("100.00"))
    quota = item.quota_units[0]

    item.adjust_quota_allocation(UNIT_A, Decimal("80.00"))

    assert item.quota_units[0] is quota
    assert quota.total_allocated == Decimal("80.00")
