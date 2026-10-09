from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.queries.dtos import (
    GetArpQuery,
    GetArpResponseDTO
)
from app.shared.domain.exceptions import EntityNotFoundException

class GetArpQueryHandler:
    def __init__(self, query_service: QueryService):
        self._query_service = query_service

    def handle(
            self,
            query: GetArpQuery,
            sector_id: int
        ) -> GetArpResponseDTO:
        result = self._query_service.execute_get_arp_by_id(query, sector_id)
        if not result:
            raise EntityNotFoundException(f"Ata com ID {query.arp_id} não localizada.")
        return result
