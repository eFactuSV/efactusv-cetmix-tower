# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_create_contract(self):
        contracts = super().action_create_contract()
        for contract in contracts:
            profiles = self.env["cx.tower.provisioning.profile"]
            products = (
                contract.contract_line_ids.sale_order_line_id.product_id.product_tmpl_id
            )
            for product in products:
                profiles |= product.with_company(
                    contract.company_id
                ).tower_provisioning_profile_id
            if len(profiles) > 1:
                raise ValidationError(
                    _(
                        "Contract %(contract)s contains services with different Tower "
                        "provisioning profiles. Split them into separate contracts.",
                        contract=contract.display_name,
                    )
                )
            if profiles:
                contract.write(
                    {
                        "tower_provisioning_profile_id": profiles.id,
                        "tower_jet_template_id": profiles.jet_template_id.id,
                        "tower_server_id": profiles.server_id.id,
                    }
                )
        return contracts
