from dataclasses import dataclass
from typing import Optional
from decimal import Decimal, ROUND_HALF_UP
import re
from app.shared.domain.enums import StateCode
from app.shared.domain.exceptions import (
    InvalidValueException,
    BusinessRuleException
)

# =========================================================================
# STRUCTURED AND VALIDATED VALUE OBJECTS (Pure & Immutable)
# =========================================================================
@dataclass(frozen=True)
class PostalCode:
    """Value Object imutável para CEP Brasileiro."""
    value: str

    def __post_init__(self) -> None:
        clean_value = re.sub(r'\D', '', self.value)
        if len(clean_value) != 8:
            raise InvalidValueException("O CEP brasileiro deve conter exatamente 8 dígitos numéricos.")
        
        # Define o valor formatado contornando a imutabilidade do frozen=True no init
        object.__setattr__(self, 'value', f"{clean_value[:5]}-{clean_value[5:]}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Address:
    """Value Object imutável para Endereço."""
    street: str
    number: str
    district: str
    city: str
    postal_code: PostalCode
    complement: Optional[str] = None
    state: StateCode = StateCode.RN

    def __post_init__(self) -> None:
        if not self.street.strip() or len(self.street) > 128:
            raise InvalidValueException("Rua deve ter entre 1 e 128 caracteres.")
        if not self.number.strip() or len(self.number) > 10:
            raise InvalidValueException("Número deve ter entre 1 e 10 caracteres.")
        if self.complement and len(self.complement) > 64:
            raise InvalidValueException("Complemento não pode exceder 64 caracteres.")
        if not self.district.strip() or len(self.district) > 64:
            raise InvalidValueException("Bairro deve ter entre 1 e 64 caracteres.")
        if not self.city.strip() or len(self.city) > 64:
            raise InvalidValueException("Cidade deve ter entre 1 e 64 caracteres.")

    def __str__(self) -> str:
        comp = f", {self.complement}" if self.complement else ""
        return f"{self.street}, Nº {self.number}{comp}, {self.district}, {self.city} - {self.state.name}, CEP: {self.postal_code}"


@dataclass(frozen=True)
class PhoneNumber:
    """Value Object imutável para Telefone Brasileiro com DDD."""
    area_code: str
    number: str

    def __post_init__(self) -> None:
        clean_area = re.sub(r'\D', '', self.area_code)
        clean_num = re.sub(r'\D', '', self.number)
        
        if len(clean_area) != 2:
            raise InvalidValueException("O DDD deve conter exatamente 2 dígitos.")
        if len(clean_num) not in (8, 9):
            raise InvalidValueException("O número de telefone deve conter 8 ou 9 dígitos.")
            
        object.__setattr__(self, 'area_code', clean_area)
        object.__setattr__(self, 'number', clean_num)

    def __str__(self) -> str:
        if len(self.number) == 9:
            return f"({self.area_code}) {self.number[:5]}-{self.number[5:]}"
        return f"({self.area_code}) {self.number[:4]}-{self.number[4:]}"


@dataclass(frozen=True)
class ContactInfo:
    """Value Object imutável para Informações de Contato."""
    phone_number: PhoneNumber
    email: Optional[str] = None
    website: Optional[str] = None

    def __post_init__(self) -> None:
        if self.email and not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            raise InvalidValueException("Formato de e-mail inválido.")
        if self.website and not (self.website.startswith("http://") or self.website.startswith("https://")):
            raise InvalidValueException("Formato de URL do website inválido.")

    def __str__(self) -> str:
        web = f", Site: {self.website}" if self.website else ""
        email_str = f", Email: {self.email}" if self.email else ""
        return f"Tel: {self.phone_number}{email_str}{web}"


# =========================================================================
# BRAZILIAN MONETARY DOMAIN
# =========================================================================
@dataclass(frozen=True, order=False)
class Money:
    """Value Object estritamente imutável para tratamento financeiro em Real (BRL)."""
    amount: Decimal
    precision: int = 2

    def __post_init__(self) -> None:
        quantize_str = '1.' + '0' * self.precision
        rounded_amount = self.amount.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
        object.__setattr__(self, 'amount', rounded_amount)

    def __str__(self) -> str:
        return f"R$ {self.amount}"

    def __repr__(self) -> str:
        return f"Money(BRL {self.amount})"

    # --- Operações de Comparação Nativas ---
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money): return False
        return self.amount == other.amount

    def __lt__(self, other: 'Money') -> bool: return self.amount < other.amount
    def __le__(self, other: 'Money') -> bool: return self.amount <= other.amount
    def __gt__(self, other: 'Money') -> bool: return self.amount > other.amount
    def __ge__(self, other: 'Money') -> bool: return self.amount >= other.amount

    # --- Operações Matemáticas Seguras ---
    def __add__(self, other: 'Money') -> 'Money':
        return Money(amount=self.amount + other.amount, precision=self.precision)

    def __sub__(self, other: 'Money') -> 'Money':
        return Money(amount=self.amount - other.amount, precision=self.precision)

    def __mul__(self, other: int | float | Decimal) -> 'Money':
        return Money(amount=self.amount * Decimal(str(other)), precision=self.precision)

    def __truediv__(self, other: int | float | Decimal) -> 'Money':
        decimal_divisor = Decimal(str(other))
        if decimal_divisor == 0:
            raise BusinessRuleException("Não é possível dividir um valor monetário por zero.")
        return Money(amount=self.amount / decimal_divisor, precision=self.precision)
