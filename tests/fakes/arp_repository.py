"""Fake do port de escrita `ArpRepository`.

Sem banco, sem transação: o objetivo é observar **o que o handler fez com o agregado**
e **o que ele pediu para persistir**. Os `save_*` apenas registram a chamada — eles não
re-validam regra de negócio (isso é papel do domínio) e não replicam a escrita, porque o
fake guarda a **mesma instância** que o handler muta in-place. Consequência prática: depois
de um `adjust_quota_allocation`, o objeto em `saved_quota_adjustments` já é o objeto mutado,
então o pré-estado não é recuperável. Enquanto nenhum teste precisar de snapshot do estado
anterior, isso é suficiente para "salvou? / salvou o quê? / salvou quantas vezes?".
"""
from uuid import UUID

from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.supplies.domain.entities.arp import Arp
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.supply_order import SupplyOrder
from app.supplies.domain.entities.unit_quota import UnitQuota


class FakeArpRepository(ArpRepository):
    """Implementação em memória da porta de escrita, com recording por método."""

    def __init__(self) -> None:
        # --- estado ---
        self.arps_by_id: dict[UUID, Arp] = {}
        self.arps_by_number: dict[str, Arp] = {}
        # O catálogo é setorial: o mesmo código pode existir em outro setor e não aqui.
        self.catalog_codes: set[tuple[str, int]] = set()
        self.management_unit_ids: set[int] = set()

        # --- recording (o que foi pedido ao banco) ---
        self.saved_arps: list[Arp] = []
        self.saved_orders: list[SupplyOrder] = []
        self.saved_items: list[tuple[UUID, ArpItem]] = []
        self.saved_quotas: list[tuple[UUID, UnitQuota]] = []
        self.saved_quota_adjustments: list[UnitQuota] = []

    # --- helpers de setup -------------------------------------------------
    def seed_arp(self, arp: Arp, *, in_catalog: bool = True, units_exist: bool = True) -> "FakeArpRepository":
        """Registra a ata e, por padrão, o cenário que a torna operável.

        `in_catalog` publica os códigos dos itens no setor da ata; `units_exist`
        publica as unidades das cotas. Desligue um dos dois para exercitar os
        `EntityNotFoundException` de pré-condição do handler sem tocar no agregado.
        """
        self.arps_by_id[arp.id] = arp
        self.arps_by_number[arp.arp_number] = arp
        if in_catalog:
            for item in arp.items:
                self.add_catalog_item(item.item_code, sector_id=arp.sector_id)
        if units_exist:
            for item in arp.items:
                for quota in item.quota_units:
                    self.add_management_unit(quota.unit_id)
        return self

    def add_catalog_item(self, item_code: str, sector_id: int) -> None:
        self.catalog_codes.add((item_code, sector_id))

    def add_management_unit(self, unit_id: int) -> None:
        self.management_unit_ids.add(unit_id)

    # --- leituras ---------------------------------------------------------
    def find_by_arp_number(self, arp_number: str) -> Arp | None:
        return self.arps_by_number.get(arp_number)

    def exists_arp_number(self, arp_number: str) -> bool:
        return arp_number in self.arps_by_number

    def find_arp_by_id(self, arp_id: UUID) -> Arp | None:
        return self.arps_by_id.get(arp_id)

    def exists_in_catalog(self, item_code: str, sector_id: int) -> bool:
        return (item_code, sector_id) in self.catalog_codes

    def exists_management_unit(self, unit_id: int) -> bool:
        return unit_id in self.management_unit_ids

    # --- escrituras -------------------------------------------------------
    def save_new_arp(self, arp: Arp) -> None:
        # Indexa além de registrar: depois de salvar, a ata passou a existir no banco,
        # e um handler de teste pode querer reenvolvê-la em outra operação.
        self.arps_by_id[arp.id] = arp
        self.arps_by_number[arp.arp_number] = arp
        self.saved_arps.append(arp)

    def save_supply_order(self, arp: Arp, order: SupplyOrder) -> None:
        self.saved_orders.append(order)

    def save_item_addition(self, arp_id: UUID, item: ArpItem) -> None:
        self.saved_items.append((arp_id, item))

    def save_quota(self, item_id: UUID, quota: UnitQuota) -> None:
        self.saved_quotas.append((item_id, quota))

    def save_quota_adjustment(self, quota: UnitQuota) -> None:
        self.saved_quota_adjustments.append(quota)
