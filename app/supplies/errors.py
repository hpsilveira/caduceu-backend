from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.shared.domain.exceptions import (
    BusinessRuleException, EntityNotFoundException
)

def configure_global_exception_handlers(app: FastAPI) -> None:
    """Registra interceptadores globais para capturar exceções de domínio."""

    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)}
        )

    @app.exception_handler(BusinessRuleException)
    async def business_rule_handler(request: Request, exc: BusinessRuleException):
        # Captura estouros de cota, saldo insuficiente, regras de validação, etc.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)}
        )

    @app.exception_handler(Exception)
    async def generic_system_handler(request: Request, exc: Exception):
        # Fallback de segurança para erros inesperados (ex: banco de dados offline)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Ocorreu um erro interno inesperado no servidor."}
        )
