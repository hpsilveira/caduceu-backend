# =========================================================================
# DOMAIN EXCEPTIONS
# =========================================================================

class DomainException(Exception):
    """Exceção base para todas as violações de regras do domínio."""
    pass

class InvalidValueException(DomainException):
    """Lançada quando um Value Object recebe dados inválidos."""
    pass

class BusinessRuleException(DomainException):
    """Lançada quando uma operação matemática ou regra de negócio falha."""
    pass

class EntityNotFoundException(DomainException):
    """Lançada quando uma entidade não é encontrada no repositório."""
    pass