from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.queries.dtos import (
    SearchArpQuery,
    SearchArpResponseDTO
)

class SearchArpQueryHandler:
    def __init__(self, query_service: QueryService):
        self._query_service = query_service

    def handle(
            self,
            query: SearchArpQuery,
            sector_id: int
        ) -> SearchArpResponseDTO:
        return self._query_service.execute_search_arp(query, sector_id)
