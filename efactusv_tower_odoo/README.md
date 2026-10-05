# efactusv Tower Odoo Blueprint

POC blueprint for one isolated Odoo 18 Docker stack per contract on an existing
Tower-managed VPS. It allocates deterministic ports under a server lock, generates
per-customer database and administrator secrets in the Tower vault, creates OVH DNS,
configures Nginx and Let's Encrypt, and exposes lifecycle actions for create, stop,
start and destroy.

Before use:

1. Set values for the three OVH keys on the target server.
2. Install the **efactusv Odoo 18 SaaS** Jet template on that server.
3. Create a provisioning profile using that template and server.
4. Assign the profile to an OCA contract service product.
