"""`UnitQuota` — a cota por unidade gestora, lado interno da cascata de débito.

É a sub-entidade que faz a vez de "quanto esta unidade ainda pode retirar". O
`remaining_balance` dela é a fronteira que o `arp_item.debit_quantity` consulta no passo 2
da cascata, então o comportamento de borda (`debit == remaining`) precisa estar congelado.
"""
from decimal import Decimal

import pytest

from app.supplies.domain.entities.unit_quota import (
    InvalidQuotaException,
    QuotaExceededException,
    UnitQuota,
)
from tests.builders import UNIT_A, make_quota


def test_non_positive_quota_is_refused_by_the_factory() -> None:
    for total in (Decimal("0.00"), Decimal("-10.00")):
        with pytest.raises(InvalidQuotaException):
            UnitQuota.create(unit_id=UNIT_A, total_allocated=total)


def test_debit_above_the_quota_balance_is_refused() -> None:
    quota = make_quota(total=Decimal("10.00"))

    with pytest.raises(QuotaExceededException):
        quota.debit(Decimal("10.01"))

    assert quota.consumed == Decimal("0.00")


def test_debit_equal_to_the_available_balance_is_allowed() -> None:
    """Fronteira: esgotar a cota é legítimo, estourá-la não."""
    quota = make_quota(total=Decimal("10.00"))

    quota.debit(Decimal("10.00"))

    assert quota.consumed == Decimal("10.00")
    assert quota.remaining_balance == Decimal("0.00")


def test_non_positive_debit_is_refused() -> None:
    quota = make_quota()
    for quantity in (Decimal("0.00"), Decimal("-1.00")):
        with pytest.raises(InvalidQuotaException):
            quota.debit(quantity)


def test_debits_accumulate_and_the_balance_shrinks_each_time() -> None:
    quota = make_quota(total=Decimal("50.00"))

    quota.debit(Decimal("20.00"))
    quota.debit(Decimal("15.00"))

    assert quota.consumed == Decimal("35.00")
    assert quota.remaining_balance == Decimal("15.00")
