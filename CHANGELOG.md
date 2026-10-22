# Changelog

This changelog tracks repository releases: Compose, mounted configuration, image build definitions, scripts, and documentation. Image tags alone do not identify the deployed repository revision.

## Unreleased

Changes since Git tag `v0.1.0` (`8bc65b9`). No new release tag or image version has been assigned.

### Changed

- Separate Traefik-to-Hub traffic on `jupyterhub_proxy_net` from Hub-to-notebook traffic on `jupyterhub_net`.
- Assign the user network subnet `172.30.250.0/24`, bridge name `br-jhub-users`, and Hub API address `172.30.250.10:8081`.
- Replace Traefik's Docker provider and container-label routing with file-based routing in `traefik/dynamic/jupyterhub.yml`; remove its Docker socket mount. The Hub still requires Docker socket access.
- Add Traefik security headers, login/signup rate limiting, and JSON access logs.
- Harden Traefik with a read-only root filesystem, reduced capabilities, no-new-privileges, memory and process limits; add no-new-privileges, memory and process limits to the Hub.
- Restrict usernames to `^[a-z][a-z0-9_-]{1,31}$` and raise the configured minimum password length from 8 to 12 characters.
- Validate resolved user-directory paths against traversal and create new directories with mode `0700` immediately.
- Standardize repository comments, diagnostics, and notebook examples on English; clarify the architecture diagram and operating instructions.

### Added

- Optional native Linux firewall script and systemd unit in `deploy_linux/`. These remain untested on native Linux and are not enabled automatically.
- [Migration instructions](docs/migration.md), a [release/Linux validation checklist](docs/release-checklist.md), and an explicit distinction between historical release validation and post-release checks.
- Unit regressions for directory traversal/symlink escapes, private permissions, and configured account policy; CI checks for Compose/Hub/firewall consistency.
- An [opt-in disposable Docker Desktop rehearsal](tests/integration/README.md) covering HTTPS/OAuth, Python/ROOT/custom-kernel WebSockets, persistent storage/environments, account restrictions, rate limiting, migration, restart, and snapshot-based rollback.

### Fixed

- Update the storage-hook test to expect directory creation with mode `0700`.

### Upgrade and validation notes

The Docker network must be recreated during upgrade; existing notebook servers must first be stopped through JupyterHub. Review username compatibility, subnet conflicts, local customizations, and backup/rollback requirements in the migration guide. An isolated Docker Desktop rehearsal passed all 59 checks using separately rebuilt candidate images. Native Linux validation remains pending; see [validation status](docs/validation.md#post-v010-development-checks-2026-10-22).

## 0.1.0 — 2026-10-14

Initial public release, identified by Git tag `v0.1.0` (`8bc65b9`).

- Containerized JupyterHub with NativeAuthenticator, DockerSpawner, persistent workspaces and Conda environments, and a scientific notebook image with Python and CERN ROOT.
- Local development HTTPS through Traefik, loopback-only published ports, and a disabled Traefik dashboard.
- A single shared `jupyterhub_net` network for Traefik, the Hub, and notebook containers.
- Traefik Docker-provider routing configured through Hub labels, with a read-only Docker socket bind mount. This mount did not make Docker API operations read-only.
- Hub API addressed as `jhub`, minimum password length of 8, and no explicit username pattern in the Hub configuration.
- Project image references `jupyterhub-scientific-hub:0.1.0` and `jupyterhub-scientific-notebook:0.1.0`.
- Unit/static checks and [local smoke-test records from 2026-10-14](docs/validation.md#historical-validation-for-v010).

The release was a working development PoC, not a production-security baseline or a reproducible dependency-locked build.
