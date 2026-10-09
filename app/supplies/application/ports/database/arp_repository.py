from uuid import UUID
from app.supplies.domain.entities.price_registration_agreement import (
    PriceRegistrationAgreement
)
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.supplies.domain.entities.supply_order import SupplyOrder

# =========================================================================
# THE APPLICATION PORT (Driven Port / Repository Interface)
# =========================================================================

class ArpRepository:
    """Write-side focused on Aggregate persistence and consistency."""
    
    def find_by_arp_number(
            self,
            arp_number: str
        ) -> PriceRegistrationAgreement | None:
        """Retrieves the complete ARP aggregate for modification."""
        raise NotImplementedError

    def find_arp_by_id(self, arp_id: UUID) -> PriceRegistrationAgreement | None:
        """Retrieves the complete ARP aggregate for modification."""
        raise NotImplementedError

    def save_supply_order(
            self,
            arp: PriceRegistrationAgreement,
            order: SupplyOrder
        ) -> None:
        """
        Atomically saves the state of the modified Record and the newly issued Order. 
        Ideally wrapped in a database transaction (Unit of Work).
        """
        raise NotImplementedError

    def save_new_arp(self, arp: PriceRegistrationAgreement) -> None:
        """
        Saves new ARP.
        Ideally wrapped in a database transaction (Unit of Work).
        """
        raise NotImplementedError

    def save_item_addition(
            self,
            arp_id: UUID,
            item: ArpItem
        ) -> None:
        """Insere cirurgicamente apenas o novo item e suas cotas associadas no banco."""
        raise NotImplementedError

    def save_quota(self, item_id: UUID, quota: UnitQuota) -> None:
        """Saves a Quota to the database."""
        raise NotImplementedError

    def save_quota_adjustment(self, quota: UnitQuota) -> None:
        """Saves only the modified Quota to the database."""
        raise NotImplementedError

    def exists_in_catalog(self, item_code: str, sector_id: int) -> bool:
        """Verifies whether the item actually exists in the approved catalog."""
        raise NotImplementedError

    def exists_management_unit(self, unit_id: int) -> bool:
        """Checks if the drive actually exists."""
        raise NotImplementedError
