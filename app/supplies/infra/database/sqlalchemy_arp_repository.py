from uuid import UUID
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session

# Port
from app.supplies.application.ports.database.arp_repository import ArpRepository

# Rich Domain
from app.supplies.domain.entities.price_registration_agreement import (
    PriceRegistrationAgreement
)
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.supplies.domain.entities.supply_order import SupplyOrder
from app.shared.domain.value_objects.shared_vo import Money
from app.shared.domain.exceptions import EntityNotFoundException

# Imports dos Modelos do SQLAlchemy (Suas tabelas puras de Infraestrutura)
from app.supplies.infra.database.models import (
    ArpItemModel,
    PriceRegistrationAgreementModel,
    UnitQuotaModel,
    SupplyOrderModel
)

class SqlAlchemyArpRepository(ArpRepository):
    """
    Concrete Output Adapter that implements the Write Port
    using the SQLAlchemy synchronous/asynchronous session.
    """

    def __init__(self, db_session: Session):
        self._session = db_session

    def find_arp_by_id(self, arp_id: UUID) -> PriceRegistrationAgreement | None:
        """Busca a Ata diretamente pelo seu ID único (UUID)."""
        arp_model = (
            self._session.query(PriceRegistrationAgreementModel)
            .filter(PriceRegistrationAgreementModel.id == arp_id)
            .first()
        )

        if not arp_model:
            return None
            
        # 2. Reconstitui as sub-entidades de Cotas e Itens de baixo para cima
        domain_items: list[ArpItem] = []
        for item_m in arp_model.items:
            
            # Reconstitui as cotas de cada item
            domain_quotas: list[UnitQuota] = [
                UnitQuota(
                    id=quota_m.id,
                    unit_id=quota_m.unit_id,
                    total_allocated=quota_m.total_allocated,
                    consumed=quota_m.consumed
                )
                for quota_m in item_m.quotas
            ]

            # Reconstitui o item injetando as cotas correspondentes
            domain_item = ArpItem(
                id=item_m.id,
                item_code=item_m.item_code,
                description=item_m.description,
                total_quantity_approved=item_m.total_quantity_approved,
                quantity_consumed=item_m.quantity_consumed,
                unit_price=Money(amount=Decimal(str(item_m.unit_price))),  # Mapeia float/Decimal para VO
                quota_units=domain_quotas
            )
            domain_items.append(domain_item)

        # 3. Retorna a raiz do agregado totalmente remontada a partir do construtor técnico
        return PriceRegistrationAgreement(
            id=arp_model.id,
            arp_number=arp_model.arp_number,
            process_sei=arp_model.process_sei,
            expiration_date=arp_model.expiration_date,
            owner_sector_id=arp_model.owner_sector_id,
            items=domain_items,
            is_active=arp_model.is_active
        )

    def find_by_arp_number(
            self,
            arp_number: str,
        ) -> PriceRegistrationAgreement | None:
        """
        Busca os dados relacionais do banco e reconstrói (reconstitui) 
        o Agregado completo com toda a integridade histórica de consumo.
        """
        # 1. Busca a Ata carregando os relacionamentos em cascata (eager loading)
        # para evitar o problema de N+1 consultas na memória
        arp_model = (
            self._session.query(PriceRegistrationAgreementModel)
            .filter(PriceRegistrationAgreementModel.arp_number == arp_number)
            .first()
        )
        
        if not arp_model:
            return None

        # 2. Reconstitui as sub-entidades de Cotas e Itens de baixo para cima
        domain_items: list[ArpItem] = []
        for item_m in arp_model.items:
            
            # Reconstitui as cotas de cada item
            domain_quotas: list[UnitQuota] = [
                UnitQuota(
                    id=quota_m.id,
                    unit_id=quota_m.unit_id,
                    total_allocated=quota_m.total_allocated,
                    consumed=quota_m.consumed
                )
                for quota_m in item_m.quotas
            ]

            # Reconstitui o item injetando as cotas correspondentes
            domain_item = ArpItem(
                id=item_m.id,
                item_code=item_m.item_code,
                description=item_m.description,
                total_quantity_approved=item_m.total_quantity_approved,
                quantity_consumed=item_m.quantity_consumed,
                unit_price=Money(amount=Decimal(str(item_m.unit_price))),  # Mapeia float/Decimal para VO
                quota_units=domain_quotas
            )
            domain_items.append(domain_item)

        # 3. Retorna a raiz do agregado totalmente remontada a partir do construtor técnico
        return PriceRegistrationAgreement(
            id=arp_model.id,
            arp_number=arp_model.arp_number,
            process_sei=arp_model.process_sei,
            expiration_date=arp_model.expiration_date,
            owner_sector_id=arp_model.owner_sector_id,
            items=domain_items,
            is_active=arp_model.is_active
        )

    def save_new_arp(self, arp: PriceRegistrationAgreement) -> None:
        try:
            arp_model = PriceRegistrationAgreementModel(
                id=arp.id,
                arp_number=arp.arp_number,
                process_sei=arp.process_sei,
                expiration_date=arp.expiration_date,
                owner_sector_id=arp.owner_sector_id,
                is_active=1 if arp.is_active else 0
            )
            
            # CORREÇÃO: Iterar sobre 'arp.items' (Domínio). 
            # 'arp_model.items' estaria vazio neste ponto.
            for item in arp.items: 
                item_model = ArpItemModel(
                    id=item.id,
                    arp_id=arp.id,
                    item_code=item.item_code,
                    description=item.description,
                    total_quantity_approved=item.total_quantity_approved,
                    quantity_consumed=item.quantity_consumed,
                    unit_price=float(item.unit_price.amount) # Correção para extrair do Value Object Money
                )
                
                for quota in item.quota_units:
                    quota_model = UnitQuotaModel(
                        id=quota.id,
                        unit_id=quota.unit_id,
                        total_allocated=quota.total_allocated,
                        consumed=quota.consumed
                    )
                    item_model.quotas.append(quota_model)
                    
                arp_model.items.append(item_model)
                
            self._session.add(arp_model)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def save_item_addition(
            self,
            arp_id: UUID,
            item: ArpItem
        ) -> None:
        """Insere cirurgicamente apenas o novo item e suas cotas associadas no banco."""
        try:
            item_model = ArpItemModel(
                id=item.id,
                arp_id=arp_id,
                item_code=item.item_code,
                description=item.description,
                total_quantity_approved=item.total_quantity_approved,
                quantity_consumed=item.quantity_consumed,
                unit_price=float(item.unit_price.amount)
            )

            for quota in item.quota_units:
                quota_model = UnitQuotaModel(
                    id=quota.id,
                    unit_id=quota.unit_id,
                    total_allocated=quota.total_allocated,
                    consumed=quota.consumed
                )
                item_model.quotas.append(quota_model)

            self._session.add(item_model)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def save_quota(self, item_id: UUID, quota: UnitQuota) -> None:
        """Atualiza cirurgicamente no banco apenas os valores da cota modificada."""
        try:
            item_model = (
                self._session.query(ArpItemModel)
                .filter(ArpItemModel.id == item_id)
                .first()
            )
            
            if not item_model:
                raise EntityNotFoundException("Registro físico do item não encontrado no banco de dados.")

            quota_model = UnitQuotaModel(
                id=quota.id,
                item_id=item_id,
                unit_id=quota.unit_id,
                total_allocated=quota.total_allocated,
                consumed=quota.consumed
            )

            item_model.quotas.append(quota_model)

            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def save_quota_adjustment(self, quota: UnitQuota) -> None:
        """Atualiza cirurgicamente no banco apenas os valores da cota modificada."""
        try:
            quota_model = (
                self._session.query(UnitQuotaModel)
                .filter(UnitQuotaModel.id == quota.id)
                .first()
            )
            
            if not quota_model:
                raise EntityNotFoundException("Registro físico da cota não encontrado no banco de dados.")

            # Atualiza o novo total alocado calculado e validado pelo domínio
            quota_model.total_allocated = quota.total_allocated
            
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def save_supply_order(
        self,
        arp: PriceRegistrationAgreement,
        order: SupplyOrder
    ) -> None:
        try:
            # --- 1. Atualizar o estado da Raiz da Ata no Banco ---
            arp_model = (
                self._session.query(PriceRegistrationAgreementModel)
                .filter(PriceRegistrationAgreementModel.id == arp.id)
                .first()
            )
            if not arp_model:
                return
            
            arp_model.is_active = arp.is_active

            # --- 2. Atualizar os Itens e as Cotas consumidas ---
            # CORREÇÃO: Iterar sobre 'arp.items' (Domínio) e não 'arp_model.items' (ORM)
            for domain_item in arp.items: 
                item_model = (
                    self._session.query(ArpItemModel)
                    .filter(ArpItemModel.id == domain_item.id)
                    .first()
                )
                if item_model:
                    # Agora lê o valor correto calculado pelo Domínio
                    item_model.quantity_consumed = domain_item.quantity_consumed 
                    
                    # CORREÇÃO: A entidade de domínio usa 'quota_units', não 'quotas'
                    for domain_quota in domain_item.quota_units: 
                        quota_model = (
                            self._session.query(UnitQuotaModel)
                            .filter(UnitQuotaModel.id == domain_quota.id)
                            .first()
                        )
                        if quota_model:
                            quota_model.consumed = domain_quota.consumed

            # --- 3. Inserir o novo evento histórico (SupplyOrder) ---
            new_order_model = SupplyOrderModel(
                id=order.id,
                arp_id=order.arp_id,
                item_code=order.item_code,
                unit_id=order.unit_id,
                quantity_requested=order.quantity_requested,
                process_sei_request=order.process_sei_request,
                created_at=order.created_at
            )
            self._session.add(new_order_model)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def exists_in_catalog(self, item_code: str, sector_id: int) -> bool:
        """Verifica se o item realmente existe no catálogo homologado."""
        # Uma consulta rápida no banco para saber se o código é válido
        result = self._session.execute(
            text("SELECT 1 FROM dim_catalog_item \
                WHERE item_code = :code AND catalog_id = :sector"
            ),
            {"code": item_code, "sector": sector_id}
        ).scalar()
    
        return result == 1

    def exists_management_unit(self, unit_id: int) -> bool:
        """Verifica se a unidade realmente existe."""
        # Uma consulta rápida no banco para saber se o ID é válido
        result = self._session.execute(
            text("SELECT 1 FROM dim_management_unit WHERE id = :unit_id"),
            {"unit_id": unit_id}
        ).scalar()

        return result == 1