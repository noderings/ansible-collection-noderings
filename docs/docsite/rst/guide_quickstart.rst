.. _ansible_collections.noderings.cloud.docsite.guide_quickstart:

Getting started with noderings.cloud
====================================

The ``noderings.cloud`` collection orders and manages resources on `NodeRings <https://noderings.com>`_,
the marketplace where independent hosting providers sell compute, storage, network and more.

.. contents::
  :local:
  :depth: 1

Install
-------

.. code-block:: bash

    ansible-galaxy collection install noderings.cloud

Or pin it in a ``requirements.yml`` file and run ``ansible-galaxy collection install -r requirements.yml``:

.. code-block:: yaml

    collections:
      - name: noderings.cloud
        version: ">=0.1.0"

You need ansible-core 2.16 or newer. The modules run on the host that talks to the NodeRings API, usually
``localhost``, and need Python 3.6 or newer there. The collection has no Python dependencies.

Authenticate
------------

Create a service account in the NodeRings console (**Organization > Service accounts**), give it a role,
and copy its token. Every module reads the ``NODERINGS_TOKEN`` environment variable:

.. code-block:: bash

    export NODERINGS_TOKEN=...

You can also pass ``api_token`` to a module, or set it once for all of them with ``module_defaults``
and the ``noderings.cloud.noderings`` action group:

.. code-block:: yaml+jinja

    - hosts: localhost
      module_defaults:
        group/noderings.cloud.noderings:
          api_token: "{{ vault_noderings_token }}"

Order a server
--------------

.. code-block:: yaml+jinja

    - hosts: localhost
      gather_facts: false
      tasks:
        - name: My SSH key
          noderings.cloud.ssh_key:
            name: laptop
            public_key: "{{ lookup('ansible.builtin.file', '~/.ssh/id_ed25519.pub') }}"

        - name: The server
          noderings.cloud.virtual_machine:
            hostname: web-1
            plan_code: SC-GC-1C-1G-20
            country: United States
            city: Ashburn
            billing_type: usage
            distro: ubuntu_24_04
            ssh_keys: [laptop]
            state: running
          register: vm

        - name: Point www at it
          noderings.cloud.dns_record:
            zone: example.com
            name: www
            type: A
            ttl: 300
            values: ["{{ vm.virtual_machine.ipv4 }}"]

Every module supports check mode, so ``ansible-playbook --check --diff`` shows what would change before
anything is ordered or deleted. Remove the server with ``state: absent``.

Use your servers as inventory
-----------------------------

Create a file whose name ends in ``noderings.yml``:

.. code-block:: yaml

    plugin: noderings.cloud.noderings
    tags: [prod]
    states: [running]

Then run ``ansible-inventory -i noderings.yml --graph``. Each server is grouped by tag, city, country,
provider, plan, billing type and state, for example ``noderings_tag_web``.

Get help
--------

Ask questions in the `Get Help <https://forum.ansible.com/tags/c/help/6/cloud>`_ category of the Ansible Forum
with the ``cloud`` tag, and report bugs at https://github.com/noderings/ansible-collection-noderings/issues.
