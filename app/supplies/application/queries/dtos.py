from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from uuid import UUID

# DTOs: ARP Details
@dataclass(frozen=True)
class GetArpQuery:
    """Query to retrieve details of a specific ARP by ID."""
    arp_id: UUID


@dataclass(frozen=True)
class GetArpResponseDTO:
    id: UUID
    arp_number: str
    process_sei: str
    expiration_date: str
    items: list[ArpItemDTO]
    is_active: bool

# DTOs: Item Details
@dataclass(frozen=True)
class ArpItemDTO:
    id: UUID
    item_code: str
    description: str
    total_quantity_approved: Decimal
    quantity_consumed: Decimal
    unit_price: Decimal
    quotas: list[UnitQuotaDTO]


# DTOs: Quota Details
@dataclass(frozen=True)
class UnitQuotaDTO:
    unit_id: int
    unit_name: str
    total_allocated: Decimal
    consumed: Decimal


# DTOs: Supply Order History
@dataclass(frozen=True)
class GetSupplyOrderHistoryQuery:
    arp_id: UUID
    unit_id: Optional[int] = None
    page: int = 1
    per_page: int = 10


@dataclass(frozen=True)
class GetSupplyOrderHistoryDTO:
    id: UUID
    item_code: str
    item_description: str
    unit_id: int
    unit_name: str
    quantity_requested: Decimal
    process_sei_request: str
    created_at: str


@dataclass(frozen=True)
class GetSupplyOrderHistoryResponseDTO:
    items: list[GetSupplyOrderHistoryDTO]
    total_count: int
    page: int
    per_page: int


# DTOs: ARP Search
@dataclass(frozen=True)
class SearchArpQuery:
    search_term: Optional[str] = None
    page: int = 1
    per_page: int = 50


@dataclass(frozen=True)
class SearchArpDTO:
    id: UUID
    arp_number: str
    process_sei: str
    expiration_date: str
    is_active: bool


@dataclass(frozen=True)
class SearchArpResponseDTO:
    items: list[SearchArpDTO]
    total_count: int


# DTOs: Catalog Item Dropdown
@dataclass(frozen=True)
class ListCatalogItemDTO:
    code: str
    description: str
    label: str


@dataclass(frozen=True)
class ListCatalogItemResponseDTO:
    items: list[ListCatalogItemDTO]


# DTOs: Management Unit Dropdown
@dataclass(frozen=True)
class ListManagementUnitDTO:
    id: int
    label: str


@dataclass(frozen=True)
class ListManagementUnitResponseDTO:
    items: list[ListManagementUnitDTO]
