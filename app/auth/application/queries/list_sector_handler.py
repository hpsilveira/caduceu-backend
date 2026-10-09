from app.auth.application.queries.dtos import SectorDTO
from app.auth.application.ports.query_service import QueryService
from app.auth.domain.entities.user import User

class ListSectorQueryHandler:
    def __init__(self, query_service: QueryService):
        self._query_service = query_service

    def handle(self, user: User) -> list[SectorDTO]:
        all_sectors = self._query_service.execute_list_sector()

        if user.sector_code == "GLOBAL_ADMIN":
            return all_sectors

        return [s for s in all_sectors if s.code == user.sector_code]