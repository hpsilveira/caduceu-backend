from sqlalchemy import update
from sqlalchemy.orm import Session
from typing import Optional
from app.auth.domain.entities.user import User
from app.shared.domain.enums import UserRole
from app.auth.application.ports.user_repository import UserRepository
from app.supplies.infra.database.models import UserModel, DimSectorModel

class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, db_session: Session):
        self._session = db_session

    def find_by_username(self, username: str) -> Optional[User]:
        
        result = (
            self._session.query(UserModel, DimSectorModel.code)
            .join(DimSectorModel, UserModel.sector_id == DimSectorModel.id)
            .filter(UserModel.username == username)
            .first()
        )
        if not result:
            return None

        user_model, sector_code = result
        # Reconstrói a entidade de domínioUser
        return User(
            id=user_model.id,
            username=user_model.username,
            full_name=user_model.full_name,
            role=UserRole(user_model.role),
            sector_id=user_model.sector_id,
            sector_code=sector_code,
            hashed_password=user_model.hashed_password,
            must_change_password=user_model.must_change_password,
            is_active=user_model.is_active
        )

    def save(self, user: User) -> None:
        user_model = UserModel(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            role=user.role,
            sector_id=user.sector_id,
            must_change_password=user.must_change_password,
            is_active=user.is_active
        )
        self._session.add(user_model)
        self._session.commit()

    def update_password(
            self,
            username: str,
            hashed_password: str,
            must_change_password: bool
        ) -> None:
        """
        Executa a mutação física na tabela 'users' aplicando o novo hash 
        e atualizando a flag de controle de governança.
        """
        # 1. Monta o comando de update de forma explícita e otimizada
        try:
            stmt = (
                update(UserModel)
                .where(UserModel.username == username)
                .values(
                    hashed_password=hashed_password,
                    must_change_password=must_change_password
                )
            )
            
            self._session.execute(stmt)

            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def find_sector_id_by_code(self, code: str) -> Optional[int]:
        return (
            self._session.query(DimSectorModel.id)
            .filter(DimSectorModel.code == code, DimSectorModel.is_active.is_(True))
            .scalar()
        )