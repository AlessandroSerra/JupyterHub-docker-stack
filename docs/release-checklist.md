# Next-release checklist

No new version or tag is assigned by this checklist. The latest released deployment is `v0.1.0`; post-release changes remain **Unreleased**. A possible `v0.2.0` must be a deliberate maintainer decision after reviewing validation evidence and limitations.

## Automated and Docker Desktop checks

- [x] All 22 local unit tests pass on Python 3.10.20, 3.12.13, and 3.14.6 (macOS).
- [x] Python syntax, notebook structure, Compose configuration, cross-file configuration contracts, and Bash syntax pass.
- [x] The [opt-in isolated rehearsal](../tests/integration/README.md) passes: [59 checks](validation-rehearsal-2026-10-22.json), including migration and snapshot rollback.
- [x] Record source/target commits, fixture adaptations, platform, image IDs, and [uncached candidate-build provenance](validation-builds-2026-10-22.json).
- [x] Separate historical and current [validation evidence](validation.md), including explicit untested behavior.
- [ ] Confirm hosted Python 3.10/3.12 CI results after pushing; the local matrix does not establish GitHub Actions status.
- [ ] Inspect browser rendering separately if visual correctness is part of the release claim.

## Native Linux validation — maintainer action required

Use a disposable native Linux Docker Engine host or VM, fresh storage, and non-production credentials. A container running under Docker Desktop is not a substitute. Record Engine/Compose/kernel versions, architecture, firewall backend, Git commit, image IDs/digests, and any local changes.

1. **Compatibility and storage:** build the images on the intended architecture; run unit/static checks and the complete [deployment recheck](validation.md#rechecking-a-deployment). Confirm UID 1000/GID 100 workspace writes, `0700` directory modes, persistent environments/kernels, and stop/restart behavior. Note amd64 or arm64 explicitly.
2. **Network layout:** verify Traefik only joins `jupyterhub_proxy_net`, the Hub joins both networks, and notebooks only join `jupyterhub_net`. Confirm Hub API address, subnet, and bridge match the configuration. Check host/VPN subnet conflicts before starting.
3. **Firewall prerequisites:** inspect the real firewall backend and rule hooks before applying the optional script. The current script targets iptables `DOCKER-USER` and host `INPUT`, not a native nftables policy. Verify bridge traffic actually traverses these hooks; the presence of a chain alone does not establish enforcement. Configure real DNS resolvers and review the whole script first.
4. **Positive paths after enabling the rules:** login, fresh spawning, Hub API callbacks, JupyterLab HTTP/WebSockets, Python/ROOT kernels, allowed DNS, and Internet Conda/pip access must still work. Test DNS both before and after enabling the policy.
5. **Negative paths:** from a notebook, attempt TCP connections to another test notebook, Hub ports other than 8081, host services/gateway, private LAN services, other Docker networks, and a controlled link-local/metadata test target. Verify failures using rule counters and reachable positive controls, not just failed ping or a closed destination port. Do not query real cloud credentials or scan unrelated hosts. If IPv6 is enabled, evaluate it separately: this script contains IPv4 iptables rules only.
6. **Lifecycle and rollback:** inspect firewall counters after container replacement and Docker/host restarts. Disable the systemd unit and confirm the custom chains/jumps are removed and expected connectivity returns. Perform these experiments only on the disposable host. Record any failure rather than treating the untested script as a security guarantee.
7. **Upgrade and restore:** rehearse [migration and rollback](migration.md) with Linux permissions and real network recreation. Verify backup restoration, account compatibility, and persistent data after each transition. Stop every notebook before network removal.

Fix issues discovered here before describing native Linux isolation as validated. At minimum, retain an explicit experimental/untested designation if shipping without successful evidence.

## Release preparation (no publication implied)

- [ ] Review changes from `v0.1.0`, including compatibility notes and residual Docker-socket authority in the Hub.
- [ ] Choose whether deployment and image versions move together or independently. Document the policy; do not silently retag existing image contents.
- [ ] If changing image versions, update build examples, Compose, spawner configuration, contract checks, and operating instructions consistently. Record immutable image IDs/digests and resolved dependencies.
- [ ] Repeat appropriate smoke tests on the exact candidate commit and images. Verify the hosted CI result after pushing; local checks alone do not establish hosted status.
- [ ] Review secrets, licenses, release notes, migration instructions, and rollback assets.
- [ ] Only then approve a version, tag/release, and publication. Push, merge, and release creation require explicit maintainer approval.
