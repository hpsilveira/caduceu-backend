import os
from typing import Any, Generator
from dotenv import load_dotenv
from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry
from app.supplies.infra.database.models import Base

load_dotenv()

# 1. Recupera a URL do banco das variáveis de ambiente.
# No Render o SQLite default é uma armadilha: o disco é efêmero e cada deploy apagaria tudo.
# Resolve na chamada, nunca no import: é o que deixa a suíte de teste importar este módulo sem
# depender de `.env` (e sem o `RENDER=true` do ambiente derrubar o `pytest` inteiro).
def resolve_database_url() -> str:
    if url := os.getenv("DATABASE_URL"):
        return url
    if os.getenv("RENDER", "").lower() == "true":
        raise RuntimeError(
            "DATABASE_URL é obrigatório no Render: crie o PostgreSQL gerenciado e copie a "
            "Internal Database URL nas variáveis de ambiente do serviço."
        )
    return "sqlite:///./caduceu.db"  # apenas desenvolvimento local

# 2. Fábricas de engine/sessão.
# Nada aqui é criado no import: a engine vive no app (app.state), então subir o módulo não abre
# conexão nem exige DATABASE_URL de produção — é isto que permite apontar a aplicação inteira para
# um banco de teste sem reatribuir nome nenhum em outro módulo.
def build_engine(database_url: str) -> Engine:
    is_sqlite = database_url.startswith("sqlite")

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

    engine = create_engine(database_url, **engine_kwargs)

    if is_sqlite:
        # O SQLite ignora FOREIGN KEY por padrão e o pragma é por conexão. Sem isto as FKs do schema
        # (arp_item.item_code, unit_quota.unit_id) seriam decorativas no dev — no Postgres elas já
        # são fiscalizadas pelo servidor e o bloco não roda.
        @event.listens_for(engine, "connect")
        def _enforce_sqlite_foreign_keys(
            dbapi_connection: DBAPIConnection, _connection_record: ConnectionPoolEntry
        ) -> None:
            # Sem chamadas no código: o pool dispara esta função (posicional) a cada conexão
            # física nova, em _ConnectionRecord.__connect() -> pool.dispatch.connect.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def default_session_factory() -> sessionmaker[Session]:
    """A fábrica do ambiente: engine de `resolve_database_url()`. É o que `create_app()` usa quando nada é injetado."""
    return build_session_factory(build_engine(resolve_database_url()))


# 3. Inicializador do Banco Automático (Para uso no Startup do FastAPI e no script de seed)
def init_db(bind: Engine | Connection) -> None:
    """
    Varre os modelos mapeados pelo SQLAlchemy e gera o banco 
    e as tabelas locais automaticamente se elas não existirem.
    """
    Base.metadata.create_all(bind=bind)


# 4. Dependência de sessão para os adaptadores.
# A fábrica vem do app, não de um global do módulo: é o único ponto por onde uma requisição chega
# ao banco, e por isso serve os dois contextos (`supplies` e `auth`).
def get_db_session(request: Request) -> Generator[Session, None, None]:
    """
    Cria uma nova sessão e garante o fechamento seguro dela,
    mesmo que ocorra um erro durante a execução do código.
    """
    session = request.app.state.session_factory()
    try:
        yield session  # Entrega a sessão pronta para uso
    except Exception:
        session.rollback()  # Desfaz alterações se houver erro no processo
        raise
    finally:
        session.close()  # Garante a conexão de volta ao pool (Obrigatório!)
