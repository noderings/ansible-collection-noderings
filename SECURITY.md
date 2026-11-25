# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Email **partners@noderings.com** with:

- a description of the issue and its impact
- steps to reproduce, or a proof of concept
- the collection version (`ansible-galaxy collection list noderings.cloud`) and ansible-core version

We acknowledge reports within three working days and keep you updated until the issue is fixed. Credit is given in the release notes unless you ask us not to.

## Supported versions

Security fixes are made for the latest minor release.

## Handling credentials

The modules read the NodeRings service account token from the `api_token` option or the `NODERINGS_TOKEN` environment variable. Keep the token in Ansible Vault or your secret store rather than in plain playbooks or inventory, and give the service account the narrowest NodeRings role that covers the resources you manage. The modules mark the token as `no_log`, so it is never printed in task output.
