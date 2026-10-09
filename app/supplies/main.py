# app/supplies/main.py
import os
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.supplies.errors import configure_global_exception_handlers
from app.supplies.infra.database.config import SessionFactory, init_db
from app.supplies.infra.web.routes import router as supply_router
from app.auth.infra.web.routers import router as auth_router
from app.supplies.infra.database.seed import seed

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Executa ao iniciar o servidor: cria o arquivo SQLite e as tabelas
    init_db()
    print("📋 Banco de dados SQLite local inicializado e tabelas geradas!")

    # 2. Trava inteligente: Verifica se o banco já foi populado
    session = SessionFactory()
    try:
        total_items = (
            session.execute(text("SELECT COUNT(*) FROM dim_catalog_item"))
            .scalar() or 0
        )
        if total_items == 0:
            seed()  # Só roda se o banco estiver 100% virgem
        else:
            print("📋 Banco de dados local já contém dados. Ignorando Seed.")
    finally:
        session.close()

    yield
    # Código executado ao desligar o servidor (se necessário)

app = FastAPI(lifespan=lifespan,
              title="SAS/COADI Supplies Microservice - SESAP-RN",
              description="Plataforma Operacional de Controle de \
                Saldos de ARPs e Débitos de Cotas.")
    
# Configuração de segurança de rede (CORS) para o React + Vite
# Em produção CADUCEU_CORS_ORIGINS (csv) é obrigatório no Render; o wildcard fica só para dev local.
_cors_origins = [
    origin.strip()
    for origin in os.getenv("CADUCEU_CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
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
