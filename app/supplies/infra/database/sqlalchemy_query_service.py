from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from datetime import datetime, timezone
from typing import Optional

# Ports
from app.supplies.application.ports.database.query_service import QueryService

# DTOs Query Handler
from app.supplies.application.queries.dtos import (
    GetArpQuery,
    GetArpResponseDTO,
    ListCatalogItemDTO,
    ListCatalogItemResponseDTO,
    ArpItemDTO,
    UnitQuotaDTO,
    GetSupplyOrderHistoryQuery,
    GetSupplyOrderHistoryResponseDTO,
    GetSupplyOrderHistoryDTO,
    ListManagementUnitDTO,
    ListManagementUnitResponseDTO,
    SearchArpQuery,
    SearchArpDTO,
    SearchArpResponseDTO
)

# Models
from app.supplies.infra.database.models import (
    ArpModel,
    ArpItemModel,
    SupplyOrderModel,
    DimCatalogItemModel,
    DimManagementUnitModel
)

def _iso_utc(carimbo: datetime) -> str:
    """Devolve o instante com offset explícito, igual em SQLite e Postgres.

    O SQLite devolve `naive` (o tipo não guarda fuso) e o Postgres devolve `aware` com o fuso da
    sessão. Sem offset na string, o `Date.parse` do navegador trata a hora como **local** e o
    histórico sai deslocado conforme o banco. Como a escrita normaliza para UTC, `naive` aqui é UTC.
    """
    aware = carimbo.replace(tzinfo=timezone.utc) if carimbo.tzinfo is None else carimbo
    return aware.astimezone(timezone.utc).isoformat()


