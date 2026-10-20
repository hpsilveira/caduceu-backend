from abc import ABC, abstractmethod
from typing import Optional
from app.supplies.application.queries.dtos import (
    GetArpQuery,
    GetArpResponseDTO,
    GetSupplyOrderHistoryQuery,
    GetSupplyOrderHistoryResponseDTO,
    ListCatalogItemResponseDTO,
    ListManagementUnitResponseDTO,
    SearchArpQuery,
    SearchArpResponseDTO,
)

class QueryService(ABC):
    """Centralized Reading Port (Driven Port) for the supply module."""
    @abstractmethod
    def execute_get_arp_by_id(
            self,
            query: GetArpQuery,
            sector_id: int
        ) -> Optional[GetArpResponseDTO]:
        """Busca os detalhes completos de uma Ata para visualização."""
        pass


    @abstractmethod
    def execute_get_supply_order_history(
            self,
            query: GetSupplyOrderHistoryQuery,
            sector_id: int
        ) -> GetSupplyOrderHistoryResponseDTO:
        """Busca o histórico paginado e filtrado de ordens de fornecimento."""
        pass

    @abstractmethod
    def execute_search_arp(
            self,
            query: SearchArpQuery,
            sector_id: int
        ) -> SearchArpResponseDTO:
        """Realiza busca filtrada por número da ata ou processo SEI."""
        pass

    @abstractmethod
    def execute_list_catalog_item(
            self,
            sector_id: int
        ) -> ListCatalogItemResponseDTO:
        """It retrieves the list of active items in the sector to populate Select."""
        pass

    @abstractmethod
    def execute_list_management_unit(self) -> ListManagementUnitResponseDTO:
        """Busca a lista de unidades gestoras da SESAP para o Select."""
        pass
