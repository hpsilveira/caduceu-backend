from dataclasses import dataclass
from app.shared.domain.enums import UserRole

@dataclass(frozen=True)
class CreateUserCommand:
    """Comando para criação de novo usuário no sistema."""
    username: str
    full_name: str
    password: str
    sector_code: str
    role: UserRole