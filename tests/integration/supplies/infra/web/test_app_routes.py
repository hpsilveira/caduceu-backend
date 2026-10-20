"""Testes de rota: o fio entre HTTP, DI e adaptador SQLAlchemy — todos contra a engine injetada.

Cada caso escreve no banco do teste um dado que não existe em banco nenhum outro (usuário, item de
catálogo, ata e unidade sentinela) e afirma que a resposta HTTP o vê. Assim a injeção não passa por
coincidência: com `create_app` ignorando o parâmetro `session_factory`, os testes de login/401
continuavam verdes porque o banco do ambiente também tem o `admin` do seed — aqui eles falham junto
com os demais. O que sobra intencionalmente independente de banco é `/health` (prova de que não
abre conexão) e o 401 sem token (rejeita antes da consulta ao usuário).
"""
from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.auth.infra.services.jwt_auth_service import JwtAuthService
from app.shared.domain.enums import UserRole
from app.supplies.infra.database.models import (
    ArpModel,
    DimCatalogItemModel,
    DimManagementUnitModel,
    UserModel
)
from app.supplies.main import create_app

SAS_SECTOR_ID = 2
SENTINELA_UNIT_ID = 999_999
SENTINELA_ITEM_CODE = "SENTINELA-0001"
SENTINELA_ARP_NUMBER = "SENTINELA-ATA/2026"
SENTINELA_USER = "operador.sentinela"
SENTINELA_PASSWORD = "senha-que-so-vale-no-banco-de-teste"


def _new_user(
        session_factory: sessionmaker[Session],
        *,
        username: str,
        sector_id: int = SAS_SECTOR_ID
    ) -> None:
    """Escreve o usuário direto na engine injetada, sem passar pela API."""
    with session_factory() as session:
        session.add(UserModel(
            username=username,
            full_name="Usuário Sentinela do Teste",
            hashed_password=JwtAuthService().get_password_hash(SENTINELA_PASSWORD),
            role=UserRole.WRITE,
            sector_id=sector_id,
            must_change_password=False,
            is_active=True
        ))
        session.commit()


