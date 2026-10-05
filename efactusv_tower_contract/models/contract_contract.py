# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class ContractContract(models.Model):
    _inherit = "contract.contract"

    tower_jet_ids = fields.One2many(
        comodel_name="cx.tower.jet",
        inverse_name="contract_id",
        string="Tower Instances",
    )
    tower_jet_count = fields.Integer(
        compute="_compute_tower_jet_count",
        string="Instances",
    )
    tower_jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        string="Instance Template",
        help="Jet template used to create new instances for this contract",
    )
    tower_server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        string="Instance Server",
        help="Server where new instances for this contract are created",
    )

    def _compute_tower_jet_count(self):
        jet_data = (
            self.env["cx.tower.jet"]
            .sudo()
            ._read_group(
                domain=[("contract_id", "in", self.ids)],
                groupby=["contract_id"],
                aggregates=["__count"],
            )
        )
        count_map = {contract.id: count for contract, count in jet_data}
        for contract in self:
            contract.tower_jet_count = count_map.get(contract.id, 0)

    def action_view_tower_jets(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Instances"),
            "res_model": "cx.tower.jet",
            "view_mode": "kanban,list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }
        if self.tower_jet_count == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.tower_jet_ids.id,
                }
            )
        return action

    def action_create_tower_jet(self):
        """Create a new jet for this contract using the configured template."""
        self.ensure_one()
        if not self.env.user.has_group("cetmix_tower_server.group_manager"):
            raise AccessError(_("Only Tower managers can create instances."))
        if not self.tower_jet_template_id or not self.tower_server_id:
            raise ValidationError(
                _(
                    "Please configure both the instance template and the "
                    "instance server on the contract first."
                )
            )
        if self.is_terminated:
            raise ValidationError(
                _("Cannot create an instance for a terminated contract.")
            )
        jet = self.tower_jet_template_id.create_jet(
            self.tower_server_id,
            name=self.code or self.name,
            partner_id=self.partner_id.id,
            contract_id=self.id,
        )
        if not jet:
            raise ValidationError(
                _(
                    "Failed to create the instance. Check the jet limit on the "
                    "server and the template settings."
                )
            )
        self.message_post(
            body=_(
                "Tower instance %(jet)s created on server %(server)s.",
                jet=jet.display_name,
                server=self.tower_server_id.display_name,
            )
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": jet.id,
            "view_mode": "form",
            "target": "current",
        }

    # -- Contract lifecycle hooks

    def _terminate_contract(
        self,
        terminate_reason_id,
        terminate_comment,
        terminate_date,
        terminate_lines_with_last_date_invoiced=False,
    ):
        res = super()._terminate_contract(
            terminate_reason_id,
            terminate_comment,
            terminate_date,
            terminate_lines_with_last_date_invoiced=terminate_lines_with_last_date_invoiced,
        )
        self._tower_apply_contract_state("state_on_contract_terminate_id")
        return res

    def action_cancel_contract_termination(self):
        res = super().action_cancel_contract_termination()
        self._tower_apply_contract_state("state_on_contract_reactivate_id")
        return res

    def _tower_apply_contract_state(self, template_state_field):
        """Bring the contract jets to the state configured on their template.

        Errors are logged to the contract chatter instead of raised so a
        failing instance transition never blocks the contract workflow.

        Args:
            template_state_field (str): field on cx.tower.jet.template holding
                the target state (e.g. 'state_on_contract_terminate_id').
        """
        # Billing users terminate contracts without Tower access: read the jets
        # as superuser, like the transition below.
        for contract in self.sudo():
            for jet in contract.tower_jet_ids.filtered("active"):
                state = jet.jet_template_id[template_state_field]
                if not state or jet.state_id == state:
                    continue
                try:
                    # Roll back every partial Tower write while preserving the
                    # surrounding contract transaction and its audit trail.
                    with self.env.cr.savepoint():
                        jet.sudo()._bring_to_state(state)
                except Exception:
                    _logger.exception(
                        "Failed to bring jet %s to state %s for contract %s",
                        jet.display_name,
                        state.name,
                        contract.display_name,
                    )
                    contract.message_post(
                        body=_(
                            "Failed to bring instance %(jet)s to state "
                            "%(state)s. Check the instance logs in Cetmix "
                            "Tower.",
                            jet=jet.display_name,
                            state=state.name,
                        )
                    )
