# v0.2.0 — Network isolation and administrator-approved access

## Highlights

- Separate Traefik proxy traffic from user containers; remove Traefik's Docker socket mount and use file-based routing.
- Add container hardening, security headers, login/signup rate limiting and stricter workspace/username handling.
- Allow user registration with **mandatory administrator approval**. Enable the **Authorize Users** navigation; no second Hub username allowlist is required.
- Add optional IPv4 Linux firewall rules, prerequisite checks and systemd integration. Document `br_netfilter` and private-key ownership requirements discovered in Debian testing.
- Align local Hub/notebook image tags with repository version `0.2.0`.

## Validation

- 27 unit tests passed on Python 3.10/3.12 and Debian 3.13.
- 64 isolated Docker Desktop checks passed, covering login/approval, kernels/WebSockets, scientific demos, persistence, migration and snapshot rollback.
- Debian 13 ARM64 VM: updated firewall installed, Hub recreated and notebook freshly spawned using `0.2.0` images; 11 runtime checks passed. Selected host/private-network paths and reboot persistence were also manually verified.

See [validation](validation.md), [release provenance](validation-release-0.2.0.json), and the [Debian report](validation-linux-2026-10-27.md) for exact scope and limitations.

## Install and upgrade

Images are **built locally**, not published to a registry:

```sh
git clone --branch v0.2.0 https://github.com/AlessandroSerra/JupyterHub-docker-stack.git
cd JupyterHub-docker-stack
docker build -t jupyterhub-scientific-hub:0.2.0 ./jupyterhub
docker build -t jupyterhub-scientific-notebook:0.2.0 ./singleuser
```

Complete certificates, storage and bootstrap setup in the [README](../README.md). Existing installations must follow the [migration guide](migration.md): stop user servers, take a consistent backup, and recreate the changed network. Preserve `0.1.0` images and state backups for rollback.

**Account-policy change:** previously approved non-admin accounts can now log in without an additional Hub allowlist. Review persisted approvals before upgrading. `allow_all=True` does not disable password authentication or NativeAuthenticator approval.

## Known limits

This is a development deployment, **not production-security certification**. The Hub retains root-equivalent Docker access. TLS defaults are local-development only; ports remain loopback-bound. Optional firewall rules are IPv4/iptables-only and partially validated. Native Linux migration/backup restore, full metadata/CGNAT/private-range coverage, amd64, load testing and CD are not claimed. Dependencies remain unlocked; cached successful builds are not reproducible-build or vulnerability guarantees.
