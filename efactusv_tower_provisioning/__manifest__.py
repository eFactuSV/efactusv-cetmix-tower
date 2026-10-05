# Copyright 2026 efactusv
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "efactusv Tower Provisioning",
    "summary": "Provision Tower services after a customer invoice is paid",
    "version": "18.0.1.1.0",
    "category": "Services/Contract",
    "website": "https://tower.cetmix.com",
    "author": "efactusv",
    "license": "AGPL-3",
    "depends": [
        "product_contract",
        "efactusv_tower_contract",
        "cetmix_tower_server_queue",
        "queue_job",
    ],
    "data": [
        "security/provisioning_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/provisioning_profile_views.xml",
        "views/provisioning_request_views.xml",
        "views/product_template_views.xml",
        "views/contract_contract_views.xml",
        "views/cx_tower_jet_views.xml",
    ],
    "installable": True,
}
