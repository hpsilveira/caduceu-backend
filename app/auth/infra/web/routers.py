from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.domain.entities.user import User
from app.auth.application.queries.dtos import SectorDTO
from app.supplies.infra.web.schemas import (
    CreateResponseSchema
)
from app.auth.infra.web.schemas import (
    UserChangePasswordRequestSchema,
    CreateUserRequestSchema,
)
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
from app.auth.dependencies import (
    get_current_user,
    get_login_handler,
    get_create_user_handler,
    get_change_password_handler,
    get_list_sector_handler
)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação SAS/COADI"])

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    handler: LoginHandler = Depends(get_login_handler)
):
    # O handler verifica credenciais e retorna o Token
    token = handler.handle(form_data.username, form_data.password)
    return {"access_token": token, "token_type": "bearer"}


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateResponseSchema
)
def create_user(
    payload: CreateUserRequestSchema,
    current_user: User = Depends(get_current_user),
    handler: CreateUserCommandHandler = Depends(get_create_user_handler)
):
    """
    Endpoint exclusivo para ADMIN criar novos usuários.
    Senha padrão: a123456@ (força troca no primeiro login)
    """
    # 1. Validação de permissão (apenas ADMIN)
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem criar novos usuários."
        )
    
    # 2. Senha padrão fixa (governança de segurança)
    default_password = "a123456@"
    
    # 3. Executar comando
    from app.auth.application.commands.dtos import CreateUserCommand
    command = CreateUserCommand(
        username=payload.username,
        full_name=payload.full_name,
        password=default_password,
        sector_code=payload.sector_code,
        role=payload.role
    )
    
    user_id = handler.handle(command, current_user=current_user)
    
    return CreateResponseSchema(
        id=user_id,
        message=f"Usuário '{payload.username}' criado com sucesso. Senha padrão: {default_password}"
    )


@router.post(
    "/change-password", 
    status_code=status.HTTP_200_OK, 
    response_model=CreateResponseSchema
)
def change_password(
    payload: UserChangePasswordRequestSchema,
    current_user: User = Depends(get_current_user),
    handler: ChangePasswordHandler = Depends(get_change_password_handler   ) # Injeção sem o sufixo 'handler' no nome da factory
):
    """
    Endpoint seguro para alteração obrigatória de senha no primeiro acesso.
    O username é extraído diretamente do token JWT assinado para evitar fraudes.
    """
        # Executa a linha de montagem reta do caso de uso
    handler.handle(
        username=current_user.username, 
        payload=payload
    )
        
    return CreateResponseSchema(
        id=current_user.id,
        message="Senha atualizada com sucesso. Refaça o login para validar suas credenciais."
    )
        

@router.get("/sectors", response_model=list[SectorDTO])
def list_sector(
    current_user: User = Depends(get_current_user),
    handler: ListSectorQueryHandler = Depends(get_list_sector_handler)
):
    """Lista setores ativos. ADMIN comum vê apenas o próprio."""
    return handler.handle(current_user)