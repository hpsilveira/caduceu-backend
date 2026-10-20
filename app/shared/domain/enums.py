from enum import Enum

# =========================================================================
# AUTH ENUMS
# =========================================================================
class UserRole(str, Enum):
    READ = "read"       # Visualizador (ex: Direção, Auditoria)
    WRITE = "write"     # Operador (ex: Setor de Compras, Almoxarifado)
    ADMIN = "admin"     # Gestor (ex: Coordenador de TI/SESAP, Administrador do Setor)

# =========================================================================
# PCA DOMAIN ENUMS
# =========================================================================

class PlanStatus(Enum):
    ELABORATION = 1
    ANALYSIS = 2
    APPROVAL = 3
    REVISION = 4
    COMPLETION = 5
    CANCELLATION = 99

class PriorityLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class ItemPhase(Enum):
    PLANNING = 1
    INSTRUCTION = 2
    PROCUREMENT = 3
    CONTRACTED = 4
    CANCELLED = 5

# =========================================================================
# ENUMS SPECIFIC TO PUBLIC MANAGEMENT / HEALTH
# =========================================================================

class MovementType(str, Enum):
    INFLOW = "Inflow"
    OUTFLOW = "Outflow"
    TRANSFER = "Transfer"

class LocationTag(str, Enum):
    ALMOXARIFADO_GERAL = "Almoxarifado Geral"
    FARMACIA_HOSPITALAR = "Farmácia Hospitalar"
    REDE_DE_FRIOS = "Rede de Frios (Vacinas/Imunobiológicos)"
    PRODUTO_CONTROLADO = "Medicamento Controlado"

class StateCode(str, Enum):
    RN = "Rio Grande do Norte"
    CE = "Ceará"
    PB = "Paraíba"
    PE = "Pernambuco"
