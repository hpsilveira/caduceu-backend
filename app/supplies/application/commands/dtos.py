from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

# =========================================================================
# THE COMMAND DTO
# =========================================================================
@dataclass(frozen=True)
class CreateArpCommand:
    arp_number: str
    process_sei: str
    expiration_date: date
    owner_sector_id: int
    items: list[ArpItemDTO]


@dataclass(frozen=True)
class ArpItemDTO:
    item_code: str
    description: str
    total_quantity_approved: Decimal
    unit_price: Decimal
    quotas: list[UnitQuotaDTO]


@dataclass(frozen=True)
class AddArpItemCommand:
    arp_id: UUID  # Identificador da Ata que vai receber o item
    item_code: str
    description: str
    total_quantity_approved: Decimal
    unit_price: Decimal
    initial_quotas: list[UnitQuotaDTO]
    sector_id: int


@dataclass(frozen=True)
class UnitQuotaDTO:
    unit_id: int
    total_allocated: Decimal
    

@dataclass(frozen=True)
class AddUnitQuotaCommand:
    arp_id: UUID       # ID da Ata de Registro de Preços
    item_code: str     # Código do item (ex: MED-4412)
    unit_id: int       # ID da unidade gestora que terá a cota
    total: Decimal     # Nova quantidade total alocada estipulada pelo gestor
    sector_id: int


@dataclass(frozen=True)
class AdjustUnitQuotaCommand:
    arp_id: UUID       # ID da Ata de Registro de Preços
    item_code: str     # Código do item (ex: MED-4412)
    unit_id: int       # ID da unidade gestora que terá a cota ajustada
    new_total: Decimal # Nova quantidade total alocada estipulada pelo gestor
    sector_id: int


@dataclass(frozen=True)
class RequestSupplyCommand:
    """Carrega estritamente os dados necessários para executar a intenção de débito."""
    arp_number: str
    item_code: str
    quantity: Decimal
    unit_id: int
    process_sei_request: str
    sector_id: int
