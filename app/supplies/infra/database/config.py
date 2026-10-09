import os
from typing import Any, Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.supplies.infra.database.models import Base

load_dotenv()

# 1. Recupera a URL do banco das variáveis de ambiente (Fallback para SQLite local se não houver Postgres)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./caduceu.db")

# 2. Configura o Engine dinamicamente com Pool apenas se não for SQLite
is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs: dict[str, Any] = {
    "echo": False  # Mude para True para ver os SQLs gerados no terminal
}

if is_sqlite:
    # Parâmetro obrigatório para o SQLite funcionar corretamente com múltiplas threads no FastAPI
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Parâmetros de pool ideais e essenciais para ambiente de produção com Postgres
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

# 3. Cria a Fábrica de Sessões
SessionFactory = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# 4. Inicializador do Banco Automático (Para uso no Startup do FastAPI)
def init_db() -> None:
    """
    Varre os modelos mapeados pelo SQLAlchemy e gera o banco 
    e as tabelas locais automaticamente se elas não existirem.
    """
    Base.metadata.create_all(bind=engine)

# 5. Gerenciador de Contexto / Dependência para os Adaptadores
def get_db_session() -> Generator[Session, None, None]:
    """
    Cria uma nova sessão e garante o fechamento seguro dela,
    mesmo que ocorra um erro durante a execução do código.
    """
    session = SessionFactory()
    try:
        yield session  # Entrega a sessão pronta para uso
    except Exception:
        session.rollback()  # Desfaz alterações se houver erro no processo
        raise
    finally:
        session.close()  # Garante o fechamento da conexão (Obrigatório!)
