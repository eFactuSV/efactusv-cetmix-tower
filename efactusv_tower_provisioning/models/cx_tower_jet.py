# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    provisioning_request_id = fields.Many2one(
        "cx.tower.provisioning.request",
        string="Provisioning Request",
        index=True,
        tracking=True,
        ondelete="restrict",
    )

    def _finalize_transition(self, failed=False):
        result = super()._finalize_transition(failed=failed)
        for jet in self:
            request = jet.provisioning_request_id
            if request.state not in ("queued", "provisioning"):
                continue
            if failed:
                request._mark_failed(_("Tower reported a failed lifecycle transition."))
            elif not jet.target_state_id:
                request._mark_provisioned(url=jet.url or request.url)
        return result


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    def _allowed_jet_fields(self):
        return super()._allowed_jet_fields() + ["provisioning_request_id"]
