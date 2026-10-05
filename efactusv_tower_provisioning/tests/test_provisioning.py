# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTowerProvisioning(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env["res.partner"].create(
            {"name": "POC Customer", "email": "poc@example.com"}
        )
        cls.os = cls.env["cx.tower.os"].create({"name": "Provisioning Test OS"})
        cls.server = cls.env["cx.tower.server"].create(
            {
                "name": "Provisioning Test Server",
                "ip_v4_address": "127.0.0.1",
                "ssh_username": "odoo",
                "ssh_password": "test",
                "ssh_auth_mode": "p",
                "host_key": "test",
                "os_id": cls.os.id,
            }
        )
        cls.running = cls.env["cx.tower.jet.state"].create(
            {"name": "POC Running", "reference": "poc_running"}
        )
        cls.starting = cls.env["cx.tower.jet.state"].create(
            {"name": "POC Starting", "reference": "poc_starting"}
        )
        cls.template = cls.env["cx.tower.jet.template"].create(
            {
                "name": "POC Template",
                "reference": "poc_template",
                "server_ids": [(6, 0, cls.server.ids)],
            }
        )
        cls.env["cx.tower.jet.action"].create(
            {
                "name": "POC Create",
                "reference": "poc_create",
                "jet_template_id": cls.template.id,
                "state_transit_id": cls.starting.id,
                "state_to_id": cls.running.id,
            }
        )
        cls.profile = cls.env["cx.tower.provisioning.profile"].create(
            {
                "name": "POC",
                "jet_template_id": cls.template.id,
                "server_id": cls.server.id,
                "base_domain": "efactusv.com",
            }
        )
        cls.contract = cls.env["contract.contract"].create(
            {
                "name": "POC Contract",
                "code": "ACME Test",
                "partner_id": cls.partner.id,
                "tower_provisioning_profile_id": cls.profile.id,
                "tower_jet_template_id": cls.template.id,
                "tower_server_id": cls.server.id,
            }
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Provisioning Test Sales",
                "code": "PTS",
                "type": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "invoice_date": "2026-01-01",
                "journal_id": cls.journal.id,
            }
        )

    def test_request_is_idempotent_per_contract(self):
        with patch.object(type(self.env["cx.tower.provisioning.request"]), "_enqueue"):
            first = self.contract._tower_create_provisioning_request(self.invoice)
            second = self.contract._tower_create_provisioning_request(self.invoice)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)

    def _queued_request(self):
        return self.env["cx.tower.provisioning.request"].create(
            {
                "contract_id": self.contract.id,
                "source_invoice_id": self.invoice.id,
                "profile_id": self.profile.id,
                "state": "queued",
            }
        )

    def test_provisioning_auto_verifies_by_default(self):
        request = self._queued_request()
        with (
            patch.object(type(request), "_validate_for_provisioning"),
            patch.object(type(request), "_on_verified", autospec=True) as verified,
        ):
            request._run_provisioning()
        self.assertTrue(request.jet_id)
        self.assertEqual(request.state, "verified")
        verified.assert_called_once()

    def test_in_payment_invoice_counts_as_paid(self):
        request = self._queued_request()
        self.invoice.write({"state": "posted", "payment_state": "in_payment"})
        request._validate_for_provisioning()

    def test_unpaid_invoice_is_rejected(self):
        request = self._queued_request()
        with self.assertRaises(ValidationError):
            request._validate_for_provisioning()

    def test_server_without_capacity_fails_request(self):
        self.template.limit_per_server = 1
        self.template.create_jet(self.server, name="existing-customer")
        request = self._queued_request()
        self.invoice.write({"state": "posted", "payment_state": "paid"})
        with patch.object(type(request), "_schedule_review_activity"):
            request._run_provisioning()
        self.assertEqual(request.state, "failed")
        self.assertIn("no capacity", request.last_error)
        self.assertFalse(request.jet_id)

    def test_provisioning_creates_linked_jet_and_review_state(self):
        self.profile.auto_verify = False
        request = self.env["cx.tower.provisioning.request"].create(
            {
                "contract_id": self.contract.id,
                "source_invoice_id": self.invoice.id,
                "profile_id": self.profile.id,
                "state": "queued",
            }
        )
        with (
            patch.object(type(request), "_validate_for_provisioning"),
            patch.object(type(request), "_schedule_review_activity"),
        ):
            request._run_provisioning()
        self.assertTrue(request.jet_id)
        self.assertEqual(request.jet_id.contract_id, self.contract)
        self.assertEqual(request.jet_id.provisioning_request_id, request)
        self.assertEqual(request.state, "ready_for_review")
        self.assertRegex(request.hostname, r"^acme-test-[0-9]+\.efactusv\.com$")

    def test_non_manager_cannot_retry(self):
        request = self.env["cx.tower.provisioning.request"].create(
            {
                "contract_id": self.contract.id,
                "source_invoice_id": self.invoice.id,
                "profile_id": self.profile.id,
                "state": "failed",
            }
        )
        user = self.env["res.users"].create(
            {
                "name": "Provisioning Reader",
                "login": "provisioning-reader",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            request.with_user(user).action_retry()
