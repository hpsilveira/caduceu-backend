from datetime import datetime, timedelta, timezone
from app.auth.application.ports.user_repository import UserRepository
from app.auth.application.ports.auth_service import AuthService
from app.auth.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.shared.domain.exceptions import BusinessRuleException

class LoginHandler:
    def __init__(self, repository: UserRepository, auth_service: AuthService):
        self._repository = repository
        self._auth_service = auth_service

    def handle(self, username: str, password: str) -> str:
        # 1. Busca o usuário
        user = self._repository.find_by_username(username)

        # 2. Valida existência e senha
        if not user or not self._auth_service.verify_password(password, user.hashed_password):
            raise BusinessRuleException("Credenciais inválidas ou usuário inativo.")

        if not user.is_active:
            raise BusinessRuleException("Conta de usuário desativada.")

        # 1. Calcula a expiração baseado na constante do config.py
        expire_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        # No LoginHandler.handle:
        claims = user.to_claims(expire_at=expire_at)

        # 3. Gera o Token JWT
        return self._auth_service.create_access_token(claims)
