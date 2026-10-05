# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _invoice_paid_hook(self):
        result = super()._invoice_paid_hook()
        invoices = self.filtered(
            lambda move: (
                move.move_type == "out_invoice"
                and move.state == "posted"
                and move.payment_state == "paid"
            )
        )
        for invoice in invoices:
            contracts = invoice.invoice_line_ids.contract_line_id.contract_id
            contracts |= invoice.invoice_line_ids.sale_line_ids.contract_id
            for contract in contracts:
                try:
                    with self.env.cr.savepoint():
                        contract._tower_create_provisioning_request(invoice)
                except Exception as error:  # payment must never be rolled back by infra
                    _logger.exception(
                        "Unable to queue Tower provisioning for %s",
                        contract.display_name,
                    )
                    contract.message_post(
                        body=_(
                            "The invoice was paid, but Tower provisioning could not "
                            "be queued: %(error)s",
                            error=str(error),
                        )
                    )
        return result
