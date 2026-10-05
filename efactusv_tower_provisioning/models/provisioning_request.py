# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class TowerProvisioningRequest(models.Model):
    _name = "cx.tower.provisioning.request"
    _description = "Tower Provisioning Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        default=lambda self: self.env._("New"), readonly=True, copy=False
    )
    contract_id = fields.Many2one(
        "contract.contract",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    service_key = fields.Char(required=True, default="primary", readonly=True)
    source_invoice_id = fields.Many2one(
        "account.move", ondelete="restrict", tracking=True
    )
    profile_id = fields.Many2one(
        "cx.tower.provisioning.profile",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    company_id = fields.Many2one(
        related="contract_id.company_id", store=True, index=True
    )
    partner_id = fields.Many2one(
        related="contract_id.partner_id", store=True, index=True
    )
    jet_id = fields.Many2one(
        "cx.tower.jet", ondelete="restrict", tracking=True, copy=False
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("queued", "Queued"),
            ("provisioning", "Provisioning"),
            ("ready_for_review", "Ready for Review"),
            ("verified", "Verified"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    slug = fields.Char(readonly=True, copy=False, tracking=True)
    hostname = fields.Char(readonly=True, copy=False, tracking=True)
    url = fields.Char(readonly=True, copy=False)
    attempt_count = fields.Integer(readonly=True, copy=False)
    last_error = fields.Text(readonly=True, copy=False)

    _sql_constraints = [
        (
            "contract_service_unique",
            "unique(contract_id, service_key)",
            "Only one instance can be provisioned for each contract service.",
        ),
        (
            "hostname_unique",
            "unique(hostname)",
            "The instance hostname must be unique.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                vals["name"] = sequence.next_by_code(
                    "cx.tower.provisioning.request"
                ) or self.env._("New")
        return super().create(vals_list)

    def _check_manager(self):
        if not self.env.user.has_group("cetmix_tower_server.group_manager"):
            raise AccessError(
                _("Only Tower managers can operate provisioning requests.")
            )

    @staticmethod
    def _slugify(value):
        value = (
            unicodedata.normalize("NFKD", value or "")
            .encode("ascii", "ignore")
            .decode()
        )
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:45] or "customer"

    def _ensure_identity(self):
        self.ensure_one()
        if self.slug and self.hostname:
            return
        stem = self._slugify(self.contract_id.code or self.partner_id.name)
        slug = f"{stem}-{self.id}"
        self.write(
            {
                "slug": slug,
                "hostname": f"{slug}.{self.profile_id.base_domain.strip('.').lower()}",
                "url": f"https://{slug}.{self.profile_id.base_domain.strip('.').lower()}",
            }
        )

    def action_enqueue(self):
        self._check_manager()
        return self._enqueue()

    def _enqueue(self):
        for request in self:
            if request.state in (
                "verified",
                "cancelled",
                "provisioning",
                "ready_for_review",
            ):
                continue
            request.write({"state": "queued", "last_error": False})
            request.with_delay(
                identity_key=f"efactusv-tower-provision-{request.id}",
                description=_("Provision %(request)s", request=request.display_name),
            )._run_provisioning()
        return True

    def action_retry(self):
        self._check_manager()
        invalid = self.filtered(lambda request: request.state != "failed")
        if invalid:
            raise UserError(_("Only failed requests can be retried."))
        return self.action_enqueue()

    def action_cancel(self):
        self._check_manager()
        if self.filtered(lambda request: request.jet_id):
            raise UserError(_("A request with an instance cannot be cancelled."))
        self.write({"state": "cancelled"})
        return True

    def action_mark_verified(self):
        self._check_manager()
        invalid = self.filtered(lambda request: request.state != "ready_for_review")
        if invalid:
            raise UserError(_("Only requests ready for review can be verified."))
        self.write({"state": "verified"})
        self.activity_unlink(["mail.mail_activity_data_todo"])
        return True

    def action_open_jet(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": self.jet_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _validate_for_provisioning(self):
        self.ensure_one()
        if self.state != "queued":
            raise ValidationError(_("The request is not queued."))
        if self.contract_id.is_terminated:
            raise ValidationError(_("The contract is terminated."))
        invoice = self.source_invoice_id
        if not invoice or invoice.state != "posted" or invoice.payment_state != "paid":
            raise ValidationError(_("The source invoice is not fully paid."))
        if not self.profile_id.active:
            raise ValidationError(_("The provisioning profile is archived."))
        if self.profile_id.server_id not in self.profile_id.jet_template_id.server_ids:
            raise ValidationError(
                _("The jet template is not installed on the selected server.")
            )
        if self.jet_id:
            raise ValidationError(_("This request already has an instance."))
        if self.contract_id.tower_jet_ids:
            raise ValidationError(_("This contract already has an instance."))

    def _run_provisioning(self):
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM cx_tower_provisioning_request WHERE id = %s FOR UPDATE",
            [self.id],
        )
        try:
            with self.env.cr.savepoint():
                self._validate_for_provisioning()
                self._ensure_identity()
                profile = self.profile_id
                target_state = profile.jet_template_id.action_create_id.state_to_id
                if not target_state:
                    raise ValidationError(_("The jet template has no Create action."))
                jet = profile.jet_template_id.create_jet(
                    profile.server_id,
                    name=self.slug,
                    state=target_state,
                    url=self.url,
                    partner_id=self.partner_id.id,
                    contract_id=self.contract_id.id,
                    provisioning_request_id=self.id,
                    variable_values=profile._prepare_variable_values(self),
                )
                if not jet:
                    raise ValidationError(_("Tower rejected instance creation."))
                self.write(
                    {
                        "jet_id": jet.id,
                        "state": "provisioning"
                        if jet.target_state_id
                        else "ready_for_review",
                        "attempt_count": self.attempt_count + 1,
                        "last_error": False,
                    }
                )
                if not jet.target_state_id:
                    self._schedule_review_activity()
        except Exception as error:
            self._mark_failed(str(error))
        return True

    def _mark_failed(self, error):
        self.ensure_one()
        self.write(
            {
                "state": "failed",
                "attempt_count": self.attempt_count + 1,
                "last_error": error,
            }
        )
        self.message_post(body=_("Provisioning failed: %(error)s", error=error))
        self._schedule_review_activity(summary=_("Tower provisioning failed"))

    def _schedule_review_activity(self, summary=None):
        self.ensure_one()
        group = self.env.ref("cetmix_tower_server.group_manager")
        user = (
            group.users.filtered(lambda item: item.active and not item.share)[:1]
            or self.env.user
        )
        existing = self.activity_ids.filtered(
            lambda activity: (
                activity.activity_type_id
                == self.env.ref("mail.mail_activity_data_todo")
            )
        )
        if not existing:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                summary=summary or _("Review provisioned Odoo instance"),
            )
