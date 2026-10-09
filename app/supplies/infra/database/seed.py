import csv
import os
from pathlib import Path

from sqlalchemy import delete

from app.shared.domain.enums import UserRole
from app.supplies.infra.database.config import SessionFactory, init_db
from app.auth.infra.services.jwt_auth_service import JwtAuthService
from app.supplies.infra.database.models import (
    DimCatalogItemModel,
    DimManagementUnitModel,
    DimSectorModel,
    UserModel
)

CATALOG_CSV = Path(__file__).parent / "seed_data" / "catalog_items.csv"
MANAGEMENT_UNITS_CSV = Path(__file__).parent / "seed_data" / "management_units.csv"

# A senha inicial só permanece no código como conveniência de desenvolvimento:
# em produção CADUCEU_ADMIN_PASSWORD deve ser definida e a troca é exigida no primeiro acesso.
ADMIN_INITIAL_PASSWORD = os.getenv("CADUCEU_ADMIN_PASSWORD", "admin123")


def _load_catalog_items(sector_id_by_code: dict[str, int]) -> list[DimCatalogItemModel]:
    """Carrega o catálogo de insumos da COADI exportado da planilha oficial."""
    with CATALOG_CSV.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    items: list[DimCatalogItemModel] = []
    for row in rows:
        sector_code = row["sector_code"].strip().upper()
        if sector_code not in sector_id_by_code:
            raise ValueError(
                f"O item '{row['item_code']}' referencia o setor desconhecido '{row['sector_code']}'."
            )
        items.append(DimCatalogItemModel(
            item_code=row["item_code"].strip(),
            description=row["description"].strip(),
            category=row["category"].strip(),
            catalog_id=sector_id_by_code[sector_code]
        ))
    return items


def _load_management_units() -> list[DimManagementUnitModel]:
    """Carrega a relação de unidades gestoras exportada da planilha oficial da COADI."""
    with MANAGEMENT_UNITS_CSV.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    return [DimManagementUnitModel(
        id=int(row["id"]),
        name=row["name"].strip(),
        cnpj=row["cnpj"].strip()
    ) for row in rows]


def seed():
    """Popula o banco com os dados de referência da COADI e o usuário administrador."""
    print("⏳ Iniciando a carga inicial de dados (Seed)...")

    # Garante que as tabelas existem ao rodar o script fora do lifespan do FastAPI
    init_db()

    session = SessionFactory()
    auth_service = JwtAuthService()

    try:
        # Limpeza para permitir a recarga dos dados de referência (filhos antes de dim_sector)
        session.execute(delete(DimCatalogItemModel))
        session.execute(delete(UserModel))
        session.execute(delete(DimManagementUnitModel))
        session.execute(delete(DimSectorModel))
        session.commit()

        # =========================================================================
        # 1. SETORES OPERACIONAIS (SESAP/RN)
        # =========================================================================
        sectors = [
            DimSectorModel(
                id=1,
                code="GLOBAL_ADMIN",
                name="Administração Global do Sistema"
            ),
            DimSectorModel(
                id=2,
                code="SAS",
                name="Subcoordenadoria de Aquisições e Suprimentos"
            ),
            DimSectorModel(
                id=3,
                code="EPA",
                name="Estratégia e Planejamento Administrativo"
            ),
        ]
        session.add_all(sectors)
        session.commit()
        sector_id_by_code = {sector.code: sector.id for sector in sectors}

        # =========================================================================
        # 2. USUÁRIO ADMINISTRADOR
        # =========================================================================
        # Demais usuários são criados em produção pelo admin via POST /api/v1/auth/users
        session.add(UserModel(
            username="admin",
            full_name="Administrador do Sistema",
            hashed_password=auth_service.get_password_hash(ADMIN_INITIAL_PASSWORD),
            role=UserRole.ADMIN,
            sector_id=sector_id_by_code["GLOBAL_ADMIN"],
            must_change_password=True,
            is_active=True
        ))
        session.commit()
        print("👤 Usuário 'admin' criado. A senha inicial deve ser trocada no primeiro acesso.")

        # =========================================================================
        # 3. DIMENSÃO DE UNIDADES GESTORAS (SESAP/RN)
        # =========================================================================
        management_units = _load_management_units()
        session.add_all(management_units)
        session.commit()
        print(f"🏥 Unidades Gestoras cadastradas: {len(management_units)}!")

        # =========================================================================
        # 4. DIMENSÃO DO CATÁLOGO DE INSUMOS (COADI)
        # =========================================================================
        catalog_items = _load_catalog_items(sector_id_by_code)
        session.add_all(catalog_items)
        session.commit()
        print(f"📦 Catálogo de referência carregado com {len(catalog_items)} itens!")

        print("✅ [CADUCEU] Carga inicial concluída com sucesso!")

    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao rodar o seed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    # Permite rodar o script diretamente pelo terminal: python -m app.supplies.infra.database.seed
    seed()
