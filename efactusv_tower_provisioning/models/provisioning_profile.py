# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TowerProvisioningProfile(models.Model):
    _name = "cx.tower.provisioning.profile"
    _description = "Tower Provisioning Profile"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    jet_template_id = fields.Many2one(
        "cx.tower.jet.template", required=True, ondelete="restrict", tracking=True
    )
    server_id = fields.Many2one(
        "cx.tower.server", required=True, ondelete="restrict", tracking=True
    )
    base_domain = fields.Char(required=True, default="efactusv.com", tracking=True)
    variable_value_ids = fields.One2many(
        "cx.tower.provisioning.profile.variable", "profile_id", string="Variables"
    )

    @api.constrains("base_domain")
    def _check_base_domain(self):
        for profile in self:
            domain = (profile.base_domain or "").strip().lower().strip(".")
            if not domain or " " in domain or "." not in domain:
                raise ValidationError(
                    _("Enter a valid base domain, for example efactusv.com.")
                )

    def _prepare_variable_values(self, request):
        self.ensure_one()
        values = {
            line.variable_id.reference: line.value_char
            for line in self.variable_value_ids
        }
        values.update(
            {
                "instance_name": request.slug,
                "instance_domain": request.hostname,
            }
        )
        return values


class TowerProvisioningProfileVariable(models.Model):
    _name = "cx.tower.provisioning.profile.variable"
    _description = "Tower Provisioning Profile Variable"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    profile_id = fields.Many2one(
        "cx.tower.provisioning.profile", required=True, ondelete="cascade", index=True
    )
    variable_id = fields.Many2one(
        "cx.tower.variable", required=True, ondelete="restrict"
    )
    value_char = fields.Char(string="Value", required=True)

    _sql_constraints = [
        (
            "profile_variable_unique",
            "unique(profile_id, variable_id)",
            "A variable can only be configured once per profile.",
        )
    ]
