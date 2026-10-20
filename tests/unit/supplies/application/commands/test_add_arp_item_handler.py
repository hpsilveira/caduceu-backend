"""`AddArpItemCommandHandler` — aditivo de item numa ata já existente.

A ordem das checagens deste handler é deliberada e estes testes a preservam: o catálogo é
consultado **antes** de a ata ser carregada. Um código que não existe no setor do usuário não
deve nem chegar perto de revelar a existência de uma ata. Dentro do laço de cotas, cada `unit_id`
é checado pela porta antes de virar `UnitQuota` — a FK do adaptador é a rede de segurança, não a
mensagem que o operador lê.
"""
from decimal import Decimal

import pytest

from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.supplies.application.commands.add_arp_item_handler import AddArpItemCommandHandler
from app.supplies.application.commands.dtos import AddArpItemCommand, UnitQuotaDTO
from app.supplies.domain.entities.arp import Arp, DuplicateItemException
from app.supplies.domain.entities.arp_item import InvalidItemException
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

NEW_CODE = "MED-9001"


def make_command(
        fake: FakeArpRepository,
        arp: Arp,
        *,
        item_code: str = NEW_CODE,
        sector_id: int = SECTOR_ID,
        description: str = "Luva de procedimento",
        total_quantity_approved: Decimal = Decimal("200.00"),
        unit_price: Decimal = Decimal("1.20"),
        initial_quotas: list[UnitQuotaDTO] | None = None
    ) -> AddArpItemCommand:
    fake.add_catalog_item(item_code, sector_id)
    return AddArpItemCommand(
        arp_id=arp.id,
        item_code=item_code,
        description=description,
        total_quantity_approved=total_quantity_approved,
        unit_price=unit_price,
        initial_quotas=initial_quotas or [],
        sector_id=sector_id,
    )


def test_adds_a_new_item_and_persists_only_the_addition(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp)

    item_id = AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert len(fake_arp_repository.saved_items) == 1
    arp_id, item = fake_arp_repository.saved_items[0]
    assert arp_id == arp.id
    assert item.id == item_id
    assert item.item_code == NEW_CODE
    assert item.total_value_approved.amount == Decimal("240.00")
    assert [i.item_code for i in arp.items] == [ITEM_CODE, NEW_CODE]


def test_initial_quotas_come_in_the_same_item_addition(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    # A cota inicial é referência: a unidade precisa existir no banco como as do catálogo.
    fake_arp_repository.add_management_unit(UNIT_B)
    command = make_command(
        fake_arp_repository,
        arp,
        initial_quotas=[
            UnitQuotaDTO(unit_id=UNIT_A, total_allocated=Decimal("120.00")),
            UnitQuotaDTO(unit_id=UNIT_B, total_allocated=Decimal("80.00")),
        ]
    )

    AddArpItemCommandHandler(fake_arp_repository).handle(command)

    _, item = fake_arp_repository.saved_items[0]
    assert sorted(q.unit_id for q in item.quota_units) == [UNIT_A, UNIT_B]
    assert sum(q.total_allocated for q in item.quota_units) == Decimal("200.00")


def test_code_outside_the_catalog_is_refused_before_loading_the_arp(fake_arp_repository: FakeArpRepository) -> None:
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp)
    fake_arp_repository.catalog_codes.clear()

    with pytest.raises(EntityNotFoundException):
        AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_items == []


def test_missing_arp_is_entity_not_found(fake_arp_repository: FakeArpRepository) -> None:
    """A ata do comando é `make_arp()` sem `seed_arp`: o `id` gerado pela factory não existe no fake."""
    command = make_command(fake_arp_repository, make_arp())

    with pytest.raises(EntityNotFoundException):
        AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_items == []


def test_another_sector_does_not_add_an_item(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 1: a pré-condição de setor vale também para aditivo, não só para consulta."""
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, sector_id=OTHER_SECTOR_ID)

    with pytest.raises(BusinessRuleException):
        AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_items == []
    assert len(arp.items) == 1


def test_nonexistent_quota_unit_blocks_the_addition_before_persisting(fake_arp_repository: FakeArpRepository) -> None:
    """`unit_quota.unit_id` tem FK (13/10/2026): unidade que não existe é `IntegrityError` no
    adaptador, e erro de integração não é regra de negócio — virava 500. O handler de cota avulsa
    já checava a unidade; o aditivo de item, que também recebe cotas, não checava nenhuma. A recusa
    é da porta e cai antes de `save_item_addition`, então a ata fica como estava.
    """
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    # `seed_arp` publica UNIT_A (a da cota existente na ata); UNIT_B não existe no banco do teste.
    command = make_command(
        fake_arp_repository,
        arp,
        initial_quotas=[
            UnitQuotaDTO(unit_id=UNIT_A, total_allocated=Decimal("100.00")),
            UnitQuotaDTO(unit_id=UNIT_B, total_allocated=Decimal("100.00")),
        ]
    )

    with pytest.raises(EntityNotFoundException):
        AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_items == []
    assert len(arp.items) == 1


def test_repeated_item_in_the_arp_is_refused(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 6 pelo caminho do aditivo: o código já homologado não entra duas vezes."""
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, item_code=ITEM_CODE)

    with pytest.raises(DuplicateItemException):
        AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_items == []
    assert len(arp.items) == 1


def test_bad_item_data_is_refused_by_the_domain(fake_arp_repository: FakeArpRepository) -> None:
    """O handler não re-valida o que a factory do item já guarda — ele só propaga."""
    arp = make_arp_with_quota()
    fake_arp_repository.seed_arp(arp)
    command = make_command(fake_arp_repository, arp, total_quantity_approved=Decimal("0.00"))

    with pytest.raises(InvalidItemException):
        AddArpItemCommandHandler(fake_arp_repository).handle(command)

    assert fake_arp_repository.saved_items == []
