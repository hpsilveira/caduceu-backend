from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.queries.dtos import ListCatalogItemResponseDTO

class ListCatalogItemQueryHandler:
    def __init__(self, query_service: QueryService):
        self._query_service = query_service

    def handle(self, sector_id: int) -> ListCatalogItemResponseDTO:
        return self._query_service.execute_list_catalog_item(sector_id)
