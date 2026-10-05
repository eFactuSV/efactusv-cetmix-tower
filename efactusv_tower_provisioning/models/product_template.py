# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tower_provisioning_profile_id = fields.Many2one(
        "cx.tower.provisioning.profile",
        string="Tower Provisioning Profile",
        company_dependent=True,
        domain="[('company_id', '=', company_id)]",
        help="Service infrastructure created after the first invoice is fully paid.",
    )

    @api.constrains("tower_provisioning_profile_id", "is_contract", "type")
    def _check_tower_provisioning_profile(self):
        for product in self:
            if product.tower_provisioning_profile_id and (
                not product.is_contract or product.type != "service"
            ):
                raise ValidationError(
                    self.env._(
                        "Tower provisioning is only available for contract services."
                    )
                )
