from decimal import Decimal
from uuid import UUID, uuid4
from app.shared.domain.exceptions import (
    BusinessRuleException
)

# Exceção de negócio específica para cotas de unidades gestoras
class QuotaExceededException(BusinessRuleException):
    """Lançada quando uma unidade gestora tenta debitar mais do que sua cota permite."""
    pass


class InvalidQuotaException(BusinessRuleException):
    """Lançada quando os parâmetros de inicialização da cota são inválidos."""
    pass


class UnitQuota:
    """Entidade interna que rastreia a cota específica de um item atribuída a uma unidade gestora."""

    def __init__(
            self,
            id: UUID,
            unit_id: int,
            total_allocated: Decimal,
            consumed: Decimal
        ):
        """Construtor puro utilizado para reconstituição pelo Repositório."""
        self._id: UUID = id
        self._unit_id: int = unit_id
        self._total_allocated: Decimal = total_allocated
        self._consumed: Decimal = consumed

    @classmethod
    def create(cls, unit_id: int, total_allocated: Decimal) -> "UnitQuota":
        """Factory Method para inicialização de novas cotas de unidades no domínio."""
        if total_allocated <= Decimal("0"):
            raise InvalidQuotaException("A cota alocada para a unidade deve ser maior que zero.")
            
        return cls(
            id=uuid4(),
            unit_id=unit_id,
            total_allocated=total_allocated,
            consumed=Decimal("0.00")
        )

    # --- GETTERS ---
    @property
    def id(self) -> UUID: return self._id

    @property
    def unit_id(self) -> int: return self._unit_id

    @property
    def total_allocated(self) -> Decimal: return self._total_allocated

    @property
    def consumed(self) -> Decimal: return self._consumed

    # --- PROPRIEDADE CALCULADA ---
    @property
    def remaining_balance(self) -> Decimal:
        """Calcula o saldo remanescente disponível para a unidade gestora."""
        return self._total_allocated - self._consumed

    # --- COMPORTAMENTO ---
    def debit(self, quantity: Decimal) -> None:
        """Executa a dedução física do saldo da cota da unidade."""
        if quantity <= Decimal("0"):
            raise InvalidQuotaException("A quantidade a ser debitada deve ser maior que zero.")

        if quantity > self.remaining_balance:
            raise QuotaExceededException(
                f"Cota insuficiente para a unidade gestora {self._unit_id}. "
                f"Disponível: {self.remaining_balance}, Solicitado: {quantity}"
            )
        self._consumed += quantity
