"""Costura da suíte de API: o app é montado sobre um banco de teste, nunca sobre o do ambiente.

Diferente da suíte unitária, aqui importar `app.*.infra.*` e `app.supplies.main` é legítimo —
é justamente o acoplamento a esses adaptadores que se quer provar. O preço é o `AUTH_SECRET_KEY`:
`app/auth/config.py` lê a variável sem default, então ela é definida antes de qualquer import de
`app.*`. `setdefault` perde para um `.env` do dev? Não: `load_dotenv` não sobrescreve o que já está
no ambiente, então o valor de teste é o que vale e a suíte fica hermética.
"""
import os

os.environ.setdefault("AUTH_SECRET_KEY", "chave-usada-so-por-testes-para-assinar-jwt")

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.supplies.infra.database.config import build_engine, build_session_factory
from app.supplies.main import create_app


@pytest.fixture
def engine(tmp_path: str) -> Iterator[Engine]:
    """Engine de um arquivo SQLite exclusivo do teste, montada pelo código de produção.

    `build_engine` é usado em vez de um `create_engine` cru porque o `PRAGMA foreign_keys=ON`
    mora nele: teste que não passa por lá não fiscaliza FK como o dev fiscaliza. Arquivo em
    `tmp_path` (e não `sqlite://` na memória) porque memory DB tem uma database por conexão.
    """
    engine = build_engine(f"sqlite:///{tmp_path}/caduceu-test.db")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return build_session_factory(engine)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """`with` dispara o lifespan: schema criado e seed rodando no banco do teste."""
    with TestClient(create_app(session_factory=session_factory)) as test_client:
        yield test_client


@pytest.fixture
def admin_token(client: TestClient) -> str:
    """Login do `admin` criado pelo seed, com a senha default de desenvolvimento."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
