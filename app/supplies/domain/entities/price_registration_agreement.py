from datetime import date
from decimal import Decimal
from typing import Tuple
from uuid import UUID, uuid4
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.shared.domain.exceptions import (
    BusinessRuleException, EntityNotFoundException
)

# Exceções específicas deste Agregado
class InvalidArpException(BusinessRuleException):
    """Contrato inválido ou expirado.""";
    pass


class DuplicateItemException(BusinessRuleException):
    """Item duplicado na ata.""";
    pass


class PriceRegistrationAgreement:
    """Aggregate Root para gerenciamento de Atas de Registro de Preços (ARP)."""

    def __init__(
        self,
        id: UUID,
        arp_number: str,
        process_sei: str,
        expiration_date: date,
        owner_sector_id: int,
        items: list[ArpItem],
        is_active: bool
    ):
        """
        Construtor puro destinado à reconstituição pelo Repositório.
        Não possui efeitos colaterais como geração de UUID ou validação de data corrente.
        """
        self._id: UUID = id
        self._arp_number: str = arp_number
        self._process_sei: str = process_sei
        self._expiration_date: date = expiration_date
        self._owner_sector_id: int = owner_sector_id
        self._items: list[ArpItem] = list(items)  # Cópia defensiva
        self._is_active: bool = is_active

    @classmethod
    def create(
        cls,
        arp_number: str,
        process_sei: str,
        expiration_date: date,
        owner_sector_id: int,
        current_date: date  # Passado explicitamente para testabilidade e pureza
    ) -> "PriceRegistrationAgreement":
        """Factory Method para criação de novas instâncias no fluxo de negócio."""
        if expiration_date < current_date:
            raise InvalidArpException("A data de vencimento da ARP não pode ser no passado.")

        return cls(
            id=uuid4(),
            arp_number=arp_number,
            process_sei=process_sei,
            expiration_date=expiration_date,
            owner_sector_id=owner_sector_id,
            items=[],
            is_active=True
        )

    def add_new_item(self, item: ArpItem) -> None:
        """Comportamento para aditivos: Adiciona um novo item à ata jurídica."""
        if any(i.item_code == item.item_code for i in self._items):
            raise DuplicateItemException(f"O item {item.item_code} já existe nesta Ata.")
        self._items.append(item)

    def allocate_quota_to_item(self, item_code: str, quota: UnitQuota) -> None:
        """Localiza o item interno e delega a criação de uma nova cota regional."""
        target_item = next((i for i in self._items if i.item_code == item_code), None)
        if not target_item:
            raise EntityNotFoundException(f"Item {item_code} não pertence a esta Ata.")
        
        # O próprio item vai validar se a unidade já não possui cota
        target_item.add_quota_unit(quota)

    # --- GETTERS (Encapsulamento estrito) ---
    @property
    def id(self) -> UUID: return self._id
    
    @property
    def arp_number(self) -> str: return self._arp_number
    
    @property
    def process_sei(self) -> str: return self._process_sei
    
    @property
    def expiration_date(self) -> date: return self._expiration_date
    
    @property
    def owner_sector_id(self) -> int:
        return self._owner_sector_id

    @property
    def is_active(self) -> bool: return self._is_active

    @property
    def items(self) -> Tuple[ArpItem, ...]:
        """Retorna uma tupla para impedir modificações externas diretas na lista."""
        return tuple(self._items)

    # --- COMPORTAMENTOS / REGRAS DE NEGÓCIO ---
    def validate_ownership(self, user_sector_id: int) -> None:
        """Regra rica: A própria entidade se protege contra invasão de setor."""
        if self._owner_sector_id != user_sector_id:
            raise BusinessRuleException("Esta Ata não pertence ao seu setor operacional.")

    def add_item(self, item: ArpItem) -> None:
        """Adiciona um item homologado à Ata garantindo a unicidade."""
        if any(i.item_code == item.item_code for i in self._items):
            raise DuplicateItemException(f"O item com código {item.item_code} já existe nesta ARP.")
        self._items.append(item)

    def request_supply(self, item_code: str, quantity: Decimal, unit_id: int, current_date: date) -> None:
        """
        Orquestra o débito de saldo de uma unidade gestora.
        Garante conformidade com prazos e saldos vigentes.
        """
        if not self._is_active:
            raise InvalidArpException("Esta ARP encontra-se inativa.")
            
        if current_date > self._expiration_date:
            self._is_active = False  # Mutação interna de estado válida pela regra de negócio
            raise InvalidArpException("Esta ARP está expirada e não permite novos débitos.")

        target_item = next((i for i in self._items if i.item_code == item_code), None)
        if not target_item:
            raise EntityNotFoundException(f"Item com código {item_code} não pertence a esta ARP.")

        # Delegação para a entidade interna do agregado
        target_item.debit_quantity(quantity, unit_id)
