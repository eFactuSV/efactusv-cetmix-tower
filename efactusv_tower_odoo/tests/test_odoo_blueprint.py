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

    def test_backup_command_streams_standard_dump_to_signed_url(self):
        code = self.env.ref("efactusv_tower_odoo.command_backup_odoo").code
        self.assertIn("--entrypoint odoo web db -c /etc/odoo/odoo.conf dump", code)
        self.assertIn("-X PUT -T", code)
        self.assertIn("{{ backup_upload_url }}", code)
        self.assertIn("EFACTUSV_BACKUP_SIZE=", code)

    def test_restore_command_always_restarts_web(self):
        code = self.env.ref("efactusv_tower_odoo.command_restore_odoo").code
        self.assertIn("load --force {{ instance_name }}", code)
        self.assertEqual(code.count("docker compose start web"), 2)

    def test_signed_url_variables_reject_quotes(self):
        for xmlid in ("variable_backup_upload_url", "variable_restore_download_url"):
            pattern = self.env.ref(f"efactusv_tower_odoo.{xmlid}").validation_pattern
            self.assertRegex("https://s3.example.com/b/k.zip?X-Amz=1&y=2", pattern)
            self.assertNotRegex("https://x.com/a'b", pattern)

    def test_usage_command_reports_one_parseable_line(self):
        code = self.env.ref("efactusv_tower_odoo.command_usage_odoo").code
        self.assertIn("EFACTUSV_USAGE users=", code)
        self.assertIn("pg_database_size", code)
        self.assertIn("'user_root', 'user_admin'", code)

    def test_domain_commands_keep_the_same_proxy_and_certificate(self):
        add = self.env.ref("efactusv_tower_odoo.command_domain_add").code
        self.assertIn("server_name {{ custom_domain }};", add)
        self.assertIn("proxy_pass http://127.0.0.1:{{ odoo_http_port }};", add)
        self.assertIn("certbot --nginx", add)
        self.assertIn("-d {{ custom_domain }}", add)
        remove = self.env.ref("efactusv_tower_odoo.command_domain_remove").code
        self.assertIn("--cert-name {{ custom_domain }}", remove)

    def test_custom_domain_variable_rejects_unsafe_values(self):
        pattern = self.env.ref("efactusv_tower_odoo.variable_custom_domain")
        pattern = pattern.validation_pattern
        self.assertRegex("erp.miempresa.com", pattern)
        for bad in ("erp miempresa.com", "erp.miempresa.com;rm", "x'.com", "ERP.COM"):
            self.assertNotRegex(bad, pattern)
