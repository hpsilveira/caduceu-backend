from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.queries.dtos import ListManagementUnitResponseDTO

# =========================================================================
# THE QUERY PORT & HANDLER
# =========================================================================
class ListManagementUnitQueryHandler:
    def __init__(self, query_service: QueryService):
        self._query_service = query_service

    def handle(self) -> ListManagementUnitResponseDTO:
        return self._query_service.execute_list_management_unit()
