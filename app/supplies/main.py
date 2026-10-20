# app/supplies/main.py
import os
from collections.abc import AsyncGenerator, Callable
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from app.shared.infra.web.errors import configure_global_exception_handlers
from app.supplies.infra.database.config import default_session_factory, init_db
from app.supplies.infra.web.routes import router as supply_router
from app.auth.infra.web.routers import router as auth_router
from app.supplies.infra.database.seed import seed


def _catalog_is_empty(session_factory: sessionmaker[Session]) -> bool:
    with session_factory() as session:
        return not (session.execute(text("SELECT COUNT(*) FROM dim_catalog_item")).scalar() or 0)


def bootstrap_database(session_factory: sessionmaker[Session]) -> None:
    """Gera o schema e popula o banco na primeira execução do servidor."""
    # 1. Cria o arquivo SQLite (ou o schema no Postgres) e as tabelas
    with session_factory() as session:
        init_db(session.get_bind())
    print("📋 Banco de dados inicializado e tabelas geradas!")

    # 2. Trava inteligente: Verifica se o banco já foi populado
    if _catalog_is_empty(session_factory):
        seed(session_factory)  # Só roda se o banco estiver 100% virgem
    else:
        print("📋 Banco de dados já contém dados. Ignorando Seed.")


def _cors_allow_origins() -> list[str]:
    # Configuração de segurança de rede (CORS) para o React + Vite.
    # Em produção CADUCEU_CORS_ORIGINS (csv) é obrigatório no Render; o wildcard fica só para dev local.
    _cors_origins = [
        origin.strip()
        for origin in os.getenv("CADUCEU_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return _cors_origins or ["*"]


def create_app(
        *,
        session_factory: sessionmaker[Session] | None = None,
        bootstrap: Callable[[sessionmaker[Session]], None] | None = bootstrap_database
    ) -> FastAPI:
    """Composition root: monta o FastAPI e injeta o que toca o mundo externo.

    `session_factory` é a única porta de entrada da aplicação ao banco — o default é a engine do
    `DATABASE_URL` do ambiente, e um teste passa a sua para não encostar no `caduceu.db`. O mesmo
    vale para `bootstrap`: `bootstrap=None` sobe as rotas sem criar schema nem rodar seed.
    """
    factory = session_factory or default_session_factory()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # Código executado ao desligar o servidor (se necessário)
        if bootstrap is not None:
            bootstrap(app.state.session_factory)
        yield

    app = FastAPI(lifespan=lifespan,
                  title="SAS/COADI Supplies Microservice - SESAP-RN",
                  description="Plataforma Operacional de Controle de \
                Saldos de ARPs e Débitos de Cotas.")

    app.state.session_factory = factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    configure_global_exception_handlers(app)  # Configura interceptadores globais de exceção
    # Acopla o módulo de Suprimentos ao servidor web
    app.include_router(supply_router)
    app.include_router(auth_router)

    @app.get("/health", tags=["Infra"])
    def health() -> dict[str, str]:
        """Liveness para o health check do Render. Não toca o banco de propósito:
        o check precisa ser barato e continuar respondendo em picos de latência do banco."""
        return {"status": "ok"}

    return app


app = create_app()
