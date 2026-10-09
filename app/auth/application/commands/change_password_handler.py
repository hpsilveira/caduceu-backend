from app.auth.application.ports.user_repository import UserRepository
from app.auth.application.ports.auth_service import AuthService
from app.auth.infra.web.schemas import UserChangePasswordRequestSchema
from app.shared.domain.exceptions import (
    EntityNotFoundException, BusinessRuleException
)

class ChangePasswordHandler:
    def __init__(self, repository: UserRepository, auth_service: AuthService):
        self._repository = repository
        self._auth_service = auth_service

    def handle(self, username: str, payload: UserChangePasswordRequestSchema) -> None:
        user = self._repository.find_by_username(username)
        if not user:
            raise EntityNotFoundException("Usuário não localizado.")

        # Valida se a senha atual digitada está correta
        if not self._auth_service.verify_password(payload.current_password, user.hashed_password):
            raise BusinessRuleException("A senha atual informada está incorreta.")

        # Criptografa a nova senha e desliga a trava de primeiro acesso
        nova_senha_hash = self._auth_service.get_password_hash(payload.new_password)
        
        # Salvamento direto via repositório/banco
        self._repository.update_password(
            username,
            nova_senha_hash,
            must_change_password=False
        )
