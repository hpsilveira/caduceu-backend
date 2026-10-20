# app/adapters/database/models.py
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from app.shared.domain.enums import UserRole

class Base(DeclarativeBase):
    """Classe base declarativa do ORM"""
    pass


class ArpModel(Base):
    __tablename__ = "arp"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    arp_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    process_sei: Mapped[str] = mapped_column(String(30), nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sector_id: Mapped[int] = mapped_column(ForeignKey("dim_sector.id"), nullable=False, index=True)
    items: Mapped[list["ArpItemModel"]] = relationship(
        back_populates="arp", cascade="all, delete-orphan", lazy="joined"
    )


class ArpItemModel(Base):
    __tablename__ = "arp_item"

    # A invariante "um item por ata" vivia só no domínio (arp.py);
    # sem ela no banco, o join do histórico por (arp_id, item_code) faria fanning-out de débitos.
    __table_args__ = (UniqueConstraint("arp_id", "item_code", name="uq_arp_item_arp_id_item_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(
        String(50), ForeignKey("dim_catalog_item.code"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_quantity_approved: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_consumed: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    quotas: Mapped[list["UnitQuotaModel"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", lazy="joined"
    )
    arp_id: Mapped[UUID] = mapped_column(ForeignKey("arp.id", ondelete="CASCADE"), nullable=False)
    arp: Mapped["ArpModel"] = relationship(back_populates="items")


class UnitQuotaModel(Base):
    __tablename__ = "unit_quota"

    # Uma cota por unidade por item: hoje só o domínio impede (DuplicateQuotaException).
    __table_args__ = (UniqueConstraint("item_id", "unit_id", name="uq_unit_quota_item_id_unit_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    total_allocated: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    consumed: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    item: Mapped["ArpItemModel"] = relationship(back_populates="quotas")
    # Sem cascade: se uma unidade gestora sair da dimensão, a operação deve falhar e não
    # apagar as cotas que consomem o saldo da ata.
    unit_id: Mapped[int] = mapped_column(ForeignKey("dim_management_unit.id"), nullable=False)
    item_id: Mapped[UUID] = mapped_column(ForeignKey("arp_item.id", ondelete="CASCADE"), nullable=False)


class SupplyOrderModel(Base):
    """Tabela Fato Operacional: Log de transações históricas (Ideal para o Data Lake)"""
    __tablename__ = "supply_order"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    arp_id: Mapped[UUID] = mapped_column(nullable=False)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_id: Mapped[int] = mapped_column(nullable=False)
    quantity_requested: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    process_sei_request: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# =========================================================================
# TABLES FROM OTHER BOUNDED CONTEXTS (Read only / References dimensions)
# =========================================================================
class DimCatalogItemModel(Base):
    """Tabela administrada pela COADI. Suprimentos apenas lê."""
    __tablename__ = "dim_catalog_item"

    # `code` é atributo do próprio item; o String(50) casa com a FK de arp_item.item_code.
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    # Antes chamava-se `catalog_id`, mas o alvo é dim_sector.id: é o setor dono do catálogo.
    sector_id: Mapped[int] = mapped_column(ForeignKey("dim_sector.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DimManagementUnitModel(Base):
    """Tabela que mapeia a estrutura física do Estado. Suprimentos apenas lê."""
    __tablename__ = "dim_management_unit"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    cnpj: Mapped[str] = mapped_column()


class DimSectorModel(Base):
    """Tabela dimensão de setores operacionais da SESAP."""
    __tablename__ = "dim_sector"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# =========================================================================
# AUTHENTICATION MODULE (AUTH)
# =========================================================================
class UserModel(Base):
    __tablename__ = "user"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=lambda: uuid4())
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.READ, nullable=False)
    sector_id: Mapped[int] = mapped_column(ForeignKey("dim_sector.id"), nullable=False, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))