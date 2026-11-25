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

## Commit messages

Pull request titles (and commits, if you merge without squashing) use
[Conventional Commits](https://www.conventionalcommits.org/), because release-please reads them to pick the
next version:

- `fix: ...` makes a patch release, `feat: ...` a minor release.
- `feat!: ...` or a `BREAKING CHANGE:` footer makes a major release (a minor one while the version is below 1.0.0).
- `docs:`, `ci:`, `test:` and `chore:` do not start a release on their own.

The changelog that users read still comes from the fragments in `changelogs/fragments`, so add one as well.

## Releasing

Releases are automatic. Nobody edits `galaxy.yml`'s version or pushes tags by hand.

1. After each merge to `main`, the [release-please workflow](.github/workflows/release-please.yml) opens or
   updates one pull request named `chore: release X.Y.Z`. It sets `version` in `galaxy.yml`, and a second job
   runs `antsibull-changelog release --version X.Y.Z`, which turns the fragments into `CHANGELOG.rst`.
2. When you want to release, review that pull request and merge it. release-please then tags the merge commit
   `X.Y.Z` (no `v`, so the tag is exactly the Galaxy version) and creates the GitHub release.
3. The tag starts the [Release workflow](.github/workflows/release.yml). It runs the sanity tests, checks that
   the tag matches `galaxy.yml`, builds the tarball with `ansible-galaxy collection build`, attaches it to the
   GitHub release with a build provenance attestation, and publishes it to Ansible Galaxy.

To publish an existing tag again (for example after adding the Galaxy key), run the Release workflow by hand
from the Actions tab and give it the tag.

One-time setup, done by an organization owner:

| Name | Kind | Where | What |
|---|---|---|---|
| `RELEASE_BOT_APP_ID` (or `RELEASE_BOT_CLIENT_ID`) | Variable | Organization | ID of the organization's release bot GitHub App |
| `RELEASE_BOT_PRIVATE_KEY` | Secret | Organization | The app's private key (`.pem` file contents) |
| `GALAXY_API_KEY` | Secret | This repository | API token from https://galaxy.ansible.com (Collections > API token) |

Until they exist, the workflows skip those steps with a warning instead of failing.
