from app.supplies.application.ports.database.arp_repository import ArpRepository
from app.supplies.application.commands.dtos import AdjustUnitQuotaCommand
from app.shared.domain.exceptions import EntityNotFoundException

# =========================================================================
# THE COMMAND HANDLER
# =========================================================================
class AdjustUnitQuotaCommandHandler:
    def __init__(self, repository: ArpRepository):
        self._repository = repository

    def handle(self, command: AdjustUnitQuotaCommand) -> None:
        """Ajusta o teto da cota de uma unidade protegendo as invariantes do Agregado."""
        
        # 1. Recupera o Agregado completo (com itens e cotas) para garantir consistência
        arp = self._repository.find_arp_by_id(command.arp_id)
        if not arp:
            raise EntityNotFoundException("Ata de Registro de Preços não localizada.")

        arp.validate_ownership(user_sector_id=command.sector_id)

        # 2. Localiza o item específico dentro do Agregado
        target_item = next((i for i in arp.items if i.item_code == command.item_code), None)
        if not target_item:
            raise EntityNotFoundException(f"Item com código {command.item_code} não pertence a esta ARP.")

        # 3. Executa as validações e o ajuste delegando para a lógica rica do Domínio
        # (Lançará BusinessRuleException se estourar o total homologado do item
        # ou se o novo total for menor do que a unidade gestora já consumiu)
        target_item.adjust_quota_allocation(
            unit_id=command.unit_id,
            new_total=command.new_total
        )

        # 4. Localiza a cota alterada para persistência cirúrgica
        modified_quota = next((q for q in target_item.quota_units if q.unit_id == command.unit_id), None)
        
        # 5. Persiste unicamente a cota modificada no banco de dados
        if modified_quota:
            self._repository.save_quota_adjustment(modified_quota)

        return
