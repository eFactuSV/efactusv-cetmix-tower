# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    contract_id = fields.Many2one(
        comodel_name="contract.contract",
        string="Contract",
        index=True,
        tracking=True,
        help="Customer contract this instance is billed with",
    )

    def action_open_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contract.contract",
            "res_id": self.contract_id.id,
            "view_mode": "form",
            "target": "current",
        }
