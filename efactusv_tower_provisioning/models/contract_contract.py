# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ContractContract(models.Model):
    _inherit = "contract.contract"

    tower_provisioning_profile_id = fields.Many2one(
        "cx.tower.provisioning.profile", string="Provisioning Profile", tracking=True
    )
    tower_provisioning_request_ids = fields.One2many(
        "cx.tower.provisioning.request", "contract_id", string="Provisioning Requests"
    )
    tower_provisioning_request_count = fields.Integer(
        compute="_compute_tower_provisioning_request_count", string="Provisioning"
    )

    def _compute_tower_provisioning_request_count(self):
        grouped = (
            self.env["cx.tower.provisioning.request"]
            .sudo()
            ._read_group(
                [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
            )
        )
        counts = {contract.id: count for contract, count in grouped}
        for contract in self:
            contract.tower_provisioning_request_count = counts.get(contract.id, 0)

    def _tower_create_provisioning_request(self, invoice):
        self.ensure_one()
        if not self.tower_provisioning_profile_id or self.is_terminated:
            return self.env["cx.tower.provisioning.request"]
        Request = self.env["cx.tower.provisioning.request"].sudo()
        existing = Request.search(
            [("contract_id", "=", self.id), ("service_key", "=", "primary")], limit=1
        )
        if existing:
            return existing
        try:
            with self.env.cr.savepoint():
                request = Request.create(
                    {
                        "contract_id": self.id,
                        "source_invoice_id": invoice.id,
                        "profile_id": self.tower_provisioning_profile_id.id,
                    }
                )
        except IntegrityError:
            request = Request.search(
                [("contract_id", "=", self.id), ("service_key", "=", "primary")],
                limit=1,
            )
        request._enqueue()
        return request

    def action_create_tower_jet(self):
        self.ensure_one()
        if self.tower_provisioning_profile_id:
            raise ValidationError(
                _(
                    "Use a paid invoice or Retry on the provisioning request for "
                    "this contract."
                )
            )
        return super().action_create_tower_jet()

    def action_view_tower_provisioning_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "efactusv_tower_provisioning.action_tower_provisioning_request"
        )
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {"default_contract_id": self.id}
        if self.tower_provisioning_request_count == 1:
            action.update(
                {"view_mode": "form", "res_id": self.tower_provisioning_request_ids.id}
            )
        return action
