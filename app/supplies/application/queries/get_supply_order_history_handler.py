from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.queries.dtos import (
    GetSupplyOrderHistoryQuery,
    GetSupplyOrderHistoryResponseDTO
)

class GetSupplyOrderHistoryQueryHandler:
    def __init__(self, query_service: QueryService):
        self._query_service = query_service

    def handle(
            self,
            query: GetSupplyOrderHistoryQuery,
            sector_id: int
        ) -> GetSupplyOrderHistoryResponseDTO:
        return self._query_service.execute_get_supply_order_history(query, sector_id)
