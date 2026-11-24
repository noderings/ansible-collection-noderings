# Contributing

Issues and pull requests are welcome at https://github.com/noderings/ansible-collection-noderings.

## Set up

Collections must sit in an `ansible_collections/<namespace>/<name>` directory:

```bash
git clone https://github.com/noderings/ansible-collection-noderings.git \
  ~/ansible_collections/noderings/cloud
cd ~/ansible_collections/noderings/cloud
```

## Before opening a pull request

```bash
ansible-test sanity --venv
ansible-test units --venv
```

Add a changelog fragment for every change users notice, in `changelogs/fragments/<short-name>.yml`:

```yaml
bugfixes:
  - virtual_machine - wait for the firewall to be applied before returning (https://github.com/noderings/ansible-collection-noderings/pull/123).
```

Sections are `major_changes`, `minor_changes`, `breaking_changes`, `deprecated_features`,
`removed_features`, `security_fixes` and `bugfixes`. New modules need no fragment; `version_added` in the
module documentation is enough.

## Integration tests

The targets in `tests/integration/targets` call the real NodeRings API and create real (and, for
virtual machines, billed) resources. See the README for how to run them against a test organization.

## Releasing

1. `antsibull-changelog release --version X.Y.Z`
2. Set `version: X.Y.Z` in `galaxy.yml`, commit, and push a `vX.Y.Z` tag.
   The release workflow builds the collection, creates the GitHub release and publishes it to Ansible Galaxy.
