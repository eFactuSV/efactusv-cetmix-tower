# efactusv Tower Provisioning

Creates exactly one Tower instance per customer contract after a posted customer invoice
reaches the fully paid state. Provisioning runs through the queue job framework, is
idempotent per contract, and stops at **Ready for Review** so an operator can validate
the service before marking it verified.

Configure a provisioning profile, assign it to a contract service product, and make sure
its Jet template is installed on the selected existing Tower server.
