from fastapi import Depends
from sqlalchemy.orm import Session

# Ports
from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.application.ports.database.arp_repository import ArpRepository

# Adapters
from app.supplies.infra.database.sqlalchemy_query_service import (
    SqlAlchemyQueryService
)
from app.supplies.infra.database.sqlalchemy_arp_repository import (
    SqlAlchemyArpRepository
)

# Query Handlers
from app.supplies.application.queries.get_arp_handler import (
    GetArpQueryHandler
)
from app.supplies.application.queries.get_supply_order_history_handler import (
    GetSupplyOrderHistoryQueryHandler
)
from app.supplies.application.queries.list_catalog_item_handler import (
    ListCatalogItemQueryHandler
)
from app.supplies.application.queries.list_management_unit_handler import (
    ListManagementUnitQueryHandler
)
from app.supplies.application.queries.search_arp_handler import (
    SearchArpQueryHandler
)

# Command Handlers
from app.supplies.application.commands.create_arp_handler import (
    CreateArpCommandHandler
)
from app.supplies.application.commands.request_supply_handler import (
    RequestSupplyCommandHandler
)
from app.supplies.application.commands.add_arp_item_handler import (
    AddArpItemCommandHandler
)
from app.supplies.application.commands.add_unit_quota_handler import (
    AddUnitQuotaCommandHandler
)
from app.supplies.application.commands.adjust_unit_quota_handler import (
    AdjustUnitQuotaCommandHandler
)

# DB Session
from app.supplies.infra.database.config import get_db_session

# =========================================================================
# INJEÇÕES PARA O FLUXO DE ESCRITA (COMMANDS)
# =========================================================================
def get_arp_repository(
        db: Session = Depends(get_db_session)
    ) -> ArpRepository:
    """Injeta a sessão do SQLAlchemy na porta de escrita do repositório."""
    return SqlAlchemyArpRepository(db_session=db)


def get_create_arp_handler(
        repo: ArpRepository = Depends(get_arp_repository)
    ) -> CreateArpCommandHandler:
    return CreateArpCommandHandler(repository=repo)


def get_add_arp_item_handler(
        repo: ArpRepository = Depends(get_arp_repository)
    ) -> AddArpItemCommandHandler:
    return AddArpItemCommandHandler(repository=repo)


def get_add_unit_quota_handler(
        repo: ArpRepository = Depends(get_arp_repository)
    ) -> AddUnitQuotaCommandHandler:
    return AddUnitQuotaCommandHandler(repository=repo)


def get_adjust_unit_quota_handler(
        repo: ArpRepository = Depends(get_arp_repository)
    ) -> AdjustUnitQuotaCommandHandler:
    return AdjustUnitQuotaCommandHandler(repository=repo)


def get_request_supply_handler(
        repo: ArpRepository = Depends(get_arp_repository)
    ) -> RequestSupplyCommandHandler:
    """Monta o Handler de aplicação injetando seu respectivo repositório."""
    return RequestSupplyCommandHandler(repository=repo)


# =========================================================================
# INJEÇÕES PARA O FLUXO DE LEITURA (QUERIES)
# =========================================================================
def get_query_service(db: Session = Depends(get_db_session)) -> QueryService:
    """Injeta a sessão do banco no adaptador unificado de leitura."""
    return SqlAlchemyQueryService(db_session=db)


def get_arp_handler(
        service: QueryService = Depends(get_query_service)
    ) -> GetArpQueryHandler:
    return GetArpQueryHandler(query_service=service)


def get_supply_order_history_handler(
        service: QueryService = Depends(get_query_service)
    ) -> GetSupplyOrderHistoryQueryHandler:
    return GetSupplyOrderHistoryQueryHandler(query_service=service)


def get_search_arp_handler(
        service: QueryService = Depends(get_query_service)
    ) -> SearchArpQueryHandler:
    return SearchArpQueryHandler(query_service=service)


def get_list_catalog_item_handler(
        service: QueryService = Depends(get_query_service)
        ) -> ListCatalogItemQueryHandler:
    return ListCatalogItemQueryHandler(query_service=service)


def get_list_management_unit_handler(
        service: QueryService = Depends(get_query_service)
        ) -> ListManagementUnitQueryHandler:
    return ListManagementUnitQueryHandler(query_service=service)
