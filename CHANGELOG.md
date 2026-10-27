# Changelog

This changelog tracks repository releases: Compose, mounted configuration, image build definitions, scripts, and documentation. Image tags alone do not identify the deployed repository revision.

## 0.2.0 — 2026-10-27

Changes since Git tag `v0.1.0` (`8bc65b9`). Repository release and local project image references move to `0.2.0`; build images locally. No prebuilt image registry publication is included.

### Changed

- Separate Traefik-to-Hub traffic on `jupyterhub_proxy_net` from Hub-to-notebook traffic on `jupyterhub_net`.
- Assign the user network subnet `172.30.250.0/24`, bridge name `br-jhub-users`, and Hub API address `172.30.250.10:8081`.
- Replace Traefik's Docker provider and container-label routing with file-based routing in `traefik/dynamic/jupyterhub.yml`; remove its Docker socket mount. The Hub still requires Docker socket access.
- Add Traefik security headers, login/signup rate limiting, and JSON access logs.
- Harden Traefik with a read-only root filesystem, reduced capabilities, no-new-privileges, memory and process limits; add no-new-privileges, memory and process limits to the Hub.
- Restrict usernames to `^[a-z][a-z0-9_-]{1,31}$` and raise the configured minimum password length from 8 to 12 characters.
- Validate resolved user-directory paths against traversal and create new directories with mode `0700` immediately.
- Standardize repository comments, diagnostics, and notebook examples on English; clarify the architecture diagram and operating instructions.
- Use NativeAuthenticator administrator approval without a second Hub username allowlist (`allow_all=True`, `open_signup=False`); enable its management templates. This deliberately broadens access from administrator-only to approved registered users.

### Added

- Optional IPv4 Linux firewall script and systemd unit in `deploy_linux/`, with selected paths manually tested on a Debian 13 ARM64 VM. Rules are not enabled automatically and require deployment-specific validation.
- Firewall preflight checks for the existing Docker iptables `DOCKER-USER` chain and enabled bridge filtering; stop/cleanup remains available without configured DNS. Guard failures are unit-tested with fake commands; successful installation and 11 runtime checks passed on the Debian VM with the updated script.
- [Linux VM validation report](docs/validation-linux-2026-10-27.md), including environment/image provenance, observed counters, prerequisites and remaining gaps.
- [Migration instructions](docs/migration.md), a [release/Linux validation checklist](docs/release-checklist.md), and an explicit distinction between historical release validation and post-release checks.
- Unit regressions for directory traversal/symlink escapes, private permissions, and configured account policy; CI checks for Compose/Hub/firewall consistency.
- An [opt-in disposable Docker Desktop rehearsal](tests/integration/README.md) covering HTTPS/OAuth, Python/ROOT/custom-kernel WebSockets, persistent storage/environments, account restrictions, login lockout, rate limiting, migration, restart, and snapshot-based rollback.

### Fixed

- Update the storage-hook test to expect directory creation with mode `0700`.
- Document root ownership and mode `0600` for the Linux Traefik private key; document persistent `br_netfilter` configuration to avoid silent bridge-filter bypass.
- Keep host-side configuration tests independent of the container-only NativeAuthenticator dependency.

### Upgrade and validation notes

The Docker network must be recreated during upgrade; existing notebook servers must first be stopped through JupyterHub. Review username compatibility, subnet conflicts, local customizations, and backup/rollback requirements in the migration guide. The updated isolated Docker Desktop rehearsal passed **64 checks**, including approved/unapproved login, authorization navigation, migration and snapshot rollback. The Debian ARM64 VM passed **11 runtime checks** after updating to freshly spawned `0.2.0` services; **27 unit tests** passed on Python 3.10/3.12 and Debian 3.13. See [release evidence](docs/validation-release-0.2.0.json) and [validation status](docs/validation.md). Linux migration/restore, amd64 and full address-range coverage remain untested. Review the intentionally changed account approval policy before upgrading.

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
