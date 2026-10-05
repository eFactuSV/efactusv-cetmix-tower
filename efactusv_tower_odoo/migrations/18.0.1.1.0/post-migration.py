# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

COMMIT = "; env.cr.commit()"


def migrate(cr, version):
    """Make the administrator command persist its changes.

    odoo shell rolls back on exit, so the command never saved the administrator
    login and password. The blueprint is noupdate, so the fix is applied here.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    command = env.ref(
        "efactusv_tower_odoo.command_configure_admin", raise_if_not_found=False
    )
    if not command or "env.cr.commit()" in (command.code or ""):
        return
    marker = "'#!cxtower.secret.EFACTUSV_ODOO_ADMIN_PASSWORD!#'})"
    if marker in command.code:
        command.code = command.code.replace(marker, marker + COMMIT, 1)
