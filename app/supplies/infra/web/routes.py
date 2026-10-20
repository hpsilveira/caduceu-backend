from fastapi import APIRouter, Depends, status, Query
from typing import Optional
from uuid import UUID

# Command Handlers
from app.supplies.application.commands.request_supply_handler import (
    RequestSupplyCommandHandler
)
from app.supplies.application.commands.create_arp_handler import (
    CreateArpCommandHandler
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

# Query Handlers
from app.supplies.application.queries.search_arp_handler import (
    SearchArpQueryHandler
)
from app.supplies.application.queries.get_arp_handler import (
    GetArpQueryHandler
)
from app.supplies.application.queries.list_management_unit_handler import (
    ListManagementUnitQueryHandler,
)
from app.supplies.application.queries.list_catalog_item_handler import (
    ListCatalogItemQueryHandler
)
from app.supplies.application.queries.get_supply_order_history_handler import (
    GetSupplyOrderHistoryQueryHandler
)

# DTOs
from app.supplies.application.commands.dtos import (
    CreateArpCommand,
    AddArpItemCommand,
    AddUnitQuotaCommand,
    AdjustUnitQuotaCommand,
    RequestSupplyCommand,
    UnitQuotaDTO,
    ArpItemDTO
)
from app.supplies.application.queries.dtos import (
    GetArpQuery,
    GetArpResponseDTO,
    GetSupplyOrderHistoryQuery,
    GetSupplyOrderHistoryResponseDTO,
    ListCatalogItemResponseDTO,
    ListManagementUnitResponseDTO,
    SearchArpQuery,
    SearchArpResponseDTO
)

# Schemas
from app.supplies.infra.web.schemas import (
    CreateArpRequestSchema,
    AddArpItemRequestSchema,
    AddUnitQuotaRequestSchema,
    AdjustUnitQuotaRequestSchema,
    RequestSupplyRequestSchema,
    CreateResponseSchema
)

# Dependencies Injections
from app.supplies.dependencies import (
    get_create_arp_handler,
    get_add_arp_item_handler,
    get_add_unit_quota_handler,
    get_adjust_unit_quota_handler,
    get_request_supply_handler,
    get_arp_handler,
    get_supply_order_history_handler,
    get_list_catalog_item_handler,
    get_list_management_unit_handler,
    get_search_arp_handler
)

# Auth Module
from app.auth.dependencies import get_current_user, get_current_writer
from app.auth.domain.entities.user import User

# =========================================================================
# EXCEÇÕES DE DOMÍNIO PARA MAPEAMENTO HTTP
# =========================================================================

router = APIRouter(prefix="/api/v1/supplies", tags=["Suprimentos e Atas (COADI)"])

# =========================================================================
# COMMAND ROUTERS
# =========================================================================
@router.post("/arps", status_code=status.HTTP_201_CREATED)
def create_arp(
        payload: CreateArpRequestSchema,
        handler: CreateArpCommandHandler = Depends(get_create_arp_handler),
        current_user: User = Depends(get_current_writer)
    ) -> CreateResponseSchema:
    """Cadastra uma nova Ata de Registro de Preços completa via Script/Lote."""
    command = CreateArpCommand(
        arp_number=payload.arp_number,
        process_sei=payload.process_sei,
        expiration_date=payload.expiration_date,
        sector_id=current_user.sector_id,
        items=[
            ArpItemDTO(
                item_code=i.item_code,
                description=i.description,
                total_quantity_approved=i.total_quantity_approved,
                unit_price=i.unit_price,
                quotas=[UnitQuotaDTO(**q.model_dump()) for q in i.quotas]
            ) for i in payload.items
        ]
    )
    arp_id = handler.handle(command)
    return CreateResponseSchema(id=arp_id, message="Ata cadastrada com sucesso.")


@router.post("/arps/{arp_id}/items", status_code=status.HTTP_201_CREATED)
def add_arp_item(
        arp_id: UUID,
        payload: AddArpItemRequestSchema,
        handler: AddArpItemCommandHandler = Depends(get_add_arp_item_handler),
        current_user: User = Depends(get_current_writer)
    ) -> CreateResponseSchema:
    """Ação granular do dia a dia: Adiciona um novo item homologado a uma Ata ativa."""
    command = AddArpItemCommand(
        arp_id=arp_id,
        item_code=payload.item_code,
        description=payload.description,
        total_quantity_approved=payload.total_quantity_approved,
        unit_price=payload.unit_price,
        initial_quotas=[UnitQuotaDTO(**q.model_dump())
                        for q in payload.quotas],
        sector_id=current_user.sector_id
    )
    item_id = handler.handle(command)
    return CreateResponseSchema(id=item_id, message="Item adicionado com sucesso.")


@router.post(
    "/arps/{arp_id}/items/{item_code}/quotas",
    status_code=status.HTTP_201_CREATED
)
def add_quota_unit(
        arp_id: UUID,
        item_code: str,
        payload: AddUnitQuotaRequestSchema,
        handler: AddUnitQuotaCommandHandler = Depends(get_add_unit_quota_handler),
        current_user: User = Depends(get_current_writer)
    ) -> CreateResponseSchema:
    """Ação granular do dia a dia: Ajusta o teto físico da cota de uma unidade gestora."""
    command = AddUnitQuotaCommand(
        arp_id=arp_id,
        item_code=item_code,
        unit_id=payload.unit_id,
        total=payload.total_allocated,
        sector_id=current_user.sector_id
    )
    quota_id = handler.handle(command)
    return CreateResponseSchema(id=quota_id, message="Cota adicionado com sucesso.")


@router.patch(
    "/arps/{arp_id}/items/{item_code}/quotas/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def adjust_quota_unit(
        arp_id: UUID,
        item_code: str,
        unit_id: int,
        payload: AdjustUnitQuotaRequestSchema,
        handler: AdjustUnitQuotaCommandHandler = Depends(get_adjust_unit_quota_handler),
        current_user: User = Depends(get_current_writer)
    ) -> None:
    """Ação granular do dia a dia: Ajusta o teto físico da cota de uma unidade gestora."""
    command = AdjustUnitQuotaCommand(
        arp_id=arp_id,
        item_code=item_code,
        unit_id=unit_id,
        new_total=payload.new_total,
        sector_id=current_user.sector_id
    )
    handler.handle(command)
    return


@router.post("/request-supply", status_code=status.HTTP_201_CREATED)
def request_supply(
        payload: RequestSupplyRequestSchema,
        handler: RequestSupplyCommandHandler = Depends(get_request_supply_handler),
        current_user: User = Depends(get_current_writer)
    ) -> CreateResponseSchema:
    """Executa a intenção de debitar saldo de um item e cota da unidade gestora."""
    command = RequestSupplyCommand(
        sector_id=current_user.sector_id,
        **payload.model_dump()
    )
    order_id = handler.handle(command)
    return CreateResponseSchema(id=order_id, message="Débito executado com sucesso.")


# =========================================================================
# QUERY ROUTERS
# =========================================================================
@router.get("/arps/{arp_id}", response_model=GetArpResponseDTO)
def get_arp(
        arp_id: UUID,
        handler: GetArpQueryHandler = Depends(get_arp_handler),
        current_user: User = Depends(get_current_user)
    ):
    """
    O FastAPI agora valida se o retorno do handler 
    segue exatamente a estrutura do ArpDetailsReadDTO.
    """
    query = GetArpQuery(
        arp_id=arp_id,
    )
    return handler.handle(query, current_user.sector_id)


@router.get("/arps/{arp_id}/order-history", status_code=status.HTTP_200_OK)
def get_supply_order_history(
        arp_id: UUID,
        unit_id: Optional[int] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=100),
        handler: GetSupplyOrderHistoryQueryHandler = Depends(get_supply_order_history_handler),
        current_user: User = Depends(get_current_user)
    ) -> GetSupplyOrderHistoryResponseDTO:
    """Retorna o histórico de ordens paginado e mastigado para o TanStack Query."""
    query = GetSupplyOrderHistoryQuery(
        arp_id=arp_id,
        unit_id=unit_id,
        page=page,
        per_page=per_page
    )
    return handler.handle(query, current_user.sector_id)


@router.get("/lookups/items")
def list_catalog_item(
        handler: ListCatalogItemQueryHandler = Depends(get_list_catalog_item_handler),
        current_user: User = Depends(get_current_user)
    ) -> ListCatalogItemResponseDTO:
    """Retorna o catálogo de itens para alimentar Selects no React."""
    return handler.handle(current_user.sector_id)


@router.get("/lookups/units")
def list_management_unit(
        handler: ListManagementUnitQueryHandler = Depends(get_list_management_unit_handler),
        current_user: User = Depends(get_current_user)
    ) -> ListManagementUnitResponseDTO:
    """Retorna a lista de unidades gestoras para Selects."""
    return handler.handle()


@router.get("/arps", response_model=SearchArpResponseDTO)
def search_arp(
        query: Optional[str] = Query(None, alias="query"),
        handler: SearchArpQueryHandler = Depends(get_search_arp_handler),
        current_user: User = Depends(get_current_user)
    ):
    """Endpoint de busca para a barra lateral do Master-Detail."""
    search_query = SearchArpQuery(
        search_term=query,
    )
    return handler.handle(search_query, current_user.sector_id)
