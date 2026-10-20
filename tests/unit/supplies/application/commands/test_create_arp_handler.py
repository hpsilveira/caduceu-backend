"""`CreateArpCommandHandler` — orquestração da criação de ata com fakes.

O handler é onde as pré-condições de infra (código no catálogo, unidade existente) encontram
as regras do domínio. Os testes de falha assertam `saved_arps == []`: criar meia ata e salvar
é o tipo de inconsistência que o repositório depois não consegue distinguir de um dado ruim.

Observação que estes testes preservam: a checagem de soma de cotas existe **em dois níveis**
(`create_arp_handler.py` e `arp_item.add_quota_unit`), e a do handler é inalcançável — as
entidades lançam antes. Não se corrige isso aqui; ter os dois níveis cobertos é o que torna
segura uma eventual unificação.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.supplies.application.commands.create_arp_handler import CreateArpCommandHandler
from app.supplies.application.commands.dtos import (
    ArpItemDTO,
    CreateArpCommand,
    UnitQuotaDTO,
)
from app.shared.domain.exceptions import BusinessRuleException, EntityNotFoundException
from app.supplies.domain.entities.arp import DuplicateArpNumberException, InvalidArpException
from tests.builders import (
    ARP_NUMBER,
    EXPIRATION_DATE,
    ITEM_CODE,
    ITEM_DESCRIPTION,
    PROCESS_SEI,
    OTHER_SECTOR_ID,
    SECTOR_ID,
    TODAY,
    UNIT_A,
    UNIT_B,
)
from tests.fakes.arp_repository import FakeArpRepository


def make_command(
        *,
        items: list[ArpItemDTO] | None = None,
        sector_id: int = SECTOR_ID,
        expiration_date: date = EXPIRATION_DATE
    ) -> CreateArpCommand:
    if items is None:
        items = [make_item_dto()]
    return CreateArpCommand(
        arp_number=ARP_NUMBER,
        process_sei=PROCESS_SEI,
        expiration_date=expiration_date,
        sector_id=sector_id,
        items=items
    )


def make_item_dto(
        *,
        code: str = ITEM_CODE,
        total: Decimal = Decimal("100.00"),
        price: Decimal = Decimal("3.50"),
        quotas: list[UnitQuotaDTO] | None = None
    ) -> ArpItemDTO:
    return ArpItemDTO(
        item_code=code,
        description=ITEM_DESCRIPTION,
        total_quantity_approved=total,
        unit_price=price,
        quotas=quotas if quotas is not None else [UnitQuotaDTO(unit_id=UNIT_A, total_allocated=Decimal("50.00"))]
    )


def seed_catalog_and_units(fake: FakeArpRepository, command: CreateArpCommand) -> None:
    """Publica no fake tudo que o handler exige que exista antes de criar a ata."""
    for item in command.items:
        fake.add_catalog_item(item.item_code, command.sector_id)
        for quota in item.quotas:
            fake.add_management_unit(quota.unit_id)


def test_creates_the_full_arp_and_persists_it_once(fake_arp_repository: FakeArpRepository) -> None:
    command = make_command()
    seed_catalog_and_units(fake_arp_repository, command)

    arp_id = CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert len(fake_arp_repository.saved_arps) == 1
    saved = fake_arp_repository.saved_arps[0]
    assert saved.id == arp_id
    assert saved.arp_number == ARP_NUMBER
    assert saved.sector_id == SECTOR_ID
    assert len(saved.items) == 1
    assert len(saved.items[0].quota_units) == 1
    # salvo quer dizer localizável: o handler devolve só o ID (CQRS estrito)
    assert fake_arp_repository.find_arp_by_id(arp_id) is saved


def test_quota_sum_above_the_approved_total_persists_nothing(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 2 na camada de aplicação."""
    command = make_command(items=[make_item_dto(
        total=Decimal("100.00"),
        quotas=[
            UnitQuotaDTO(unit_id=UNIT_A, total_allocated=Decimal("60.00")),
            UnitQuotaDTO(unit_id=UNIT_B, total_allocated=Decimal("40.01")),
        ]
    )])
    seed_catalog_and_units(fake_arp_repository, command)

    with pytest.raises(BusinessRuleException):
        CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert fake_arp_repository.saved_arps == []


