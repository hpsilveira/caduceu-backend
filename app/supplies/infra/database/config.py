import os
from typing import Any, Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session
from app.supplies.infra.database.models import Base

load_dotenv()

# 1. Recupera a URL do banco das variáveis de ambiente.
# No Render o SQLite default é uma armadilha: o disco é efêmero e cada deploy apagaria tudo.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("RENDER", "").lower() == "true":
        raise RuntimeError(
            "DATABASE_URL é obrigatório no Render: crie o PostgreSQL gerenciado e copie a "
            "Internal Database URL nas variáveis de ambiente do serviço."
        )
    DATABASE_URL = "sqlite:///./caduceu.db"  # apenas desenvolvimento local

# Fixa o driver do PostgreSQL. A Internal Database URL do Render chega com o scheme cru
# `postgresql://`, e no SQLAlchemy 2.x esse scheme resolve para o driver psycopg 3 — que não
# está no requirements (o pin é psycopg2-binary). Normalizar aqui permite colar a URL exatamente
# como o painel do Render a apresenta. Mantém-se o objeto URL (não str()): str(URL) esconde a
# senha como `***`.
DATABASE_URL = make_url(DATABASE_URL)
if DATABASE_URL.drivername == "postgresql":
    DATABASE_URL = DATABASE_URL.set(drivername="postgresql+psycopg2")

# 2. Configura o Engine dinamicamente com Pool apenas se não for SQLite
is_sqlite = DATABASE_URL.drivername == "sqlite"

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
        "pool_recycle": 1800,
        # Render encerra conexões ociosas; sem pre-ping a primeira requisição após o
        # período idle recebe uma conexão morta e quebra com InterfaceError.
        "pool_pre_ping": True
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
