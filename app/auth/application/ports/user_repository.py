from abc import ABC, abstractmethod
from typing import Optional
from app.auth.domain.entities.user import User

class UserRepository(ABC):
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        pass

    @abstractmethod
    def save(self, user: User) -> None:
        pass

    @abstractmethod
    def update_password(
            self,
            username: str,
            hashed_password: str,
            must_change_password: bool
        ) -> None:
        """
        Atualiza fisicamente a senha de um usuário e redefine 
        o status da trava de primeiro acesso.
        """
        pass

    @abstractmethod
    def find_sector_id_by_code(self, code: str) -> Optional[int]:
        pass