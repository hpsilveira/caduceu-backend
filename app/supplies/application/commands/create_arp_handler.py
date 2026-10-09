from decimal import Decimal
from datetime import date
from uuid import UUID

from app.supplies.domain.entities.price_registration_agreement import (
    PriceRegistrationAgreement
)
from app.supplies.domain.entities.arp_item import ArpItem
from app.supplies.domain.entities.unit_quota import UnitQuota
from app.supplies.application.commands.dtos import CreateArpCommand
from app.supplies.application.ports.database.arp_repository import ArpRepository

from app.shared.domain.value_objects.shared_vo import Money
from app.shared.domain.exceptions import (
    BusinessRuleException, EntityNotFoundException
)

# =========================================================================
# THE COMMAND HANDLER (Orquestrador do fluxo de criação)
# =========================================================================
class CreateArpCommandHandler:
    def __init__(self, repository: ArpRepository):
        self._repository = repository

    def handle(
            self,
            command: CreateArpCommand,
            current_date: date | None = None
        ) -> UUID:
        """Instancia o Agregado complexo da ARP e persiste transacionalmente."""
        today = current_date or date.today()

        # 1. Cria a Raiz do Agregado usando a Factory do Domínio
        # (Lançará erro de negócio se a data de expiração for no passado)
        arp = PriceRegistrationAgreement.create(
            arp_number=command.arp_number,
            process_sei=command.process_sei,
            expiration_date=command.expiration_date,
            owner_sector_id=command.owner_sector_id,
            current_date=today
        )

        # 2. Constrói e aninha os itens e suas respectivas cotas
        for item_data in command.items:
            # Cria a entidade interna do Item via Factory
            if not self._repository.exists_in_catalog(
                item_data.item_code,
                command.owner_sector_id
            ):
                raise EntityNotFoundException(f"Código {item_data.item_code} não localizado no catálogo oficial da COADI.")
    
            item = ArpItem.create(
                item_code=item_data.item_code,
                description=item_data.description,
                total_quantity_approved=item_data.total_quantity_approved,
                unit_price=Money(amount=Decimal(str(item_data.unit_price)))
            )

            # Cria e vincula as cotas das unidades ao item
            total_quotas_sum = Decimal("0.00")
            for quota_data in item_data.quotas:
                if not self._repository.exists_management_unit(quota_data.unit_id):
                    raise EntityNotFoundException(f"Unidade {quota_data.unit_id} não localizada no sistema.")

                quota = UnitQuota.create(
                    unit_id=quota_data.unit_id,
                    total_allocated=quota_data.total_allocated
                )
                item.add_quota_unit(quota)
                total_quotas_sum += quota_data.total_allocated

            # Invariante de Negócio: A soma das cotas das unidades não pode exceder o total do item
            if total_quotas_sum > item.total_quantity_approved:
                raise BusinessRuleException(
                    f"A soma das cotas distribuídas ({total_quotas_sum}) excede "
                    f"a quantidade total aprovada do item {item.item_code} ({item.total_quantity_approved})."
                )

            # Adiciona o item configurado na Raiz do Agregado (Ata)
            arp.add_item(item)

        # 3. Salva o Agregado completo
        self._repository.save_new_arp(arp)

        return arp.id
