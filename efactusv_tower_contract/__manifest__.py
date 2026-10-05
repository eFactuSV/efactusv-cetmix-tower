# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "efactusv Tower Contract",
    "summary": "Link Cetmix Tower SaaS instances (jets) to customer contracts",
    "version": "18.0.1.1.0",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "efactusv",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "contract",
        "contract_termination",
        "cetmix_tower_server",
    ],
    "data": [
        "views/contract_contract_views.xml",
        "views/cx_tower_jet_views.xml",
        "views/cx_tower_jet_template_views.xml",
    ],
}
