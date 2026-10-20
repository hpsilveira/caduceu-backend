"""
Raiz da suíte de testes.

Regra de import dos testes unitários (domínio + handlers): nenhum módulo daqui
importa `app.auth.*`, `app.supplies.main` nem nada em `app.*.infra.*`.

O motivo é o `app/auth/config.py`, que lê `os.environ["AUTH_SECRET_KEY"]` sem default: um
unit test que importasse o contexto auth passaria a depender de `.env`. A engine não é mais
motivo — desde 15/10/2026 nada em `config.py` abre banco no import, ela vive no `app.state`.
Quem precisa de infra é a suíte de API (`tests/integration/`), com conftest próprio.
"""
import pytest

from tests.fakes.arp_repository import FakeArpRepository
from tests.fakes.query_service import FakeQueryService


@pytest.fixture
def fake_arp_repository() -> FakeArpRepository:
    """Escopo de função: cada teste recebe um repositório em branco e isolado."""
    return FakeArpRepository()


@pytest.fixture
def fake_query_service() -> FakeQueryService:
    return FakeQueryService()
