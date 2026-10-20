"""`AddUnitQuotaCommandHandler` — abrir uma cota de unidade num item da ata.

Cobre as invariantes 1 (setor), 2 (soma das cotas) e 6 (unicidade por unidade) na camada de
aplicação, com o fake provando que nenhuma escrita acontece quando alguma checagem falha.
"""
from decimal import Decimal

import pytest

from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.supplies.application.commands.add_unit_quota_handler import AddUnitQuotaCommandHandler
from app.supplies.application.commands.dtos import AddUnitQuotaCommand
from app.supplies.domain.entities.arp import Arp
from app.supplies.domain.entities.arp_item import DuplicateQuotaException
from tests.builders import (
    ITEM_CODE,
    SECTOR_ID,
    OTHER_SECTOR_ID,
    UNIT_A,
    UNIT_B,
    make_arp,
    make_arp_with_quota,
)
from tests.fakes.arp_repository import FakeArpRepository


def make_command(
        fake: FakeArpRepository,
        arp: Arp,
        *,
        item_code: str = ITEM_CODE,
        unit_id: int = UNIT_B,
        total: Decimal = Decimal("30.00"),
        sector_id: int = SECTOR_ID
    ) -> AddUnitQuotaCommand:
    """Command pronto para operar: a unidade requisitante é publicada no fake junto."""
    fake.add_management_unit(unit_id)
    return AddUnitQuotaCommand(
        arp_id=arp.id,
        item_code=item_code,
        unit_id=unit_id,
        total=total,
        sector_id=sector_id,
    )


def test_opens_a_new_quota_for_the_unit_and_persists_it(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    item = arp.items[0]
    command = make_command(fake_arp_repository, arp)

    quota_id = AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert len(fake_arp_repository.saved_quotas) == 1
    item_id, quota = fake_arp_repository.saved_quotas[0]
    assert item_id == item.id
    assert quota.id == quota_id
    assert quota.unit_id == UNIT_B
    assert quota.total_allocated == Decimal("30.00")
    assert quota.consumed == Decimal("0.00")
    assert len(item.quota_units) == 2


def test_nonexistent_unit_is_refused_before_loading_the_arp(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp)
    fake_arp_repository.management_unit_ids.clear()

    with pytest.raises(EntityNotFoundException):
        AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_quotas == []


def test_missing_arp_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    """A ata do comando nunca foi semeada — só a unidade existe, e a checagem dela vem primeiro."""
    command = make_command(fake_arp_repository, make_arp())

    with pytest.raises(EntityNotFoundException):
        AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_quotas == []


def test_item_outside_the_arp_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, item_code="MED-NAO-ESTA")

    with pytest.raises(EntityNotFoundException):
        AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_quotas == []


def test_another_sector_does_not_open_a_quota(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 1: unidade e item são verificados, mas o dono da ata manda em tudo."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    item = arp.items[0]
    command = make_command(fake_arp_repository, arp, sector_id=OTHER_SECTOR_ID)

    with pytest.raises(BusinessRuleException):
        AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_quotas == []
    assert len(item.quota_units) == 1


def test_duplicate_quota_for_the_same_unit_is_refused(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 6: uma unidade, um item, uma cota."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, unit_id=UNIT_A)

    with pytest.raises(DuplicateQuotaException):
        AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_quotas == []


def test_quota_exceeding_the_approved_total_is_not_persisted(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 2: o saldo do item que não foi distribuído limita a abertura de cotas."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("80.00"))])
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, total=Decimal("21.00"))

    with pytest.raises(BusinessRuleException):
        AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_quotas == []


def test_boundary_allocating_the_whole_approved_total_is_accepted(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("80.00"))])
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, total=Decimal("20.00"))

    AddUnitQuotaCommandHandler(fake_arp_repository).handle(command)

    assert len(fake_arp_repository.saved_quotas) == 1
