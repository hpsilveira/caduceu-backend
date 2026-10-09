from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from uuid import UUID

# =========================================================================
# SCHEMAS DE SUPORTE INTERNO (DECLARADOS ANTES PARA EVITAR NAMEERROR)
# =========================================================================
class UnitQuotaSchema(BaseModel):
    unit_id: int = Field(..., gt=0)
    total_allocated: Decimal = Field(..., gt=0)


class ArpItemSchema(BaseModel):
    item_code: str = Field(...)
    description: str = Field(..., min_length=3)
    total_quantity_approved: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    quotas: list[UnitQuotaSchema] = Field(default_factory=lambda: list[UnitQuotaSchema]())


# =========================================================================
# SCHEMAS DE ENTRADA WEB (PYDANTIC V2)
# =========================================================================
class CreateArpRequestSchema(BaseModel):
    arp_number: str = Field(..., json_schema_extra={"example": "06/2026-SESAP"})
    process_sei: str = Field(..., json_schema_extra={"example": "00610022.00444/2026-11"})
    expiration_date: date = Field(...)
    items: list[ArpItemSchema] = Field(default_factory=lambda: list[ArpItemSchema]())


class AddArpItemRequestSchema(BaseModel):
    item_code: str = Field(...)
    description: str = Field(...)
    total_quantity_approved: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    quotas: list[UnitQuotaSchema] = Field(default_factory=lambda: list[UnitQuotaSchema]())


class AddUnitQuotaRequestSchema(BaseModel):
    unit_id: int = Field(..., gt=0)
    total_allocated: Decimal = Field(..., gt=0)


class AdjustUnitQuotaRequestSchema(BaseModel):
    new_total: Decimal = Field(..., gt=0)


class RequestSupplyRequestSchema(BaseModel):
    """Schema de entrada: Estrutura exata do JSON enviado pelo formulário do React."""
    arp_number: str = Field(..., description="Número de registro da ARP")
    item_code: str = Field(..., description="Código único do insumo/medicamento")
    quantity: Decimal = Field(..., gt=0, description="Quantidade a ser debitada")
    unit_id: int = Field(..., gt=0, description="ID da unidade gestora requisitante")
    process_sei_request: str = Field(..., min_length=5, description="Processo SEI do pedido")


class CreateResponseSchema(BaseModel):
    """Schema de saída: Resposta ideal seguindo as boas práticas de CQRS (Apenas o ID)."""
    id: UUID
    message: str = Field(default="")