class SqlAlchemyQueryService(QueryService):
    """Adaptador de saída unificado focado em consultas e projeções ORM rápidas."""

    def __init__(self, db_session: Session):
        self._session = db_session

    def execute_get_arp_by_id(
            self,
            query: GetArpQuery,
            sector_id: int
        ) -> Optional[GetArpResponseDTO]:
        # Busca a raiz do agregado no banco
        arp_model = (
            self._session.query(ArpModel)
            .filter(ArpModel.id == query.arp_id)
            .filter(ArpModel.sector_id == sector_id)
            .first()
        )
        
        if not arp_model:
            return None

        # Monta a lista de itens usando os novos DTOs
        items_dto: list[ArpItemDTO] = []
        for item in arp_model.items:
            quotas_dto: list[UnitQuotaDTO] = []
            for q in item.quotas:
                unit_name = (
                    self._session.
                    execute(select(DimManagementUnitModel.name)
                                          .where(DimManagementUnitModel.id == q.unit_id))
                                          .scalar() 
                                          or "Unidade Não Localizada"
                )
                quotas_dto.append(
                    UnitQuotaDTO(
                        unit_id=q.unit_id,
                        unit_name=unit_name,
                        total_allocated=q.total_allocated,
                        consumed=q.consumed
                    )
                )

            items_dto.append(
                ArpItemDTO(
                    id=item.id,
                    item_code=item.item_code,
                    description=item.description,
                    total_quantity_approved=item.total_quantity_approved,
                    quantity_consumed=item.quantity_consumed,
                    unit_price=item.unit_price,
                    quotas=quotas_dto
                )
            )

        # Retorna o DTO Raiz
        return GetArpResponseDTO(
            id=arp_model.id,
            arp_number=arp_model.arp_number,
            process_sei=arp_model.process_sei,
            expiration_date=arp_model.expiration_date.isoformat(),
            items=items_dto,
            is_active=bool(arp_model.is_active)
        )

    def execute_get_supply_order_history(
        self,
        query: GetSupplyOrderHistoryQuery,
        sector_id: int
    ) -> GetSupplyOrderHistoryResponseDTO:
        stmt = (
            select(
                # CORREÇÃO 1: Adiciona o alias "order_id" para bater com o row.order_id
                SupplyOrderModel.id.label("order_id"), 
                SupplyOrderModel.process_sei_request,
                SupplyOrderModel.item_code,
                # CORREÇÃO 2: Adiciona o unit_id ao SELECT, pois o DTO exige ele
                SupplyOrderModel.unit_id, 
                ArpItemModel.description.label("item_description"),
                DimManagementUnitModel.name.label("unit_name"),
                SupplyOrderModel.quantity_requested,
                SupplyOrderModel.created_at
            )
            .join(ArpModel,
                SupplyOrderModel.arp_id == ArpModel.id)
            .join(ArpItemModel,
                (SupplyOrderModel.item_code
                == ArpItemModel.item_code)
                & (SupplyOrderModel.arp_id
                == ArpItemModel.arp_id))
            .join(DimManagementUnitModel, SupplyOrderModel.unit_id == DimManagementUnitModel.id)
        )
        
        # CORREÇÃO CRÍTICA 3: O filtro deve ser pelo arp_id da ordem, não pelo id da ordem!
        stmt = stmt.where(SupplyOrderModel.arp_id == query.arp_id)
        stmt = stmt.where(ArpModel.sector_id == sector_id)
        
        if query.unit_id:
            stmt = stmt.where(SupplyOrderModel.unit_id == query.unit_id)
            
        # Contagem total para a paginação
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = self._session.execute(count_stmt).scalar() or 0
        
        # Paginação e Ordenação
        offset = (query.page - 1) * query.per_page
        stmt = stmt.order_by(SupplyOrderModel.created_at.desc()).limit(query.per_page).offset(offset)
        
        results = self._session.execute(stmt).fetchall()
        
        # Agora o mapeamento funciona perfeitamente pois os aliases e campos existem
        view_items = [
            GetSupplyOrderHistoryDTO(
                id=row.order_id,
                process_sei_request=row.process_sei_request,
                item_code=row.item_code,
                item_description=row.item_description,
                unit_id=row.unit_id,
                unit_name=row.unit_name,
                quantity_requested=row.quantity_requested,
                created_at=_iso_utc(row.created_at)
            ) for row in results
        ]
        
        return GetSupplyOrderHistoryResponseDTO(
            items=view_items,
            total_count=total_count,
            page=query.page,
            per_page=query.per_page
        )

    # Busca de Atas por número ou processo SEI
    def execute_search_arp(
            self,
            query: SearchArpQuery,
            sector_id: int
        ) -> SearchArpResponseDTO:
        stmt = (select(ArpModel)
                .where(ArpModel
                       .sector_id == sector_id)
        )
    
        if query.search_term:
            # Busca parcial no número da ata OU no processo SEI
            stmt = stmt.where(
                or_(
                    ArpModel.arp_number.ilike(f"%{query.search_term}%"),
                    ArpModel.process_sei.ilike(f"%{query.search_term}%")
                )
            )
    
        # Contagem total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = self._session.execute(count_stmt).scalar() or 0
    
        # Paginação e Ordenação (Mais recentes primeiro)
        offset = (query.page - 1) * query.per_page
        stmt = stmt.order_by(ArpModel.expiration_date.desc()).limit(query.per_page).offset(offset)
    
        results = self._session.execute(stmt).scalars().unique().all()
    
        items = [
            SearchArpDTO(
                id=arp.id,
                arp_number=arp.arp_number,
                process_sei=arp.process_sei,
                expiration_date=arp.expiration_date.isoformat(),
                is_active=bool(arp.is_active)
            ) for arp in results
        ]
    
        return SearchArpResponseDTO(items=items, total_count=total_count)

    def execute_list_catalog_item(
            self,
            sector_id: int
        ) -> ListCatalogItemResponseDTO:
        stmt = (
            select(DimCatalogItemModel.code, DimCatalogItemModel.description)
            .where(DimCatalogItemModel.sector_id == sector_id)
            .order_by(DimCatalogItemModel
            .description.asc())
        )
        results = self._session.execute(stmt).fetchall()
        
        return ListCatalogItemResponseDTO(items=[
            ListCatalogItemDTO(
                code=row.code,
                description=row.description,
                label=f"{row.code} - {row.description}")
            for row in results
        ])

    def execute_list_management_unit(self) -> ListManagementUnitResponseDTO:
        stmt = (
            select(DimManagementUnitModel.id, DimManagementUnitModel.name)
            .order_by(DimManagementUnitModel
            .name.asc())
        )
        results = self._session.execute(stmt).fetchall()
        
        return ListManagementUnitResponseDTO(items=[
                ListManagementUnitDTO(id=row.id, label=row.name)
            for row in results
        ])
