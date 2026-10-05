# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    state_on_contract_terminate_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="State on Contract Termination",
        help="Jets linked to a contract are brought to this state "
        "when the contract is terminated. "
        "Leave empty to keep the jet running.",
    )
    state_on_contract_reactivate_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="State on Contract Reactivation",
        help="Jets linked to a contract are brought to this state "
        "when the contract termination is cancelled. "
        "Leave empty to keep the jet in its current state.",
    )

    def _allowed_jet_fields(self):
        return super()._allowed_jet_fields() + ["contract_id"]
