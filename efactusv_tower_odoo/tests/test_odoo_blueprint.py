# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOdooBlueprint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Blueprint", "email": "Cliente@Example.com"}
        )
        os = cls.env["cx.tower.os"].create({"name": "Blueprint Test OS"})
        cls.server = cls.env["cx.tower.server"].create(
            {
                "name": "Blueprint Test Server",
                "ip_v4_address": "127.0.0.1",
                "ssh_username": "odoo",
                "ssh_password": "test",
                "ssh_auth_mode": "p",
                "host_key": "test",
                "os_id": os.id,
            }
        )
        cls.template = cls.env.ref("efactusv_tower_odoo.jet_template_odoo_saas")
        cls.template.server_ids = [(4, cls.server.id)]
        cls.profile = cls.env["cx.tower.provisioning.profile"].create(
            {
                "name": "Blueprint",
                "jet_template_id": cls.template.id,
                "server_id": cls.server.id,
            }
        )
        contract = cls.env["contract.contract"].create(
            {"name": "Contrato Blueprint", "partner_id": cls.partner.id}
        )
        cls.request = cls.env["cx.tower.provisioning.request"].create(
            {"contract_id": contract.id, "profile_id": cls.profile.id}
        )
        cls.request._ensure_identity()

    def test_variables_carry_normalized_customer_email(self):
        values = self.profile._prepare_variable_values(self.request)
        self.assertEqual(values["customer_email"], "cliente@example.com")
        self.assertTrue(values["odoo_http_port"].isdigit())

    def test_customer_password_is_generated_once_per_customer(self):
        self.profile._prepare_variable_values(self.request)
        first = self.profile._customer_password(self.request)
        self.assertTrue(first)
        self.profile._prepare_variable_values(self.request)
        self.assertEqual(self.profile._customer_password(self.request), first)
        admin = self.profile.admin_password_key_id.sudo().value_ids.filtered(
            lambda value: value.partner_id == self.partner
        )
        self.assertNotEqual(admin._get_secret_value("secret_value"), first)

    def test_unsafe_customer_email_is_rejected(self):
        for email in ("", "sin-arroba", "x'@example.com", "a b@example.com"):
            self.partner.email = email
            with self.assertRaises(ValidationError):
                self.profile._prepare_variable_values(self.request)

    def test_shell_commands_commit(self):
        """odoo shell rolls back on exit; without commit nothing is saved."""
        for xmlid in ("command_configure_admin", "command_configure_customer"):
            command = self.env.ref(f"efactusv_tower_odoo.{xmlid}")
            self.assertIn("env.cr.commit()", command.code)

    def test_customer_user_runs_in_create_plan(self):
        plan = self.env.ref("efactusv_tower_odoo.plan_create_odoo")
        commands = plan.line_ids.sorted("sequence").command_id
        configure = self.env.ref("efactusv_tower_odoo.command_configure_customer")
        start = self.env.ref("efactusv_tower_odoo.command_start_odoo")
        self.assertIn(configure, commands)
        self.assertLess(list(commands).index(configure), list(commands).index(start))

    def test_restart_action(self):
        action = self.env.ref("efactusv_tower_odoo.jet_action_restart")
        running = self.env.ref("cetmix_tower_server.cx_tower_jet_state_running")
        self.assertEqual(action.state_from_id, running)
        self.assertEqual(action.state_to_id, running)
        self.assertEqual(
            action.state_transit_id,
            self.env.ref("cetmix_tower_server.cx_tower_jet_state_restarting"),
        )
