from datetime import date
from uuid import UUID

from app.shared.domain.exceptions import EntityNotFoundException
from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.supplies.domain.entities.supply_order import SupplyOrder
from app.supplies.application.commands.dtos import RequestSupplyCommand

# =========================================================================
# THE COMMAND HANDLER (Caso de Uso de Escrita)
# =========================================================================
class RequestSupplyCommandHandler:
    """
    Handler responsável por orquestrar a execução do RequestSupplyCommand.
    Focado unicamente em regras de negócio de mutação de estado.
    """
    
    def __init__(self, repository: ArpRepository):
        # Inversão de dependência acoplada à nossa nova porta específica de escrita
        self._repository = repository

    def handle(
            self,
            command: RequestSupplyCommand,
            current_date: date | None = None
        ) -> UUID:
        """
        Executa o fluxo transacional de débito de saldo.
        Retorna apenas o ID da Ordem gerada (Seguindo o CQRS estrito: Commands alteram estado,
        mas retornam o mínimo possível de dados de leitura - geralmente apenas o ID do recurso).
        """
        # 1. Resolve a data atual (mantendo flexibilidade para testes unitários)
        today = current_date or date.today()

        # 2. Recupera o Agregado através da porta específica de escrita
        arp = self._repository.find_by_arp_number(command.arp_number)

        if not arp:
            raise EntityNotFoundException(
                f"Ata de Registro de Preços nº {command.arp_number} não foi localizada."
            )

        arp.validate_ownership(user_sector_id=command.sector_id)

        # 3. Executa o comportamento rico e protegido do domínio injetando a data
        arp.request_supply(
            item_code=command.item_code,
            quantity=command.quantity,
            unit_id=command.unit_id,
            current_date=today
        )

        # 4. Instancia a nova Ordem através do Factory Method do Domínio
        order = SupplyOrder.create(
            arp_id=arp.id,
            item_code=command.item_code,
            unit_id=command.unit_id,
            quantity_requested=command.quantity,
            process_sei_request=command.process_sei_request
        )

        # 5. Persiste as alterações atomicamente de forma transacional
        self._repository.save_supply_order(arp=arp, order=order)

        # 6. CQRS: Retorna o identificador do novo recurso criado
        return order.id