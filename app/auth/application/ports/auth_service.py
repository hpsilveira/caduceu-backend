from abc import ABC, abstractmethod
from app.auth.domain.value_objects.token_claims import TokenClaims

class AuthService(ABC):
    @abstractmethod
    def create_access_token(self, claims: TokenClaims) -> str:
        """Gera um token JWT assinado a partir das claims fornecidas."""
        pass
    
    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        pass

    @abstractmethod
    def get_password_hash(self, password: str) -> str:
        pass
        
    @abstractmethod
    def decode_token(self, token: str) -> TokenClaims | None:
        """Decodifica e valida um token, retornando suas claims estruturadas."""
        pass
