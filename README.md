# NodeRings Collection for Ansible

`noderings.cloud` lets Ansible order and manage servers on [NodeRings](https://noderings.com), the marketplace where independent hosting providers sell VPS and game servers.

With it you can:

- order a virtual machine by size and city, and get its IP address back in the same play
- keep DNS zones and records, firewalls, SSH keys, roles and groups in your playbooks
- use your NodeRings servers as an Ansible inventory, grouped by tag, city, provider and more
- run game servers, with their backups and databases

Every module supports check mode, and most support diff mode, so `--check --diff` shows what would change before anything is ordered or deleted.

## Install

```bash
ansible-galaxy collection install noderings.cloud
```

You need ansible-core 2.16 or newer and Python 3.9 or newer. The collection has no Python dependencies.

## Connect

Create a service account in the NodeRings console (**Organization > Service accounts**), give it a role, and copy its token. Then export it:

```bash
export NODERINGS_TOKEN=...
```

Every module reads `NODERINGS_TOKEN`. You can also pass `api_token` to a module, or set it once for all of them with `module_defaults`:

```yaml
- hosts: localhost
  module_defaults:
    group/noderings.cloud.noderings:
      api_token: "{{ vault_noderings_token }}"
```

To act in another organization than the token's own, set `organization_id` (or `NODERINGS_ORGANIZATION_ID`).

## A first playbook

This orders a small server billed by the hour, puts a firewall in front of it, points `www` at it, and waits until SSH answers.

```yaml
- hosts: localhost
  gather_facts: false
  tasks:
    - name: My SSH key
      noderings.cloud.ssh_key:
        name: laptop
        public_key: "{{ lookup('ansible.builtin.file', '~/.ssh/id_ed25519.pub') }}"

    - name: Firewall for a web server
      noderings.cloud.firewall_ruleset:
        name: web
        rules:
          - {direction: ingress, action: accept, protocol: tcp, destination_ports: "22", source: {cidrs: [0.0.0.0/0]}}
          - {direction: ingress, action: accept, protocol: tcp, destination_ports: "80", source: {cidrs: [0.0.0.0/0]}}
          - {direction: ingress, action: accept, protocol: tcp, destination_ports: "443", source: {cidrs: [0.0.0.0/0]}}
          - {direction: ingress, action: accept, protocol: icmp, source: {cidrs: [0.0.0.0/0]}}

    - name: The server
      noderings.cloud.virtual_machine:
        hostname: web-1
        plan_code: SC-GC-1C-1G-20      # 1 vCPU, 1 GB RAM, 20 GB disk
        country: United States
        city: Ashburn
        billing_type: usage            # hourly, paid from prepaid credit
        distro: ubuntu_24_04
        ssh_keys: [laptop]
        firewall_ruleset: web
        tags: [web, prod]
        state: running
      register: vm

    - name: DNS
      noderings.cloud.dns_record:
        zone: example.com
        name: www
        type: A
        ttl: 300
        values: ["{{ vm.virtual_machine.ipv4 }}"]

    - name: Wait for SSH
      ansible.builtin.wait_for:
        host: "{{ vm.virtual_machine.ipv4 }}"
        port: 22
```

Run it again and nothing changes. Remove the server with `state: absent`; billing stops when it is deleted.

## Use your servers as inventory

Create a file whose name ends in `noderings.yml`:

```yaml
# inventory/noderings.yml
plugin: noderings.cloud.noderings
tags: [prod]            # only servers with all of these tags
states: [running]       # only running servers
compose:
  ansible_user: "'root'"
```

```bash
ansible-inventory -i inventory/noderings.yml --graph
ansible -i inventory/noderings.yml noderings_tag_web -m ping
```

Each server gets `ansible_host` (its IPv4 address, or IPv6 with `connect_via: ipv6`) and every field of the VM as a `noderings_` variable, such as `noderings_region_city` or `noderings_plan_code`. Built-in groups:

| Group | Example |
|---|---|
| `noderings_tag_<tag>` | `noderings_tag_web` |
| `noderings_city_<city>` | `noderings_city_ashburn` |
| `noderings_country_<country>` | `noderings_country_germany` |
| `noderings_provider_<provider>` | `noderings_provider_example_hosting` |
| `noderings_plan_<plan code>` | `noderings_plan_sc_gc_1c_1g_20` |
| `noderings_billing_<type>` | `noderings_billing_usage` |
| `noderings_state_<state>` | `noderings_state_running` |

`keyed_groups`, `groups` and `compose` work as in other inventory plugins, and the API answer can be cached with `cache: true`.

## Choosing where your server runs

NodeRings is a marketplace. The same size, called a **plan code**, is usually sold by several hosting providers, in several cities, at different prices. One provider's plan for a code in one city, with its prices, is an **offer**.

When you give `virtual_machine` a `plan_code`, `country` and `city`, it picks an offer for you:

1. It lists the offers for that code in that city, of the `billing_type` you asked for.
2. It drops providers that lack anything in `require_capabilities` (for example `guest_firewall`, which is added for you when you set `firewall_ruleset`), and, with `require_ipv6`, offers without IPv6.
3. It sorts the rest by compute price, or by provider rating with `sort: rating`, and orders the first.

Pin a provider with `provider_id` or `storefront_slug`. To see the offers first, or to order one exact offer, use `marketplace_offer_info` and pass its `plan_id` and `region_id`:

```yaml
- noderings.cloud.marketplace_offer_info:
    plan_code: SC-GC-1C-1G-20
    country: United States
    city: Ashburn
    billing_type: usage
  register: found

- ansible.builtin.debug:
    msg: "{{ found.offers | map(attribute='provider_name') | list }}"
```

The offer is only chosen when the server is ordered. An existing server is never moved to another offer, so a cheaper offer appearing later does not replace it.

To find plan codes, cities and providers:

| To find | Module |
|---|---|
| Cities with offers | `marketplace_region_info` |
| Plan codes, per city or billing type | `marketplace_plan_info` |
| Offers for a code in a city | `marketplace_offer_info` |
| Providers, ratings and capabilities | `marketplace_provider_info` |
| Backups and extra IPs, with prices | `marketplace_addon_info` |
| Operating systems | `distro_info` |
| One-click apps | `instant_app_info` |

## Modules

| Area | Modules |
|---|---|
| Servers | `virtual_machine`, `virtual_machine_info`, `virtual_machine_snapshot`, `virtual_machine_backup`, `virtual_machine_additional_ip` |
| DNS | `dns_zone`, `dns_zone_info`, `dns_record`, `dns_record_info`, `dns_geo_record` |
| Firewall | `firewall_ruleset`, `firewall_address_group`, `firewall_ruleset_info` |
| Access | `ssh_key`, `ssh_key_info`, `role`, `role_assignment`, `group`, `secret`, `environment_variable`, `iam_info` |
| Game servers | `game_server`, `game_server_info`, `game_server_game_info`, `game_server_backup`, `game_server_database` |
| Marketplace | `marketplace_offer_info`, `marketplace_plan_info`, `marketplace_region_info`, `marketplace_provider_info`, `marketplace_addon_info`, `distro_info`, `instant_app_info` |
| Account | `organization_info`, `billing_info` |
| Inventory | `noderings` |

Read a module's full documentation with `ansible-doc noderings.cloud.<module>`, for example `ansible-doc noderings.cloud.virtual_machine`.

## Good to know

- **Billing.** Usage-billed servers (`billing_type: usage`) are charged by the hour from prepaid credit. Check it with `billing_info`. Subscription servers are charged monthly to the card. Backups and extra IPs are add-ons billed with the server.
- **Matching by name.** Modules find things by name: VMs by `hostname`, rulesets and roles by `name`, records by name and type. Keep those names unique, or pass the `id`.
- **What changes in place.** Tags, firewall, power state, backups and extra IPs change in place. A different `distro` needs `allow_reinstall: true` (or `state: reinstalled`), because reinstalling erases the disk.
- **Firewall rules by tag.** A rule with `vm_tags` needs at least one VM that already has the tag, so create the servers first.
- **Secrets** are write-only. `secret` cannot tell whether the stored value differs, so it rewrites it on every run unless `update_value: on_create`.
- **Orders are never retried blindly.** If an order's response is lost, the module looks for the server it just ordered instead of ordering again.

## Development

```bash
git clone https://github.com/noderings/ansible-collection-noderings.git \
  ~/ansible_collections/noderings/cloud
cd ~/ansible_collections/noderings/cloud
ansible-test sanity --venv
ansible-test units --venv
```

Every module has an integration target named after it under `tests/integration/targets`
(`virtual_machine`, `dns_record`, `inventory_noderings`…), the layout other cloud collections use.
They call the real NodeRings API, so they are marked `unsupported` and never run by accident.
Copy `tests/integration/integration_config.yml.template` to `tests/integration/integration_config.yml`
(git-ignored) and fill it in, then pick what to run:

```bash
# Free: account, catalog, SSH keys, DNS, firewall, IAM. Creates and deletes test resources.
ansible-test integration noderings/free/ --allow-unsupported --venv

# Billed: each target orders a small usage-billed VM for a few minutes and deletes it.
ansible-test integration noderings/billed/ --allow-unsupported --venv

# One module
ansible-test integration virtual_machine --allow-unsupported --venv
```

The `virtual_machine` target logs in to the VM over SSH after ordering and after a reinstall, and checks that
the guest runs the expected OS and that cloud-init set the hostname, root SSH key, IPv4 and DNS. With
`noderings_test_os_matrix: true` it reinstalls the VM through every distro and checks each one (about an hour).

Unit tests (`tests/unit`) need no account; they run against an in-memory fake of the API:

```bash
ansible-test units --venv
```

## Support

Open an issue at https://github.com/noderings/ansible-collection-noderings/issues for bugs and feature requests.
For questions about your NodeRings account or servers, contact NodeRings support from the console.

## Release notes

See [CHANGELOG.rst](CHANGELOG.rst).

## Contributing and code of conduct

See [CONTRIBUTING.md](CONTRIBUTING.md). This project follows the
[Ansible Community Code of Conduct](https://docs.ansible.com/ansible/devel/community/code_of_conduct.html).

## More information

- [Using Ansible collections](https://docs.ansible.com/ansible/latest/collections_guide/index.html)
- [NodeRings](https://noderings.com) and the [NodeRings documentation](https://docs.noderings.com)

## License

GNU General Public License v3.0 or later. See [COPYING](COPYING).
