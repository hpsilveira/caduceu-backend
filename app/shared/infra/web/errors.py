import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.shared.domain.exceptions import (
    DomainException,
    InvalidValueException,
    BusinessRuleException,
    EntityNotFoundException
)

# Configuração básica de logging estruturado para o stdout/stderr (capturado pelo Render)
logger = logging.getLogger("caduceu.infra")

def configure_global_exception_handlers(app: FastAPI) -> None:
    """
    Registra interceptadores globais agnósticos a módulos para capturar exceções 
    de domínio e aplicar as respostas HTTP corretas em conformidade com o CQRS.
    """

    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_handler(
            request: Request,
            exc: EntityNotFoundException
        ) -> JSONResponse:
        """Captura a ausência física de registros (Usuários, ARPs, etc.)."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)}
        )

    @app.exception_handler(BusinessRuleException)
    async def business_rule_handler(
            request: Request,
            exc: BusinessRuleException
        ) -> JSONResponse:
        """Captura violações de processos, como estouros de cota, saldo ou regras de vigência."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exc)}
        )

    @app.exception_handler(InvalidValueException)
    async def invalid_value_handler(
            request: Request,
            exc: InvalidValueException
        ) -> JSONResponse:
        """Captura falhas estruturais na validação interna de Value Objects (CEP, Money, Telefone)."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )

    @app.exception_handler(DomainException)
    async def generic_domain_handler(
            request: Request,
            exc: DomainException
        ) -> JSONResponse:
        """Garante que qualquer nova exceção que herde da raiz do domínio responda como erro de negócio."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exc)}
        )

    @app.exception_handler(Exception)
    async def generic_system_handler(
            request: Request,
            exc: Exception
        ) -> JSONResponse:
        """
        Fallback de segurança para erros inesperados de infraestrutura (banco offline, falha de rede).
        Registra a stack de erro detalhada no servidor e oculta informações do cliente.
        """
        # Captura o método e a URL da requisição que falhou para dar contexto ao log
        logger.error(
            f"Falha interna crítica na rota {request.method} {request.url.path}: {str(exc)}", 
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Ocorreu um erro interno inesperado no servidor."}
        )
