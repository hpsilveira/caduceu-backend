from sqlalchemy.orm import Session
from sqlalchemy import select
from app.auth.application.ports.query_service import QueryService
from app.auth.application.queries.dtos import SectorDTO
from app.supplies.infra.database.models import DimSectorModel

class SqlAlchemyQueryService(QueryService):
    """Adaptador de saída unificado focado em consultas e projeções ORM rápidas."""

    def __init__(self, db_session: Session):
        self._session = db_session

    def execute_list_sector(self) -> list[SectorDTO]:
        """Retorna uma lista de DTOs de setores ativos."""
        stmt = (
            select(DimSectorModel.code, DimSectorModel.name)
            .where(DimSectorModel.is_active == True)
        )
        results = self._session.execute(stmt).fetchall()
        return [SectorDTO(code=row.code, name=row.name) for row in results]