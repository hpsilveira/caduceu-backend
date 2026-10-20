from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.shared.domain.enums import UserRole
from app.auth.domain.entities.user import User
from app.auth.application.commands.login_handler import LoginHandler
from app.auth.application.commands.create_user_handler import (
    CreateUserCommandHandler
)
from app.auth.application.commands.change_password_handler import (
    ChangePasswordHandler
)
from app.auth.application.queries.list_sector_handler import (
    ListSectorQueryHandler
)
from app.auth.application.ports.auth_service import AuthService
from app.auth.application.ports.query_service import QueryService
from app.auth.application.ports.user_repository import UserRepository
from app.auth.infra.services.jwt_auth_service import JwtAuthService
from app.auth.infra.database.sqlalchemy_query_service import (
    SqlAlchemyQueryService
)
from app.auth.infra.database.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository
)
from app.supplies.infra.database.config import get_db_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def get_auth_service() -> AuthService:
    return JwtAuthService()


def get_query_service(db: Session = Depends(get_db_session)) -> QueryService:
    return SqlAlchemyQueryService(db_session=db)


def get_user_repository(db: Session = Depends(get_db_session)):
    return SqlAlchemyUserRepository(db_session=db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """
    Dependência que valida o token e retorna o usuário logado.
    Qualquer erro aqui interrompe a requisição com 401 Unauthorized.
    """
    # 1. Usa o novo decode_token que retorna TokenClaims tipado
    claims = auth_service.decode_token(token)
    
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso negado: Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Busca o usuário no banco usando o 'sub' (username) das claims
    user = user_repo.find_by_username(claims["sub"])
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Usuário não localizado no sistema."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Este usuário está inativo."
        )
    
    return user


def get_current_writer(
    current_user: User = Depends(get_current_user)
) -> User:
    """Autorização de escrita: o papel `READ` é somente leitura em qualquer comando.

    É dependência e não checagem dentro de cada rota porque a regra é a mesma para todas e o preço
    de esquecer um dos comandos é o operador-leitor mutar saldo de ata. O `get_current_user` roda
    uma vez por requisição (o cache de sub-dependência do FastAPI garante), então não há custo em
    separar autenticação de autorização.
    """
    if current_user.role == UserRole.READ:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este usuário é somente leitura: comandos exigem papel de escrita.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def get_login_handler(
        user_repo: UserRepository = Depends(get_user_repository),
        auth_service: AuthService = Depends(get_auth_service)
    ) -> LoginHandler:
    return LoginHandler(repository=user_repo, auth_service=auth_service)


def get_create_user_handler(
    user_repository: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service)
) -> CreateUserCommandHandler:
    """Fábrica de dependências para o Caso de Uso de criação de usuário."""
    return CreateUserCommandHandler(
        repository=user_repository,
        auth_service=auth_service
    )


def get_change_password_handler(
        user_repository: UserRepository = Depends(get_user_repository),
        auth_service: AuthService = Depends(get_auth_service)
) -> ChangePasswordHandler:
    """
    Fábrica de dependências para o Caso de Uso de alteração de senha.
    Abolido o sufixo 'handler' do nome da função conforme seu novo padrão.
    """
    
    return ChangePasswordHandler(
        repository=user_repository, 
        auth_service=auth_service
    )


def get_list_sector_handler(
    query_service: QueryService = Depends(get_query_service)
) -> ListSectorQueryHandler:
    """Fábrica de dependências para o Caso de Uso de listagem de setores."""
    return ListSectorQueryHandler(
        query_service=query_service
    )