def _login_token(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_responds_without_any_schema(session_factory: sessionmaker[Session]) -> None:
    """Liveness do Render provada contra um banco sem tabela alguma.

    `bootstrap=None` não cria o schema: se `/health` tocasse o banco, a rota morreria aqui em vez
    de responder 200 — que é exatamente o que o docstring dela promete para picos de latência.
    """
    with TestClient(create_app(session_factory=session_factory, bootstrap=None)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_creates_the_schema_and_seeds_the_test_database(
        session_factory: sessionmaker[Session]
    ) -> None:
    """O bootstrap vale para a engine injetada: tabelas e catálogo nascem no arquivo do teste."""
    with TestClient(create_app(session_factory=session_factory)) as client:
        with session_factory() as session:
            assert session.execute(text("SELECT COUNT(*) FROM dim_catalog_item")).scalar_one() > 0
        assert client.get("/health").status_code == 200


def test_protected_route_without_a_token_is_refused(client: TestClient) -> None:
    """A rejeição acontece na dependência de auth, antes de qualquer consulta ao banco."""
    assert client.get("/api/v1/supplies/lookups/units").status_code == 401


def test_admin_login_uses_the_hash_from_the_injected_engine(
        client: TestClient,
        session_factory: sessionmaker[Session]
    ) -> None:
    """A senha do admin é trocada só no banco do teste: vale a nova, não a do seed.

    Sem isso o teste passava com o app apontando para qualquer banco — o `caduceu.db` do dev tem o
    mesmo `admin`/senha do seed. A troca localiza a leitura de `hashed_password` na engine injetada.
    """
    with session_factory() as session:
        session.execute(
            update(UserModel)
            .where(UserModel.username == "admin")
            .values(hashed_password=JwtAuthService().get_password_hash(SENTINELA_PASSWORD))
        )
        session.commit()

    assert _login_token(client, "admin", SENTINELA_PASSWORD).count(".") == 2

    seed_login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert seed_login.status_code == 422


def test_a_user_that_only_exists_in_the_injected_engine_logs_in_and_reaches_a_protected_route(
        client: TestClient,
        session_factory: sessionmaker[Session]
    ) -> None:
    _new_user(session_factory, username=SENTINELA_USER)

    token = _login_token(client, SENTINELA_USER, SENTINELA_PASSWORD)
    response = client.get(
        "/api/v1/supplies/lookups/units",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200


def test_a_user_deleted_from_the_injected_engine_loses_access(
        client: TestClient,
        session_factory: sessionmaker[Session]
    ) -> None:
    """Token válido, usuário ausente: o 401 vem da leitura do usuário na engine do teste.

    Prova o caminho inverso do anterior — a credencial continua assinada e correta, mas o banco
    que o app consulta não tem mais a linha.
    """
    _new_user(session_factory, username=SENTINELA_USER)
    token = _login_token(client, SENTINELA_USER, SENTINELA_PASSWORD)

    with session_factory() as session:
        session.execute(delete(UserModel).where(UserModel.username == SENTINELA_USER))
        session.commit()

    response = client.get(
        "/api/v1/supplies/lookups/units",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_a_read_route_uses_the_injected_engine(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Marcador escrito direto no banco do teste: se a rota ler o `caduceu.db` do ambiente, ele não aparece."""
    with session_factory() as session:
        session.add(DimManagementUnitModel(id=SENTINELA_UNIT_ID, name="Unidade Sentinela", cnpj=""))
        session.commit()

    response = client.get("/api/v1/supplies/lookups/units", headers=auth_headers)

    assert response.status_code == 200
    assert SENTINELA_UNIT_ID in [item["id"] for item in response.json()["items"]]


def test_the_user_sector_decides_which_arps_show_up_in_the_search(
        client: TestClient,
        auth_headers: dict[str, str],
        session_factory: sessionmaker[Session]
    ) -> None:
    """Isolamento por setor na borda, com controle positivo.

    Sem o operador do SAS vendo a ata, a lista vazia do `admin` seria verdade vaciosa: passaria até
    com o adaptador devolvendo nada para todo mundo. Os dois lados juntos é que provam que o
    `sector_id` do usuário viaja até o `WHERE` do adaptador.
    """
    _new_user(session_factory, username=SENTINELA_USER, sector_id=SAS_SECTOR_ID)
    with session_factory() as session:
        session.add(ArpModel(
            id=uuid4(),
            arp_number=SENTINELA_ARP_NUMBER,
            process_sei="00610000.000000/2026-00",
            expiration_date=date(2026, 12, 31),
            is_active=True,
            sector_id=SAS_SECTOR_ID
        ))
        session.add(DimCatalogItemModel(
            code=SENTINELA_ITEM_CODE,
            description="Item Sentinela do Catálogo SAS",
            category="SENTINELA",
            sector_id=SAS_SECTOR_ID
        ))
        session.commit()

    operator_headers = {"Authorization": f"Bearer {_login_token(client, SENTINELA_USER, SENTINELA_PASSWORD)}"}

    operator_arps = client.get("/api/v1/supplies/arps", headers=operator_headers).json()
    operator_catalog = client.get("/api/v1/supplies/lookups/items", headers=operator_headers).json()
    admin_catalog = client.get("/api/v1/supplies/lookups/items", headers=auth_headers).json()
    admin_arps = client.get("/api/v1/supplies/arps", headers=auth_headers).json()

    assert SENTINELA_ARP_NUMBER in [arp["arp_number"] for arp in operator_arps["items"]]
    assert operator_arps["total_count"] == 1
    assert SENTINELA_ITEM_CODE in [item["code"] for item in operator_catalog["items"]]
    assert admin_catalog["items"] == []
    assert admin_arps["items"] == []
    assert admin_arps["total_count"] == 0
