"""Value object `Money` — invariante 7 do AGENTS.md (ROUND_HALF_UP, 2 casas, divisão por zero).

Tudo que passa por preço na ARP nasce daqui: `arp_item.unit_price` e `total_value_approved`.
Um centavo de erro de arredondamento num item de cem mil unidades vira diferença contábil na
página da licitação, então as casas decimais são contrato, não detalhe de implementação.
"""
from decimal import Decimal

import pytest

from app.shared.domain.exceptions import BusinessRuleException
from app.shared.domain.value_objects.shared_vo import Money


def test_rounds_half_up_with_two_decimals() -> None:
    assert Money(amount=Decimal("1.005")).amount == Decimal("1.01")
    assert Money(amount=Decimal("1.004")).amount == Decimal("1.00")
    assert Money(amount=Decimal("2.675")).amount == Decimal("2.68")


def test_precision_is_a_parameter_and_keeps_the_requested_scale() -> None:
    assert Money(amount=Decimal("1.00005")).amount == Decimal("1.00")
    assert Money(amount=Decimal("1.23456"), precision=4).amount == Decimal("1.2346")


def test_division_by_zero_becomes_an_explicit_business_rule() -> None:
    """Nada de ZeroDivisionError escapando para fora do domínio."""
    money = Money(amount=Decimal("10.00"))
    for divisor in (0, 0.0, Decimal("0"), Decimal("0.00")):
        with pytest.raises(BusinessRuleException):
            money / divisor


def test_multiplication_by_quantity_returns_a_quantized_money() -> None:
    price = Money(amount=Decimal("3.50"))

    assert price * Decimal("100.00") == Money(amount=Decimal("350.00"))
    assert price * 3 == Money(amount=Decimal("10.50"))
    assert (price * 0.33333).amount == Decimal("1.17")


def test_equality_compares_the_value_not_the_representation() -> None:
    assert Money(amount=Decimal("1.00")) == Money(amount=Decimal("1.0000"), precision=4)
    assert Money(amount=Decimal("1.00")) != Money(amount=Decimal("1.01"))
