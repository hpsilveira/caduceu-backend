from uuid import UUID
from app.auth.application.ports.user_repository import UserRepository
from app.auth.application.ports.auth_service import AuthService
from app.auth.application.commands.dtos import CreateUserCommand
from app.auth.domain.entities.user import User
from app.shared.domain.exceptions import (
    BusinessRuleException,
    EntityNotFoundException
)

class CreateUserCommandHandler:
    """
    Handler responsável por orquestrar a criação de novos usuários.
    Valida duplicidade, hasheada a senha e persiste com flag de troca obrigatória.
    """
    
    def __init__(self, repository: UserRepository, auth_service: AuthService):
        self._repository = repository
        self._auth_service = auth_service
    
    def handle(self, command: CreateUserCommand, current_user: User) -> UUID:
        """
        Executa o fluxo de criação de usuário.
        """
        # 1. REGRA: ADMIN comum só cria para o próprio setor
        # Apenas GLOBAL_ADMIN pode criar para qualquer setor
        if not current_user.is_global_admin:
            if command.sector_code != current_user.sector_code:
                raise BusinessRuleException(
                    "Você só pode criar usuários para o seu setor operacional."
                )

        # 2. Valida se o setor existe
        # Resolve code → FK (valida existência do setor)
        sector_id = self._repository.find_sector_id_by_code(command.sector_code)
        if not sector_id:
            raise EntityNotFoundException(
                f"Setor '{command.sector_code}' não localizado."
            )

        # 3. Validação de duplicidade
        existing_user = self._repository.find_by_username(command.username)
        if existing_user:
            raise BusinessRuleException(
                f"O username '{command.username}' já está em uso no sistema."
            )
        
        # 4. Hashear a senha (mesmo que seja a padrão)
        hashed_password = self._auth_service.get_password_hash(command.password)
        
        # 5. Criar entidade de domínio com flag de troca obrigatória
        new_user = User.create(
            username=command.username,
            full_name=command.full_name,
            hashed_password=hashed_password,
            sector_id=sector_id,
            sector_code=command.sector_code,
            role=command.role
        )
        
        # 6. Forçar must_change_password = True (segurança de governança)
        # O User.create já define como True por padrão, mas garantimos explicitamente
        object.__setattr__(new_user, '_must_change_password', True)
        
        # 7. Persistir no banco
        self._repository.save(new_user)
        
        return new_user.id