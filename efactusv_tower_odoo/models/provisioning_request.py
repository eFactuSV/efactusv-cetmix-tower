# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class TowerProvisioningRequest(models.Model):
    _inherit = "cx.tower.provisioning.request"

    odoo_http_port = fields.Integer(readonly=True, copy=False)
    odoo_gevent_port = fields.Integer(readonly=True, copy=False)
