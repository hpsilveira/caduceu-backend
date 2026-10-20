"""Contrato da factory de `SupplyOrder`.

O teste do `created_at` verbatim é a prova da costura do relógio: a factory não pode
consultar o wall clock, porque domínio que lê hora do sistema não é determinístico —
e é justamente `SupplyOrder.create` a única impureza desse tipo no contexto `supplies`.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.supplies.domain.entities.supply_order import InvalidOrderException, SupplyOrder

FIXED_CREATED_AT = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
SENTINEL_ARP_ID = UUID("00000000-0000-0000-0000-000000000001")
SENTINEL_ITEM_CODE = "MED-4412"
SENTINEL_UNIT_ID = 101
SENTINEL_PROCESS_SEI = "01234.567890/2026-11"


def _create(
        *,
        arp_id: UUID = SENTINEL_ARP_ID,
        item_code: str = SENTINEL_ITEM_CODE,
        unit_id: int = SENTINEL_UNIT_ID,
        quantity_requested: Decimal = Decimal("10.00"),
        process_sei_request: str = SENTINEL_PROCESS_SEI,
        created_at: datetime = FIXED_CREATED_AT
    ) -> SupplyOrder:
    return SupplyOrder.create(
        arp_id=arp_id,
        item_code=item_code,
        unit_id=unit_id,
        quantity_requested=quantity_requested,
        process_sei_request=process_sei_request,
        created_at=created_at
    )


def test_request_with_non_positive_quantity_is_refused() -> None:
    for quantity in (Decimal("0.00"), Decimal("-1.00")):
        with pytest.raises(InvalidOrderException):
            _create(quantity_requested=quantity)


def test_blank_process_sei_is_refused() -> None:
    for sei in ("", "   ", "\t"):
        with pytest.raises(InvalidOrderException):
            _create(process_sei_request=sei)


def test_created_at_comes_from_the_injected_argument() -> None:
    """A factory usa o relógio que recebe — não o do sistema."""
    order = _create()

    assert order.created_at == FIXED_CREATED_AT
    assert order.created_at.tzinfo is not None


def test_valid_order_gets_an_identifier_and_echoes_the_request_data() -> None:
    arp_id = uuid4()
    order = _create(arp_id=arp_id)

    assert order.id is not None
    assert order.arp_id == arp_id
    assert order.item_code == "MED-4412"
    assert order.unit_id == 101
    assert order.quantity_requested == Decimal("10.00")
    assert order.process_sei_request == "01234.567890/2026-11"
