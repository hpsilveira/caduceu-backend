"""Fake do port de leitura `QueryService`.

`QueryService` é uma ABC com cinco `@abstractmethod`, então esta classe só é
instanciável se implementar **todas** — adicionar um método ao port quebra os testes
na coleta, não em produção. É o contrato do lado de leitura a serviço do isolamento
por setor: os argumentos são registrados porque o que importa em vários testes é
provar que o `sector_id` do usuário chegou ao adaptador.
"""
from typing import Any

from app.supplies.application.ports.database.query_service import QueryService
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


class FakeQueryService(QueryService):
    """Respostas pré-configuradas + registro das chamadas recebidas.

    Cada resultado nasce **vazio e válido**, nunca ausente: o port declara estes quatro retornos
    como não-`None`, então um default `| None` faria o fake mentir sobre o contrato. `get_arp_result`
    é a exceção honesta — ali o próprio port declara `GetArpResponseDTO | None` (a ata pode não
    existir), e é esse `None` que o teste de inexistência lê.
    """

    def __init__(self) -> None:
        self.get_arp_result: GetArpResponseDTO | None = None
        self.history_result = GetSupplyOrderHistoryResponseDTO(
            items=[], total_count=0, page=1, per_page=10
        )
        self.search_result = SearchArpResponseDTO(items=[], total_count=0)
        self.catalog_result = ListCatalogItemResponseDTO(items=[])
        self.units_result = ListManagementUnitResponseDTO(items=[])
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def execute_get_arp_by_id(
            self,
            query: GetArpQuery,
            sector_id: int
        ) -> GetArpResponseDTO | None:
        self._record("execute_get_arp_by_id", query, sector_id)
        return self.get_arp_result

    def execute_get_supply_order_history(
            self,
            query: GetSupplyOrderHistoryQuery,
            sector_id: int
        ) -> GetSupplyOrderHistoryResponseDTO:
        self._record("execute_get_supply_order_history", query, sector_id)
        return self.history_result

    def execute_search_arp(
            self,
            query: SearchArpQuery,
            sector_id: int
        ) -> SearchArpResponseDTO:
        self._record("execute_search_arp", query, sector_id)
        return self.search_result

    def execute_list_catalog_item(
            self,
            sector_id: int
        ) -> ListCatalogItemResponseDTO:
        self._record("execute_list_catalog_item", sector_id)
        return self.catalog_result

    def execute_list_management_unit(self) -> ListManagementUnitResponseDTO:
        self._record("execute_list_management_unit")
        return self.units_result
