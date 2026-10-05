# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Same pattern as the customer_email Tower variable. It also keeps the value safe
# inside the quoted odoo shell command: no quotes, spaces or shell characters.
CUSTOMER_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class TowerProvisioningProfile(models.Model):
    _inherit = "cx.tower.provisioning.profile"

    odoo_image = fields.Char(required=True, default="odoo:18.0")
    odoo_workers = fields.Integer(required=True, default=2)
    http_port_start = fields.Integer(required=True, default=18069)
    port_step = fields.Integer(required=True, default=10)
    gevent_port_offset = fields.Integer(required=True, default=1)
    base_dir = fields.Char(required=True, default="/opt/efactusv")
    admin_email = fields.Char(required=True, default="soporte@efactusv.com")
    initial_modules = fields.Char(required=True, default="base")
    ovh_zone_name = fields.Char(required=True, default="efactusv.com")
    db_password_key_id = fields.Many2one(
        "cx.tower.key",
        required=True,
        default=lambda self: self.env.ref(
            "efactusv_tower_odoo.key_odoo_db_password", raise_if_not_found=False
        ),
    )
    admin_password_key_id = fields.Many2one(
        "cx.tower.key",
        required=True,
        default=lambda self: self.env.ref(
            "efactusv_tower_odoo.key_odoo_admin_password", raise_if_not_found=False
        ),
    )
    customer_password_key_id = fields.Many2one(
        "cx.tower.key",
        required=True,
        default=lambda self: self.env.ref(
            "efactusv_tower_odoo.key_odoo_customer_password", raise_if_not_found=False
        ),
    )

    @api.constrains(
        "odoo_workers",
        "http_port_start",
        "port_step",
        "gevent_port_offset",
        "base_dir",
        "admin_email",
        "initial_modules",
    )
    def _check_odoo_settings(self):
        for profile in self:
            if (
                profile.odoo_workers < 1
                or profile.http_port_start < 1024
                or profile.port_step < 2
            ):
                raise ValidationError(
                    _(
                        "Workers must be positive and the port range must start "
                        "above 1023."
                    )
                )
            if not 0 < profile.gevent_port_offset < profile.port_step:
                raise ValidationError(
                    _("The gevent offset must fit inside the allocated port range.")
                )
            if not profile.base_dir.startswith("/"):
                raise ValidationError(
                    _("The instance base directory must be an absolute path.")
                )
            if (
                "@" not in profile.admin_email
                or " " in profile.admin_email
                or "'" in profile.admin_email
            ):
                raise ValidationError(_("Enter a valid administrator email."))
            modules = (profile.initial_modules or "").replace(",", "")
            if not modules.replace("_", "").isalnum():
                raise ValidationError(
                    _("Initial modules must be a comma-separated list of module names.")
                )

    def _allocate_ports(self, request):
        self.ensure_one()
        if request.odoo_http_port and request.odoo_gevent_port:
            return request.odoo_http_port, request.odoo_gevent_port
        self.env.cr.execute(
            "SELECT id FROM cx_tower_server WHERE id = %s FOR UPDATE",
            [self.server_id.id],
        )
        requests = (
            self.env["cx.tower.provisioning.request"]
            .sudo()
            .search(
                [
                    ("profile_id.server_id", "=", self.server_id.id),
                    ("id", "!=", request.id),
                    ("state", "not in", ["cancelled"]),
                    ("odoo_http_port", "!=", 0),
                ]
            )
        )
        used = set(requests.mapped("odoo_http_port"))
        used.update(requests.mapped("odoo_gevent_port"))
        port = self.http_port_start
        while port in used or port + self.gevent_port_offset in used:
            port += self.port_step
        request.write(
            {
                "odoo_http_port": port,
                "odoo_gevent_port": port + self.gevent_port_offset,
            }
        )
        return request.odoo_http_port, request.odoo_gevent_port

    def _ensure_secret(self, key, request):
        self.ensure_one()
        values = key.value_ids.filtered(
            lambda value: (
                value.server_id == self.server_id
                and value.partner_id == request.partner_id
            )
        )
        if not values:
            self.env["cx.tower.key.value"].sudo().create(
                {
                    "key_id": key.id,
                    "server_id": self.server_id.id,
                    "partner_id": request.partner_id.id,
                    "secret_value": secrets.token_urlsafe(32),
                }
            )

    def _prepare_variable_values(self, request):
        values = super()._prepare_variable_values(request)
        http_port, gevent_port = self._allocate_ports(request)
        self._ensure_secret(self.db_password_key_id, request)
        self._ensure_secret(self.admin_password_key_id, request)
        self._ensure_secret(self.customer_password_key_id, request)
        values.update(
            {
                "odoo_image": self.odoo_image,
                "odoo_http_port": str(http_port),
                "odoo_gevent_port": str(gevent_port),
                "odoo_workers": str(self.odoo_workers),
                "base_dir": self.base_dir.rstrip("/"),
                "admin_email": self.admin_email,
                "initial_modules": self.initial_modules,
                "ovh_zone_name": self.ovh_zone_name,
                "customer_email": self._customer_email(request),
            }
        )
        return values

    @staticmethod
    def _customer_email(request):
        email = (request.partner_id.email or "").strip().lower()
        if not CUSTOMER_EMAIL_RE.match(email):
            raise ValidationError(
                _(
                    "Customer %(partner)s needs a valid email to receive the "
                    "instance login.",
                    partner=request.partner_id.display_name,
                )
            )
        return email

    def _customer_password(self, request):
        """Initial password of the customer user, read from the Tower vault."""
        self.ensure_one()
        value = self.customer_password_key_id.sudo().value_ids.filtered(
            lambda value: value.server_id == self.server_id
            and value.partner_id == request.partner_id
        )[:1]
        return value._get_secret_value("secret_value") if value else False
