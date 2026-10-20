from uuid import UUID
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.supplies.application.commands.dtos import AddUnitQuotaCommand
from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.shared.domain.exceptions import EntityNotFoundException

# =========================================================================
# THE COMMAND HANDLER
# =========================================================================
class AddUnitQuotaCommandHandler:
    def __init__(self, repository: ArpRepository):
        self._repository = repository

    def handle(self, command: AddUnitQuotaCommand) -> UUID:
        """Ajusta o teto da cota de uma unidade protegendo as invariantes do Agregado."""
        
        # 0. Verfica se a unidade existe
        if not self._repository.exists_management_unit(command.unit_id):
            raise EntityNotFoundException(f"Unidade {command.unit_id} não localizada.")
    
        # 1. Recupera o Agregado completo (com itens e cotas) para garantir consistência
        arp = self._repository.find_arp_by_id(command.arp_id)
        if not arp:
            raise EntityNotFoundException("Ata de Registro de Preços não localizada.")

        arp.validate_ownership(user_sector_id=command.sector_id)

        # 2. Localiza o item específico dentro do Agregado
        target_item = next((i for i in arp.items if i.item_code == command.item_code), None)
        if not target_item:
            raise EntityNotFoundException(f"Item com código {command.item_code} não pertence a esta ARP.")

        # cria a cota
        quota = UnitQuota.create(
            unit_id=command.unit_id,
            total_allocated=command.total,
        )

        # 4. Executa as validações e o ajuste delegando para a lógica rica do Domínio
        # (Lançará BusinessRuleException se estourar o total homologado do item
        # ou se o novo total for menor do que a unidade gestora já consumiu)
        target_item.add_quota_unit(quota)

        # 5. Persiste unicamente o item modificado no banco de dados
        if quota:
            self._repository.save_quota(target_item.id, quota)

        return quota.id