def test_quota_sum_boundary_is_accepted(fake_arp_repository: FakeArpRepository) -> None:
    command = make_command(items=[make_item_dto(
        total=Decimal("100.00"),
        quotas=[
            UnitQuotaDTO(unit_id=UNIT_A, total_allocated=Decimal("60.00")),
            UnitQuotaDTO(unit_id=UNIT_B, total_allocated=Decimal("40.00")),
        ]
    )])
    seed_catalog_and_units(fake_arp_repository, command)

    CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert len(fake_arp_repository.saved_arps) == 1


def test_expiration_in_the_past_persists_nothing(fake_arp_repository: FakeArpRepository) -> None:
    """Invariante 5: a data de referência é injetada, o teste não depende do relógio."""
    command = make_command(expiration_date=date(2026, 2, 28))
    seed_catalog_and_units(fake_arp_repository, command)

    with pytest.raises(InvalidArpException):
        CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert fake_arp_repository.saved_arps == []


def test_code_outside_the_sector_catalog_is_refused(fake_arp_repository: FakeArpRepository) -> None:
    """EntityNotFound (não localizado), não InvalidItem (dados ruins): a distinção importa na rota."""
    command = make_command()

    with pytest.raises(EntityNotFoundException):
        CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert fake_arp_repository.saved_arps == []


def test_a_code_valid_in_another_sector_does_not_authorize_the_operation(fake_arp_repository: FakeArpRepository) -> None:
    """O catálogo é setorial: publicar o código no setor 2 não libera criar ata no setor 1."""
    command = make_command(sector_id=SECTOR_ID)
    fake_arp_repository.add_catalog_item(ITEM_CODE, OTHER_SECTOR_ID)
    for quota in command.items[0].quotas:
        fake_arp_repository.add_management_unit(quota.unit_id)

    with pytest.raises(EntityNotFoundException):
        CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert fake_arp_repository.saved_arps == []


def test_item_without_initial_quotas_is_accepted(fake_arp_repository: FakeArpRepository) -> None:
    """Cadastrar a ata antes de distribuir cotas entre unidades é um fluxo legítimo."""
    command = make_command(items=[make_item_dto(quotas=[])])
    seed_catalog_and_units(fake_arp_repository, command)

    CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert fake_arp_repository.saved_arps[0].items[0].quota_units == ()


def test_nonexistent_unit_persists_nothing(fake_arp_repository: FakeArpRepository) -> None:
    command = make_command()
    for item in command.items:
        fake_arp_repository.add_catalog_item(item.item_code, command.sector_id)

    with pytest.raises(EntityNotFoundException):
        CreateArpCommandHandler(fake_arp_repository).handle(command, current_date=TODAY)

    assert fake_arp_repository.saved_arps == []


def test_an_existing_arp_number_is_refused_before_building_the_aggregate(
        fake_arp_repository: FakeArpRepository
    ) -> None:
    """Unicidade de `arp_number` não é invariante do agregado — dois `Arp` vivos podem ter o mesmo
    número na memória; só o repositório sabe se ele já existe. Daí a checagem ser da porta, e a
    mensagem vir antes de qualquer regra de data, catálogo ou soma de cotas: o usuário que digitou
    o número repetido não precisa descobrir, de tabela, que o item também está fora do catálogo.
    """
    handler = CreateArpCommandHandler(fake_arp_repository)
    command = make_command()
    seed_catalog_and_units(fake_arp_repository, command)
    handler.handle(command, current_date=TODAY)

    with pytest.raises(DuplicateArpNumberException) as error:
        handler.handle(make_command(), current_date=TODAY)

    assert ARP_NUMBER in str(error.value)
    assert len(fake_arp_repository.saved_arps) == 1


def test_a_repeated_number_from_another_sector_is_also_refused(fake_arp_repository: FakeArpRepository) -> None:
    """A unicidade é global, não por setor — comportamento que o índice `unique` do banco já tinha;
    a checagem só o torna legível. Setor diferente não libera número repetido."""
    handler = CreateArpCommandHandler(fake_arp_repository)
    command = make_command()
    seed_catalog_and_units(fake_arp_repository, command)
    handler.handle(command, current_date=TODAY)

    rival_command = make_command(sector_id=OTHER_SECTOR_ID)
    fake_arp_repository.add_catalog_item(ITEM_CODE, OTHER_SECTOR_ID)

    with pytest.raises(DuplicateArpNumberException):
        handler.handle(rival_command, current_date=TODAY)

    assert len(fake_arp_repository.saved_arps) == 1
