from decimal import Decimal
from uuid import UUID

from app.shared.domain.exceptions import EntityNotFoundException
from app.shared.domain.value_objects.shared_vo import Money
from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.supplies.application.commands.dtos import AddArpItemCommand

# =========================================================================
# THE COMMAND HANDLER
# =========================================================================
class AddArpItemCommandHandler:
    def __init__(self, repository: ArpRepository):
        self._repository = repository

    def handle(self, command: AddArpItemCommand) -> UUID:
        """Adiciona um item a uma Ata existente protegendo as regras de negócio."""
        
        # 0. Verfica se o item existe no Catálogo oficial da COADI
        if not self._repository.exists_in_catalog(
            command.item_code,
            command.sector_id
        ):
            raise EntityNotFoundException(f"Código {command.item_code} não localizado no catálogo oficial da COADI.")
    
        # 1. Recupera o Agregado completo do banco por ID
        arp = self._repository.find_arp_by_id(command.arp_id)

        if not arp:
            raise EntityNotFoundException(f"Ata de Registro de Preços não localizada.")

        arp.validate_ownership(user_sector_id=command.sector_id)

        # 2. Cria a entidade interna do Item usando a Factory rica do Domínio
        item = ArpItem.create(
            item_code=command.item_code,
            description=command.description,
            total_quantity_approved=command.total_quantity_approved,
            unit_price=Money(amount=Decimal(command.unit_price))
        )

        # 3. Adiciona as cotas iniciais (se enviadas)
        for quota_data in command.initial_quotas:
            new_quota = UnitQuota.create(
                unit_id=quota_data.unit_id,
                total_allocated=quota_data.total_allocated
            )
            item.add_quota_unit(new_quota)

        # 4. Executa o comportamento na Raiz do Agregado (valida duplicidade de código)
        arp.add_item(item)

        # 5. Salva a alteração (O repositório cuidará de inserir apenas o novo item e cotas)
        self._repository.save_item_addition(arp.id, item)

        return item.id
