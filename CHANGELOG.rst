==================================
NodeRings Collection Release Notes
==================================

.. contents:: Topics

v0.1.0
======

Release Summary
---------------

First release of the ``noderings.cloud`` collection. It orders and manages NodeRings virtual machines, DNS zones and records, firewalls, SSH keys and access control, and adds a dynamic inventory of NodeRings servers.

New Plugins
-----------

Inventory
~~~~~~~~~

- noderings.cloud.noderings - NodeRings virtual machines as an Ansible inventory.

New Modules
-----------

- noderings.cloud.billing_info - Read a NodeRings organization's credit, subscriptions and plan limits.
- noderings.cloud.distro_info - List the operating systems NodeRings virtual machines can run.
- noderings.cloud.dns_geo_record - Manage geo\-routed DNS records in a NodeRings zone.
- noderings.cloud.dns_record - Manage DNS records in a NodeRings zone.
- noderings.cloud.dns_record_info - List DNS records in a NodeRings zone.
- noderings.cloud.dns_zone - Manage NodeRings DNS zones and DNSSEC.
- noderings.cloud.dns_zone_info - List NodeRings DNS zones.
- noderings.cloud.environment_variable - Manage environment variables in a NodeRings organization.
- noderings.cloud.firewall_address_group - Manage NodeRings firewall address groups.
- noderings.cloud.firewall_ruleset - Manage NodeRings firewall rulesets and their rules.
- noderings.cloud.firewall_ruleset_info - List NodeRings firewall rulesets and address groups.
- noderings.cloud.game_server - Order and manage NodeRings game servers.
- noderings.cloud.game_server_backup - Take, lock and delete backups of a NodeRings game server.
- noderings.cloud.game_server_database - Manage databases of a NodeRings game server.
- noderings.cloud.game_server_game_info - List the games a NodeRings game\-server plan can run.
- noderings.cloud.game_server_info - List NodeRings game servers.
- noderings.cloud.group - Manage IAM groups and their members in a NodeRings organization.
- noderings.cloud.iam_info - List users, groups, roles, service accounts and permissions of a NodeRings organization.
- noderings.cloud.instant_app_info - List NodeRings instant apps (one\-click applications).
- noderings.cloud.marketplace_addon_info - List add\-ons sold on the NodeRings marketplace.
- noderings.cloud.marketplace_offer_info - Find NodeRings marketplace offers for a plan code in a city.
- noderings.cloud.marketplace_plan_info - List plan codes sold on the NodeRings marketplace, or read one plan.
- noderings.cloud.marketplace_provider_info - List NodeRings hosting providers, or read one provider's catalog.
- noderings.cloud.marketplace_region_info - List the cities where the NodeRings marketplace has offers.
- noderings.cloud.organization_info - Get the NodeRings organization the token acts in.
- noderings.cloud.role - Manage custom IAM roles in a NodeRings organization.
- noderings.cloud.role_assignment - Give a NodeRings user, group or service account its role.
- noderings.cloud.secret - Manage secrets in a NodeRings organization.
- noderings.cloud.ssh_key - Manage SSH keys in a NodeRings organization.
- noderings.cloud.ssh_key_info - List SSH keys in a NodeRings organization.
- noderings.cloud.virtual_machine - Order and manage NodeRings virtual machines.
- noderings.cloud.virtual_machine_additional_ip - Add or remove additional IPv4 addresses on a NodeRings virtual machine.
- noderings.cloud.virtual_machine_backup - Turn automatic backups of a NodeRings virtual machine on or off.
- noderings.cloud.virtual_machine_info - List NodeRings virtual machines.
- noderings.cloud.virtual_machine_snapshot - Take and delete snapshots of NodeRings virtual machines.
