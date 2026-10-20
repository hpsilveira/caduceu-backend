"""Constructors de objetos de domínio válidos, com defaults que não mudam.

Funções puras em vez de fixtures: teste de domínio não deve depender de fixture com
estado compartilhado, e cada caso só nomeia o parâmetro que ele realmente altera — o
restante vem dos padrões abaixo, que são fixos e não calandrados. Builders exercitam
**exclusivamente as factories `create`**; o construtor puro de reconstituição é testado
pelo repositório SQLAlchemy (incremento 2), porque é ele que a infra usa para remontar
o agregado a partir de linhas.

Datas são constantes, nunca `date.today()`: teste que depende do relógio do sistema
passa hoje e falha numa terça-feira qualquer.

Nota: os DTOs de comando em `application/commands/dtos.py` têm forward-refs resolvidos
preguiçosamente (PEP 649 / Python 3.14). Instanciá-los funciona; inspecioná-los com
`typing.get_type_hints()` antes do módulo terminar de carregar daria `NameError` — por
isso nenhum builder aqui introspeciona tipos.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.shared.domain.value_objects.shared_vo import Money
from app.supplies.domain.entities.arp import Arp
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.supply_order import SupplyOrder
from app.supplies.domain.entities.unit_quota import UnitQuota

# --- parâmetros padrão: qualquer teste pode contar com estes valores ---
TODAY = date(2026, 3, 1)
EXPIRATION_DATE = date(2026, 12, 31)
FIXED_CREATED_AT = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

SECTOR_ID = 1
OTHER_SECTOR_ID = 2
UNIT_A = 101
UNIT_B = 102

ITEM_CODE = "MED-4412"
ITEM_DESCRIPTION = "Soro fisiologico 0,9%"
ITEM_TOTAL = Decimal("100.00")
ITEM_QUOTA = Decimal("50.00")
UNIT_PRICE = Decimal("3.50")
ARP_NUMBER = "ARP-001/2026"
PROCESS_SEI = "01234.567890/2026-11"


def make_money(amount: str | Decimal = "10.00", precision: int = 2) -> Money:
    return Money(amount=Decimal(str(amount)), precision=precision)


def make_arp(
        *,
        arp_number: str = ARP_NUMBER,
        process_sei: str = PROCESS_SEI,
        expiration_date: date = EXPIRATION_DATE,
        sector_id: int = SECTOR_ID,
        current_date: date = TODAY
    ) -> Arp:
    """Ata válida criada pela factory da raiz do agregado."""
    return Arp.create(
        arp_number=arp_number,
        process_sei=process_sei,
        expiration_date=expiration_date,
        sector_id=sector_id,
        current_date=current_date
    )


def make_item(
        *,
        code: str = ITEM_CODE,
        description: str = ITEM_DESCRIPTION,
        total: Decimal = ITEM_TOTAL,
        price: Money | None = None
    ) -> ArpItem:
    return ArpItem.create(
        item_code=code,
        description=description,
        total_quantity_approved=total,
        unit_price=price if price is not None else make_money(UNIT_PRICE)
    )


def make_quota(*, unit_id: int = UNIT_A, total: Decimal = ITEM_QUOTA) -> UnitQuota:
    return UnitQuota.create(unit_id=unit_id, total_allocated=total)


def make_item_with_quotas(
        *,
        quotas: list[tuple[int, Decimal]] | None = None,
        code: str = ITEM_CODE,
        description: str = ITEM_DESCRIPTION,
        total: Decimal = ITEM_TOTAL,
        price: Money | None = None
    ) -> ArpItem:
    """Item do agregado já com suas cotas — o caminho legítimo, via `add_quota_unit`."""
    item = make_item(code=code, description=description, total=total, price=price)
    for unit_id, quota_total in (quotas if quotas is not None else [(UNIT_A, ITEM_QUOTA)]):
        item.add_quota_unit(make_quota(unit_id=unit_id, total=quota_total))
    return item


def make_arp_with_items(
        *,
        items: list[ArpItem],
        arp_number: str = ARP_NUMBER,
        process_sei: str = PROCESS_SEI,
        expiration_date: date = EXPIRATION_DATE,
        sector_id: int = SECTOR_ID,
        current_date: date = TODAY
    ) -> Arp:
    arp = make_arp(
        arp_number=arp_number,
        process_sei=process_sei,
        expiration_date=expiration_date,
        sector_id=sector_id,
        current_date=current_date
    )
    for item in items:
        arp.add_item(item)
    return arp


def make_arp_with_quota(
        *,
        quotas: list[tuple[int, Decimal]] | None = None,
        consumed: Decimal = Decimal("0.00"),
        unit_id: int = UNIT_A,
        total: Decimal = ITEM_TOTAL
    ) -> Arp:
    """Cenário padrão dos testes de débito: ata > item > cota, com saldo consumido real.

    `consumed` entra pelo caminho legítimo (`Arp.request_supply`), nunca escrevendo em
    atributo privado — se a cascata estiver errada, o builder propaga o erro em vez de
    mascarar o teste.
    """
    item = make_item_with_quotas(quotas=quotas, total=total)
    arp = make_arp_with_items(items=[item])
    if consumed > Decimal("0.00"):
        consume(arp, quantity=consumed, unit_id=unit_id, item_code=item.item_code)
    return arp


def consume(
        arp: Arp,
        *,
        quantity: Decimal,
        unit_id: int = UNIT_A,
        item_code: str = ITEM_CODE,
        current_date: date = TODAY
    ) -> None:
    arp.request_supply(
        item_code=item_code,
        quantity=quantity,
        unit_id=unit_id,
        current_date=current_date
    )


def make_order(
        *,
        arp_id: UUID | None = None,
        item_code: str = ITEM_CODE,
        unit_id: int = UNIT_A,
        quantity: Decimal = Decimal("10.00"),
        process_sei_request: str = PROCESS_SEI,
        created_at: datetime = FIXED_CREATED_AT
    ) -> SupplyOrder:
    return SupplyOrder.create(
        arp_id=arp_id if arp_id is not None else UUID("00000000-0000-0000-0000-000000000001"),
        item_code=item_code,
        unit_id=unit_id,
        quantity_requested=quantity,
        process_sei_request=process_sei_request,
        created_at=created_at
    )
