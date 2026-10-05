# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestContractTower(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env["res.partner"].create({"name": "SaaS Customer"})
        cls.os = cls.env["cx.tower.os"].create({"name": "Test OS"})
        cls.server = cls.env["cx.tower.server"].create(
            {
                "name": "Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": cls.os.id,
            }
        )

        JetState = cls.env["cx.tower.jet.state"]
        cls.state_running = JetState.create(
            {"name": "Running", "reference": "test_ct_running", "sequence": 10}
        )
        cls.state_stopped = JetState.create(
            {"name": "Stopped", "reference": "test_ct_stopped", "sequence": 20}
        )
        cls.state_starting = JetState.create(
            {"name": "Starting", "reference": "test_ct_starting", "sequence": 15}
        )
        cls.state_stopping = JetState.create(
            {"name": "Stopping", "reference": "test_ct_stopping", "sequence": 25}
        )

        cls.jet_template = cls.env["cx.tower.jet.template"].create(
            {
                "name": "Odoo SaaS Template",
                "reference": "test_ct_odoo_saas",
                "state_on_contract_terminate_id": cls.state_stopped.id,
                "state_on_contract_reactivate_id": cls.state_running.id,
            }
        )
        JetAction = cls.env["cx.tower.jet.action"]
        cls.action_create = JetAction.create(
            {
                "name": "Create",
                "reference": "test_ct_create",
                "jet_template_id": cls.jet_template.id,
                "state_to_id": cls.state_running.id,
                "state_transit_id": cls.state_starting.id,
            }
        )
        cls.action_stop = JetAction.create(
            {
                "name": "Stop",
                "reference": "test_ct_stop",
                "jet_template_id": cls.jet_template.id,
                "state_from_id": cls.state_running.id,
                "state_to_id": cls.state_stopped.id,
                "state_transit_id": cls.state_stopping.id,
            }
        )
        cls.action_start = JetAction.create(
            {
                "name": "Start",
                "reference": "test_ct_start",
                "jet_template_id": cls.jet_template.id,
                "state_from_id": cls.state_stopped.id,
                "state_to_id": cls.state_running.id,
                "state_transit_id": cls.state_starting.id,
            }
        )

        cls.terminate_reason = cls.env["contract.terminate.reason"].create(
            {"name": "End of service"}
        )
        cls.env.user.groups_id += cls.env.ref(
            "contract_termination.can_terminate_contract"
        )
        cls.env.user.groups_id += cls.env.ref("cetmix_tower_server.group_manager")

        cls.contract = cls.env["contract.contract"].create(
            {
                "name": "SaaS Contract",
                "partner_id": cls.partner.id,
                "tower_jet_template_id": cls.jet_template.id,
                "tower_server_id": cls.server.id,
            }
        )

    def test_create_jet_from_contract(self):
        """Jet is created from the contract with partner and link set."""
        action = self.contract.action_create_tower_jet()
        jet = self.env["cx.tower.jet"].browse(action["res_id"])
        self.assertEqual(jet.contract_id, self.contract)
        self.assertEqual(jet.partner_id, self.partner)
        self.assertEqual(jet.server_id, self.server)
        self.assertEqual(self.contract.tower_jet_count, 1)

    def test_create_jet_requires_configuration(self):
        """Creating an instance without template/server raises."""
        self.contract.tower_server_id = False
        with self.assertRaises(ValidationError):
            self.contract.action_create_tower_jet()

    def test_terminate_contract_stops_jet(self):
        """Terminating the contract brings the jet to the configured state."""
        action = self.contract.action_create_tower_jet()
        jet = self.env["cx.tower.jet"].browse(action["res_id"])
        jet._bring_to_state(self.state_running)
        self.assertEqual(jet.state_id, self.state_running)

        self.contract._terminate_contract(
            self.terminate_reason, "test", fields.Date.today()
        )
        self.assertTrue(self.contract.is_terminated)
        self.assertEqual(jet.state_id, self.state_stopped)

    def test_billing_user_without_tower_access_can_terminate(self):
        """A contract manager outside Tower still terminates the contract."""
        action = self.contract.action_create_tower_jet()
        jet = self.env["cx.tower.jet"].browse(action["res_id"])
        jet._bring_to_state(self.state_running)
        billing_user = self.env["res.users"].create(
            {
                "name": "Billing User",
                "login": "billing-user-tower-contract",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("account.group_account_manager").id,
                            self.env.ref(
                                "contract_termination.can_terminate_contract"
                            ).id,
                        ],
                    )
                ],
            }
        )
        self.contract.with_user(billing_user)._terminate_contract(
            self.terminate_reason, "test", fields.Date.today()
        )
        self.assertTrue(self.contract.is_terminated)
        self.assertEqual(jet.state_id, self.state_stopped)

    def test_cancel_termination_restarts_jet(self):
        """Cancelling the termination brings the jet back to running."""
        action = self.contract.action_create_tower_jet()
        jet = self.env["cx.tower.jet"].browse(action["res_id"])
        jet._bring_to_state(self.state_running)
        self.contract._terminate_contract(
            self.terminate_reason, "test", fields.Date.today()
        )
        self.assertEqual(jet.state_id, self.state_stopped)

        self.contract.action_cancel_contract_termination()
        self.assertFalse(self.contract.is_terminated)
        self.assertEqual(jet.state_id, self.state_running)

    def test_create_jet_on_terminated_contract_raises(self):
        """No new instances on a terminated contract."""
        self.contract._terminate_contract(
            self.terminate_reason, "test", fields.Date.today()
        )
        with self.assertRaises(ValidationError):
            self.contract.action_create_tower_jet()
