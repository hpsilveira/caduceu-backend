from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from app.shared.domain.exceptions import BusinessRuleException

# Imaginando que as exceções de domínio criadas no passo anterior estão acessíveis
class InvalidOrderException(BusinessRuleException):
    """Lançada quando os dados do pedido de abastecimento são inválidos."""
    pass


class SupplyOrder:
    """
    Aggregate Root que rastreia o evento histórico e transacional 
    de consumo de um item de ARP por uma unidade gestora.
    """

    def __init__(
            self,
            id: UUID,
            arp_id: UUID,
            item_code: str,
            unit_id: int,
            quantity_requested: Decimal,
            process_sei_request: str,
            created_at: datetime
        ):
        """Construtor puro para reconstituição via infraestrutura/repositório."""
        self._id: UUID = id
        self._arp_id: UUID = arp_id
        self._item_code: str = item_code
        self._unit_id: int = unit_id
        self._quantity_requested: Decimal = quantity_requested
        self._process_sei_request: str = process_sei_request
        self._created_at: datetime = created_at

    @classmethod
    def create(
            cls,
            arp_id: UUID,
            item_code: str,
            unit_id: int,
            quantity_requested: Decimal,
            process_sei_request: str
        ) -> "SupplyOrder":
        """Factory Method para emissão de novos pedidos de abastecimento."""
        if quantity_requested <= Decimal("0"):
            raise InvalidOrderException("A quantidade requisitada deve ser maior que zero.")
        if not process_sei_request.strip():
            raise InvalidOrderException("O número do processo SEI da requisição é obrigatório.")

        return cls(
            id=uuid4(),
            arp_id=arp_id,
            item_code=item_code,
            unit_id=unit_id,
            quantity_requested=quantity_requested,
            process_sei_request=process_sei_request,
            created_at=datetime.now(timezone.utc)
        )

    # --- GETTERS ---
    @property
    def id(self) -> UUID: return self._id

    @property
    def arp_id(self) -> UUID: return self._arp_id

    @property
    def item_code(self) -> str: return self._item_code

    @property
    def unit_id(self) -> int: return self._unit_id

    @property
    def quantity_requested(self) -> Decimal: return self._quantity_requested

    @property
    def process_sei_request(self) -> str: return self._process_sei_request

    @property
    def created_at(self) -> datetime: return self._created_at
