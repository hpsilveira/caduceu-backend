"""`RequestSupplyCommandHandler` — o caso de uso da cascata, com fakes.

É o teste de segurança mais importante da suíte na camada de aplicação: um comando que
pertence a outro setor precisa falhar **antes** de qualquer mutação chegar ao repositório.
Os asserts `saved_orders == []` valem tanto quanto os `pytest.raises`.

Aqui também se vê o efeito da costura do relógio: `created_at` entra injetado, então a ordem
emitida é reprodutível — sem ela este arquivo precisaria de monkeypatch.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.supplies.application.commands.dtos import RequestSupplyCommand
from app.supplies.application.commands.request_supply_handler import RequestSupplyCommandHandler
from app.supplies.domain.entities.arp import InvalidArpException
from app.supplies.domain.entities.unit_quota import QuotaExceededException
from tests.builders import (
    ARP_NUMBER,
    FIXED_CREATED_AT,
    ITEM_CODE,
    PROCESS_SEI,
    SECTOR_ID,
    OTHER_SECTOR_ID,
    TODAY,
    UNIT_A,
    make_arp_with_quota,
)
from tests.fakes.arp_repository import FakeArpRepository


def make_command(
        *,
        arp_number: str = ARP_NUMBER,
        item_code: str = ITEM_CODE,
        quantity: Decimal = Decimal("10.00"),
        unit_id: int = UNIT_A,
        process_sei_request: str = PROCESS_SEI,
        sector_id: int = SECTOR_ID
    ) -> RequestSupplyCommand:
    return RequestSupplyCommand(
        arp_number=arp_number,
        item_code=item_code,
        quantity=quantity,
        unit_id=unit_id,
        process_sei_request=process_sei_request,
        sector_id=sector_id,
    )


def handle(
        fake: FakeArpRepository,
        command: RequestSupplyCommand,
        *,
        current_date: date = TODAY,
        created_at: datetime = FIXED_CREATED_AT
    ) -> UUID:
    return RequestSupplyCommandHandler(fake).handle(
        command,
        current_date=current_date,
        created_at=created_at
    )


def test_happy_debit_issues_the_order_and_updates_the_balances(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    item = arp.items[0]

    order_id = handle(fake_arp_repository, make_command())

    assert len(fake_arp_repository.saved_orders) == 1
    saved_order = fake_arp_repository.saved_orders[0]
    assert saved_order.id == order_id
    assert saved_order.arp_id == arp.id
    assert saved_order.item_code == ITEM_CODE
    assert saved_order.unit_id == UNIT_A
    assert saved_order.quantity_requested == Decimal("10.00")
    assert saved_order.created_at == FIXED_CREATED_AT
    # o agregado persistido é o mesmo que foi consolidado
    assert item.quantity_consumed == Decimal("10.00")
    assert item.quota_units[0].consumed == Decimal("10.00")


def test_another_sector_does_not_issue_an_order(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 1 — isolamento por setor não tem bypass, nem para admin."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    item = arp.items[0]

    with pytest.raises(BusinessRuleException):
        handle(fake_arp_repository, make_command(sector_id=OTHER_SECTOR_ID))

    assert fake_arp_repository.saved_orders == []
    assert item.quantity_consumed == Decimal("0.00")
    assert item.quota_units[0].consumed == Decimal("0.00")


def test_missing_arp_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    with pytest.raises(EntityNotFoundException):
        handle(fake_arp_repository, make_command(arp_number="ARP-INEXISTENTE/2026"))

    assert fake_arp_repository.saved_orders == []


def test_expired_arp_does_not_issue_an_order(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 5: o vencimento é avaliado contra a data injetada, não contra o sistema."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    item = arp.items[0]

    with pytest.raises(InvalidArpException):
        handle(fake_arp_repository, make_command(), current_date=date(2027, 1, 1))
    assert fake_arp_repository.saved_orders == []
    assert item.quantity_consumed == Decimal("0.00")


def test_overflowing_quota_issues_no_order_and_consumes_no_global_balance(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 3 ponta a ponta: a recusa da cota impede a consolidação na ata."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("5.00"))])
    fake_arp_repository.seed_arp(arp)
    item = arp.items[0]

    with pytest.raises(QuotaExceededException):
        handle(fake_arp_repository, make_command(quantity=Decimal("10.00")))

    assert fake_arp_repository.saved_orders == []
    assert item.quantity_consumed == Decimal("0.00")


def test_item_outside_the_arp_is_entity_not_found_without_issuing(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)

    with pytest.raises(EntityNotFoundException):
        handle(fake_arp_repository, make_command(item_code="MED-NAO-EXISTE"))

    assert fake_arp_repository.saved_orders == []


def test_the_route_path_without_time_injection_still_works(fake_arp_repository: FakeArpRepository) -> None:
    """A rota chama `handle(command)` sem datas — é o default de produção, não o de teste.

    Não se asserta o valor do relógio (seria testar a biblioteca-padrão e flaky por natureza);
    asserta-se apenas que o caminho sem injeção continua emitindo uma ordem carimbada.
    """
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)

    RequestSupplyCommandHandler(fake_arp_repository).handle(make_command())

    assert fake_arp_repository.saved_orders[0].created_at is not None
