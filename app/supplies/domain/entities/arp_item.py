from decimal import Decimal
from typing import Tuple
from uuid import UUID, uuid4
from app.shared.domain.value_objects.shared_vo import Money
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.shared.domain.exceptions import (
    BusinessRuleException,
    EntityNotFoundException
)

# Imaginando que as exceções de domínio criadas no passo anterior estão acessíveis

# Exceções específicas do escopo de Saldo e Itens
class InsufficientBalanceException(BusinessRuleException):
    """Saldo insuficiente.""";
    pass


class InvalidItemException(BusinessRuleException):
    """Dados de item inválidos.""";
    pass


class DuplicateQuotaException(BusinessRuleException):
    """Cota já existente.""";
    pass


class ArpItem:
    """Entidade interna do Agregado da Ata de Registro de Preços."""

    def __init__(
        self,
            id: UUID,
            item_code: str,
            description: str,
            total_quantity_approved: Decimal,
            quantity_consumed: Decimal,
            unit_price: Money,
            quota_units: list[UnitQuota]
        ):
        """Construtor limpo e sem efeitos colaterais para reconstituição via Repositório."""
        self._id: UUID = id
        self._item_code: str = item_code
        self._description: str = description
        self._total_quantity_approved: Decimal = total_quantity_approved
        self._quantity_consumed: Decimal = quantity_consumed
        self._unit_price: Money = unit_price
        self._quota_units: list[UnitQuota] = list(quota_units)  # Cópia defensiva

    @classmethod
    def create(
            cls,
            item_code: str,
            description: str,
            total_quantity_approved: Decimal,
            unit_price: Money
        ) -> "ArpItem":
        """Factory Method para inicializar um novo item com as regras de validação iniciais."""
        if total_quantity_approved <= Decimal("0"):
            raise InvalidItemException("A quantidade total homologada deve ser maior que zero.")
        if unit_price <= Money(amount=Decimal("0.00")):
            raise InvalidItemException("O preço unitário deve ser maior que zero.")

        return cls(
            id=uuid4(),
            item_code=item_code,
            description=description,
            total_quantity_approved=total_quantity_approved,
            quantity_consumed=Decimal("0.00"),
            unit_price=unit_price,
            quota_units=[]
        )

    # --- GETTERS (Encapsulamento estrito das propriedades) ---
    @property
    def id(self) -> UUID: return self._id

    @property
    def item_code(self) -> str: return self._item_code

    @property
    def description(self) -> str: return self._description

    @property
    def total_quantity_approved(self) -> Decimal: return self._total_quantity_approved

    @property
    def quantity_consumed(self) -> Decimal: return self._quantity_consumed

    @property
    def unit_price(self) -> Money: return self._unit_price

    @property
    def quota_units(self) -> Tuple[UnitQuota, ...]:
        """Garante que a lista interna não possa ser mutada via append ou pop de fora."""
        return tuple(self._quota_units)

    # --- PROPRIEDADES CALCULADAS (Invariantes de leitura) ---
    @property
    def remaining_balance(self) -> Decimal:
        """Calcula o saldo físico restante do item na Ata."""
        return self._total_quantity_approved - self._quantity_consumed

    @property
    def total_value_approved(self) -> Money:
        """Valor total financeiro originalmente registrado para este item."""
        return self._unit_price * self._total_quantity_approved

    # --- COMPORTAMENTOS ---
    def add_quota_unit(self, quota: UnitQuota) -> None:
        """Adiciona uma cota regional ao item validando duplicações."""
        if any(q.unit_id == quota.unit_id for q in self._quota_units):
            raise DuplicateQuotaException(f"A unidade {quota.unit_id} já possui cota para este item.")

        # 2. Validação da Invariante de Negócio principal: Soma das cotas não pode passar do homologado
        current_allocated_sum = sum(q.total_allocated for q in self._quota_units)
        predicted_total_allocated = current_allocated_sum + quota.total_allocated

        if predicted_total_allocated > self._total_quantity_approved:
            raise BusinessRuleException(
                f"A alocação desta cota excede a quantidade total aprovada do item na ARP. "
            )
        self._quota_units.append(quota)

    def adjust_quota_allocation(self, unit_id: int, new_total: Decimal) -> None:
        """Ajusta o teto alocado para uma unidade validando o saldo global disponível."""
        quota = next((q for q in self._quota_units if q.unit_id == unit_id), None)
        if not quota:
            raise EntityNotFoundException(f"Cota não encontrada para a unidade {unit_id}.")
        
        # Calcula qual será a nova soma de todas as cotas se aplicarmos a alteração
        current_allocated_sum = sum(q.total_allocated for q in self._quota_units)
        predicted_sum = (current_allocated_sum - quota.total_allocated) + new_total

        if predicted_sum > self._total_quantity_approved:
            raise BusinessRuleException("A nova distribuição de cotas excede o total aprovado do item.")
            
        if new_total < quota.consumed:
            raise BusinessRuleException("O novo total da cota não pode ser menor do que a unidade já consumiu.")

        # Contorna o frozen=True para atualizar a propriedade de negócio com segurança
        object.__setattr__(quota, '_total_allocated', new_total)

    def debit_quantity(self, quantity: Decimal, unit_id: int) -> None:
        """Valida e debita em cascata: Primeiro o saldo global, depois a cota da unidade."""
        if quantity <= Decimal("0"):
            raise InvalidItemException("A quantidade a ser debitada deve ser maior que zero.")
            
        # 1. Validação do Saldo Global da Ata
        if quantity > self.remaining_balance:
            raise InsufficientBalanceException(
                f"Saldo global insuficiente na ARP para o item {self._item_code}. "
                f"Disponível: {self.remaining_balance}, Solicitado: {quantity}"
            )

        # 2. Localiza a cota da unidade requisitante
        quota = next((q for q in self._quota_units if q.unit_id == unit_id), None)
        if not quota:
            raise EntityNotFoundException(
                f"A unidade {unit_id} não possui cota autorizada para o item {self._item_code}."
            )

        # 3. Executa o débito na cota da unidade (delega para a sub-entidade UnitQuota)
        quota.debit(quantity)
        
        # 4. Consolida deduzindo do saldo global da Ata após sucesso da cota interna
        self._quantity_consumed += quantity
