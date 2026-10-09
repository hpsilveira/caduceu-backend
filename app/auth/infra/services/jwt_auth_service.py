from datetime import datetime, timezone
from jose import JWTError, jwt
import bcrypt
from app.auth.domain.value_objects.token_claims import TokenClaims
from app.auth.application.ports.auth_service import AuthService
from app.auth.config import (
    SECRET_KEY,
    ALGORITHM
)

class JwtAuthService(AuthService):
    def create_access_token(self, claims: TokenClaims) -> str:
        """Gera um token JWT com tempo de expiração."""
        to_encode = dict(claims)
        
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Compara uma senha em texto plano com o hash do banco."""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

    def get_password_hash(self, password: str) -> str:
        """Gera um hash seguro para armazenar no banco."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def decode_token(self, token: str) -> TokenClaims | None:
        """Valida e extrai os dados do token JWT."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            sub = payload.get("sub")
            if not sub or not isinstance(sub, str):
                return None
            
            timestamp = payload.get("exp")
            exp = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None
            if not exp:
                return None
        
            # Fazemos o cast para garantir ao Pylance que o retorno segue o contrato
            return TokenClaims(
                sub=sub,
                full_name=payload.get("full_name", ""),
                role=payload.get("role", ""),
                sector_code=payload.get("sector_code", ""),
                must_change_password=payload.get("must_change_password", False),
                exp=exp,
            )
        except JWTError:
            return None
