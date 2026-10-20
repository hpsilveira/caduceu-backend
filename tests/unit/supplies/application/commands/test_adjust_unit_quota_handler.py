"""`AdjustUnitQuotaCommandHandler` — recalcular o teto de uma cota já aberta.

Este é o handler da invariante 4, a mais delicada do domínio: o novo teto não pode ficar
abaixo do que a unidade já retirou. `handle` retorna `None` (não cria recurso), então o que
se asserta é o que ele pediu para persistir — e, nas falhas, que ele não pediu nada.
"""
from decimal import Decimal

import pytest

from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.supplies.application.commands.adjust_unit_quota_handler import AdjustUnitQuotaCommandHandler
from app.supplies.application.commands.dtos import AdjustUnitQuotaCommand
from app.supplies.domain.entities.arp import Arp
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
        arp: Arp,
        *,
        item_code: str = ITEM_CODE,
        unit_id: int = UNIT_A,
        new_total: Decimal = Decimal("40.00"),
        sector_id: int = SECTOR_ID
    ) -> AdjustUnitQuotaCommand:
    return AdjustUnitQuotaCommand(
        arp_id=arp.id,
        item_code=item_code,
        unit_id=unit_id,
        new_total=new_total,
        sector_id=sector_id,
    )


def test_happy_adjustment_persists_only_the_modified_quota(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    quota = arp.items[0].quota_units[0]

    # `handle` devolve `None` (CQRS estrito: ajuste não cria recurso, então não há ID a provar) —
    # o que este teste observável é a escrita.
    AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(make_command(arp))

    assert fake_arp_repository.saved_quota_adjustments == [quota]
    assert quota.total_allocated == Decimal("40.00")


def test_adjustment_below_what_was_consumed_is_not_persisted(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 4: a unidade já levou 20 — o teto não pode virar 19,99."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))], consumed=Decimal("20.00"))
    fake_arp_repository.seed_arp(arp)
    quota = arp.items[0].quota_units[0]

    with pytest.raises(BusinessRuleException):
        AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(make_command(arp, new_total=Decimal("19.99")))

    assert fake_arp_repository.saved_quota_adjustments == []
    assert quota.total_allocated == Decimal("50.00")


def test_adjustment_boundary_equal_to_the_consumed_is_accepted(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))], consumed=Decimal("20.00"))
    fake_arp_repository.seed_arp(arp)
    quota = arp.items[0].quota_units[0]

    AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(make_command(arp, new_total=Decimal("20.00")))

    assert quota.total_allocated == Decimal("20.00")
    assert fake_arp_repository.saved_quota_adjustments == [quota]


def test_adjustment_exceeding_the_quota_sum_is_refused(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 2: realocar entre unidades não pode criar quantidade do nada."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("40.00")), (UNIT_B, Decimal("40.00"))])
    fake_arp_repository.seed_arp(arp)
    quota_a = arp.items[0].quota_units[0]

    with pytest.raises(BusinessRuleException):
        AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(make_command(arp, new_total=Decimal("60.01")))

    assert fake_arp_repository.saved_quota_adjustments == []
    assert quota_a.total_allocated == Decimal("40.00")


def test_another_sector_does_not_adjust_a_quota(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 1: ajuste de teto é operação de gestor do setor, não de qualquer um."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)
    quota = arp.items[0].quota_units[0]

    with pytest.raises(BusinessRuleException):
        AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(
            make_command(arp, new_total=Decimal("45.00"), sector_id=OTHER_SECTOR_ID)
        )

    assert fake_arp_repository.saved_quota_adjustments == []
    assert quota.total_allocated == Decimal("50.00")


def test_missing_arp_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    """`make_arp()` sem `seed_arp`: o `id` gerado pela factory não está no fake."""
    with pytest.raises(EntityNotFoundException):
        AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(make_command(make_arp()))

    assert fake_arp_repository.saved_quota_adjustments == []


def test_item_outside_the_arp_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)

    with pytest.raises(EntityNotFoundException):
        AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(
            make_command(arp, item_code="MED-NAO-ESTA")
        )

    assert fake_arp_repository.saved_quota_adjustments == []


def test_adjustment_for_a_unit_without_quota_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    """O domínio não encontra a cota e o handler propaga — não se cria cota por ajuste."""
    arp = make_arp_with_quota(quotas=[(UNIT_A, Decimal("50.00"))])
    fake_arp_repository.seed_arp(arp)

    with pytest.raises(EntityNotFoundException):
        AdjustUnitQuotaCommandHandler(fake_arp_repository).handle(make_command(arp, unit_id=UNIT_B))

    assert fake_arp_repository.saved_quota_adjustments == []
    assert len(arp.items[0].quota_units) == 1
