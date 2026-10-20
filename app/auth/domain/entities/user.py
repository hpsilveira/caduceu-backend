from dataclasses import dataclass
from uuid import UUID, uuid4
from datetime import datetime

from app.shared.domain.enums import UserRole
from app.auth.domain.value_objects.token_claims import TokenClaims

@dataclass(frozen=True)
class User:
    id: UUID
    username: str
    full_name: str
    hashed_password: str
    role: UserRole
    sector_id: int
    sector_code:str
    must_change_password: bool = True
    is_active: bool = True

    def to_claims(self, expire_at: datetime) -> TokenClaims:
        """Converte a entidade para o formato de claims do JWT com isolamento."""
        return {
            "sub": self.username,
            "full_name": self.full_name,
            "role": self.role.value,
            "sector_code": self.sector_code,
            "must_change_password": self.must_change_password,
            "exp": expire_at
        }

    @classmethod
    def create(
        cls,
        username: str,
        full_name: str,
        hashed_password: str,
        sector_id: int,
        sector_code: str,
        role: UserRole = UserRole.READ
    ):
        return cls(
            id=uuid4(),
            username=username,
            full_name=full_name,
            hashed_password=hashed_password,
            sector_id=sector_id,
            sector_code=sector_code,
            role=role,
            must_change_password=True,
            is_active=True
        )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_global_admin(self) -> bool:
        return self.sector_code == "GLOBAL_ADMIN"

    @property
    def can_write(self) -> bool:
        return self.role in (UserRole.WRITE, UserRole.ADMIN)
