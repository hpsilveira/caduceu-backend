"""Prova de que o `pythonpath` do pyproject.toml resolve os namespace packages do repo.

Não é um teste de comportamento — é um teste de infraestrutura: se `app` não for
importável a partir da raiz do repo, toda a suíte falha com ModuleNotFoundError e a
causa parece estar longe do problema real.
"""
import subprocess
import sys
from pathlib import Path

from app.shared.domain.value_objects.shared_vo import Money
from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.supplies.application.ports.database.query_service import QueryService
from app.supplies.domain.entities.arp import Arp
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.supply_order import SupplyOrder
from app.supplies.domain.entities.unit_quota import UnitQuota


def test_domain_is_importable_without_infra() -> None:
    assert {Arp.__name__, ArpItem.__name__, UnitQuota.__name__, SupplyOrder.__name__} == {
        "Arp", "ArpItem", "UnitQuota", "SupplyOrder",
    }
    assert Money.__name__ == "Money"


def test_ports_are_importable() -> None:
    assert ArpRepository.__name__ == "ArpRepository"
    assert QueryService.__name__ == "QueryService"


def test_importing_the_domain_does_not_pull_sqlalchemy_or_fastapi() -> None:
    """A regra de import dos unit tests, executable — num processo limpo.

    Checar `sys.modules` do próprio pytest deixaria de valer a partir do momento em que a suíte de
    integração importa sqlalchemy no mesmo processo (que é legítimo lá). O que se quer provar é que
    *importar domínio e application sozinhos* não puxa adaptador nenhum — e isso só existe num
    interpretador que não viu os outros testes.
    """
    repo_root = Path(__file__).resolve().parents[3]
    snippet = (
        "import sys;"
        "import app.supplies.domain.entities.arp;"
        "import app.supplies.application.ports.database.query_service;"
        "offenders = [p for p in ('sqlalchemy', 'fastapi', 'pydantic') if p in sys.modules];"
        "print(','.join(offenders));"
        "sys.exit(1 if offenders else 0)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, f"importou adaptadores: {completed.stdout.strip()}"
    assert completed.stdout.strip() == ""
