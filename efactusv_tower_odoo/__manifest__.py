# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "efactusv Tower Odoo Blueprint",
    "summary": "Docker, Nginx, OVH DNS and TLS blueprint for Odoo SaaS instances",
    "version": "18.0.1.0.0",
    "category": "Services/Contract",
    "website": "https://tower.cetmix.com",
    "author": "efactusv",
    "license": "AGPL-3",
    "depends": ["efactusv_tower_provisioning", "cetmix_tower_ovh"],
    "data": [
        "data/tower_variables.xml",
        "data/tower_secrets.xml",
        "data/tower_blueprint.xml",
        "views/provisioning_profile_views.xml",
        "views/provisioning_request_views.xml",
    ],
    "installable": True,
}
