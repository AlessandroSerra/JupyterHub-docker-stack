# v0.2.0 release checklist

Scope: a locally built, ARM64-tested development deployment, not production certification. Repository and project image references use `0.2.0`; no prebuilt image publication or CD is included. Remaining platform/security coverage below is explicitly outside the release claim.

## Automated and Docker Desktop checks

- [x] Historical 22-test suite passed on Python 3.10.20, 3.12.13, and 3.14.6 (macOS).
- [x] Current 27-test suite passes locally on Python 3.10 and 3.12, and on Debian Python 3.13, including mocked firewall preflight/cleanup tests. Compose contracts, Python/Bash syntax and notebook structure pass. Hosted CI passed on functional candidate `86f42f7` ([run](https://github.com/AlessandroSerra/JupyterHub-docker-stack/actions/runs/40531052516)); publication is also gated on CI for the final docs/evidence commit.
- [x] Python syntax, notebook structure, Compose configuration, cross-file configuration contracts, and Bash syntax pass.
- [x] The [updated isolated rehearsal](validation-rehearsal-2026-10-27.json) passes **64 checks**, including approved/unapproved login, authorization navigation, migration and snapshot rollback.
- [x] Record source/target commits, fixture adaptations, platform, image IDs, and [uncached candidate-build provenance](validation-builds-2026-10-22.json).
- [x] Separate historical and current [validation evidence](validation.md), including explicit untested behavior.
- [x] Hosted Python 3.10/3.12 and Compose jobs passed on the functional candidate; see the linked run above.
- [ ] Inspect browser rendering separately if visual correctness is part of the release claim.

## Native Linux validation — maintainer action required

A [Debian 13 ARM64 VM session](validation-linux-2026-10-27.md) covered selected runtime and firewall paths. This is partial evidence, not completion of every item below. The updated preflight positive path and 11 automated runtime checks subsequently passed on the VM; see the [recheck evidence](validation-linux-recheck-2026-10-27.json). Final commit/image identity and remaining coverage still require review.

Use a disposable native Linux Docker Engine host or VM, fresh storage, and non-production credentials. A container running under Docker Desktop is not a substitute. Record Engine/Compose/kernel versions, architecture, firewall backend, Git commit, image IDs/digests, and any local changes.

1. **Compatibility and storage:** build the images on the intended architecture; run unit/static checks and the complete [deployment recheck](validation.md#rechecking-a-deployment). Confirm UID 1000/GID 100 workspace writes, `0700` directory modes, persistent environments/kernels, and stop/restart behavior. Note amd64 or arm64 explicitly.
2. **Network layout:** verify Traefik only joins `jupyterhub_proxy_net`, the Hub joins both networks, and notebooks only join `jupyterhub_net`. Confirm Hub API address, subnet, and bridge match the configuration. Check host/VPN subnet conflicts before starting.
3. **Firewall prerequisites:** inspect the real firewall backend and rule hooks before applying the optional script. The current script targets iptables `DOCKER-USER` and host `INPUT`, not a native nftables policy. Verify bridge traffic actually traverses these hooks; the presence of a chain alone does not establish enforcement. Configure real DNS resolvers and review the whole script first.
4. **Positive paths after enabling the rules:** login, fresh spawning, Hub API callbacks, JupyterLab HTTP/WebSockets, Python/ROOT kernels, allowed DNS, and Internet Conda/pip access must still work. Test DNS both before and after enabling the policy.
5. **Negative paths:** from a notebook, attempt TCP connections to another test notebook, Hub ports other than 8081, host services/gateway, private LAN services, other Docker networks, and a controlled link-local/metadata test target. Verify failures using rule counters and reachable positive controls, not just failed ping or a closed destination port. Do not query real cloud credentials or scan unrelated hosts. If IPv6 is enabled, evaluate it separately: this script contains IPv4 iptables rules only.
6. **Lifecycle and rollback:** inspect firewall counters after container replacement and Docker/host restarts. Disable the systemd unit and confirm the custom chains/jumps are removed and expected connectivity returns. Perform these experiments only on the disposable host. Record any failure rather than treating the untested script as a security guarantee.
7. **Upgrade and restore:** rehearse [migration and rollback](migration.md) with Linux permissions and real network recreation. Verify backup restoration, account compatibility, and persistent data after each transition. Stop every notebook before network removal.

Fix issues discovered here before describing native Linux isolation as validated. Retain an explicit experimental/partially validated designation while coverage is incomplete.

### Debian VM follow-up

- [x] Record environment and image IDs, approved/unapproved login, scientific kernels and persistent environments.
- [x] Verify bridge, host, Hub-port and one private-network path using positive controls and counters.
- [x] Verify VM reboot restores bridge-filter prerequisites, single firewall jumps and notebook connectivity/isolation.
- [x] Updated preflight installed successfully on the VM; 27 unit tests, Compose contracts and 11 runtime checks passed; workspace UID/GID/mode inspected as `1000:100 / 0700`.
- [x] Reconcile functional-file hashes and immutable image IDs in [release evidence](validation-release-0.2.0.json); freshly spawn the `0.2.0` notebook in Debian and pass 11 runtime checks.
- [ ] Complete controlled link-local/CGNAT/private-range and direct DNS-exception coverage; do not count the other-Docker-network timeout as enforcement by this script.
- [ ] Verify standalone Docker restart and full firewall-removal connectivity restoration.
- [ ] Linux migration/backup restoration, amd64 and updated isolated integration rehearsal.
- [x] Confirm NativeAuthenticator authorization navigation and approved login through the updated integration rehearsal.
- [x] Capture successful hosted CI for the functional candidate in release evidence.

## Release preparation

- [x] Review changes from `v0.1.0`, approval-policy compatibility and residual Docker-socket authority in the Hub.
- [x] Move repository and local project image references together to `0.2.0`, preserving original `0.1.0` rollback images. Do not publish prebuilt images.
- [x] Update build examples, Compose, spawner, contracts and instructions; record IDs, source hashes and resolved packages in release/rehearsal evidence.
- [x] Repeat the isolated rehearsal and Debian runtime recheck on the functional candidate files; run unit/static checks.
- [x] Verify hosted CI after pushing the functional candidate; rerun on the final docs/evidence commit before tagging.
- [x] Review release notes, migration instructions, BSD license and rollback assets; keep certificates, credentials and user data out of Git.
- [x] Maintainer authorized completion, commit, push and release publication; commit messages must have no conventional-prefix syntax.
- [x] Publication authorized with a mandatory successful-CI gate. Actual tag/publication status is recorded by the GitHub release, not asserted by this checklist.
