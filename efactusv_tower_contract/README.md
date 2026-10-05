# efactusv Tower Contract

Links Cetmix Tower SaaS instances (jets) to customer contracts (OCA `contract`).

## Features

- `contract.contract` gets an **Instance Template** and **Instance Server** plus a
  **Create Instance** button that launches a Cetmix Tower jet linked to the contract and
  its customer.
- Smart buttons on both sides: contract → its instances, jet → its contract.
- **Lifecycle automation** (configured per jet template):
  - _State on Contract Termination_: jets are brought to this state when the linked
    contract is terminated (`contract_termination`).
  - _State on Contract Reactivation_: jets are brought to this state when the
    termination is cancelled.
- Transition failures never block the contract workflow — they are logged in the
  contract chatter instead.

## Configuration

1. In Cetmix Tower, open the jet template used for customer instances and set the
   termination/reactivation states (e.g. `stopped` / `running`).
2. On the contract, pick the jet template and target server, then use _Create Instance_.
