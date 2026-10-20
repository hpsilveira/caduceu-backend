"""`GetArpQueryHandler` — o lado de leitura do isolamento por setor.

Query não toca o domínio (CQRS): a raiz do agregado não tem como validar nada aqui, então a
única proteção é o `sector_id` do usuário chegar até o adaptador de leitura. O recording do
fake existe precisamente para provar isso — sem ele, trocar o argumento pelo setor da própria
ata seria uma mudança silenciosa e perigosa.
"""
from uuid import UUID, uuid4

import pytest

from app.shared.domain.exceptions import EntityNotFoundException
from app.supplies.application.queries.dtos import GetArpQuery, GetArpResponseDTO
from app.supplies.application.queries.get_arp_handler import GetArpQueryHandler
from tests.builders import ARP_NUMBER, OTHER_SECTOR_ID, PROCESS_SEI, SECTOR_ID, EXPIRATION_DATE
from tests.fakes.query_service import FakeQueryService


def make_response_dto(arp_id: UUID) -> GetArpResponseDTO:
    """Projeção mínima: o handler não inspeciona o corpo, só decide entre devolver e explodir."""
    return GetArpResponseDTO(
        id=arp_id,
        arp_number=ARP_NUMBER,
        process_sei=PROCESS_SEI,
        expiration_date=EXPIRATION_DATE.isoformat(),
        items=[],
        is_active=True,
    )


def test_returns_the_projection_and_passes_the_user_sector_to_the_port(fake_query_service: FakeQueryService) -> None:
    arp_id = uuid4()
    dto = make_response_dto(arp_id)
    fake_query_service.get_arp_result = dto
    query = GetArpQuery(arp_id=arp_id)

    result = GetArpQueryHandler(fake_query_service).handle(query, SECTOR_ID)

    assert result is dto
    method_name, args, kwargs = fake_query_service.calls[0]
    assert method_name == "execute_get_arp_by_id"
    assert args == (query, SECTOR_ID)
    assert kwargs == {}


def test_a_foreign_sector_never_reaches_the_port(fake_query_service: FakeQueryService) -> None:
    """O handler não filtra: quem filtra é o adaptador, e o setor precisa chegar até ele."""
    query = GetArpQuery(arp_id=uuid4())
    fake_query_service.get_arp_result = None

    with pytest.raises(EntityNotFoundException):
        GetArpQueryHandler(fake_query_service).handle(query, OTHER_SECTOR_ID)

    assert fake_query_service.calls[0][1] == (query, OTHER_SECTOR_ID)
