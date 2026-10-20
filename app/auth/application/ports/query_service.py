from abc import ABC, abstractmethod
from app.auth.application.queries.dtos import SectorDTO

class QueryService(ABC):
    """Centralized Reading Port (Driven Port) for the auth module."""

    @abstractmethod
    def execute_list_sector(self) -> list[SectorDTO]:
        """Retorna uma lista de DTOs de setores ativos."""
        pass