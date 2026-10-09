from pydantic import BaseModel, Field
from app.shared.domain.enums import UserRole

class UserChangePasswordRequestSchema(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequestSchema(BaseModel):
    """Schema de entrada para criação de novo usuário."""
    username: str = Field(..., min_length=6, max_length=50, description="Username único")
    full_name: str = Field(..., min_length=3, max_length=100)
    sector_code: str = Field(..., min_length=1, max_length=50, description="Setor operacional")
    role: UserRole = Field(..., description="Perfil de acesso (read, write, admin)")