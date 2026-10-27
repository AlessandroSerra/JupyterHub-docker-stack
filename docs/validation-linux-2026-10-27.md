# Debian ARM64 VM validation — 2026-10-27

Manual maintainer-assisted validation for a possible **v0.2.0**, not a release certification. Commands were run by the maintainer in a Debian VM on an Apple Silicon Mac; results were reported during the session. This is Linux Docker Engine inside a VM, not Docker Desktop. No production host was tested.

## Provenance

- Base checkout: `faa91d42c327da0d577a8101b449eeae62466c94`, with local changes described below.
- Debian 13 (trixie), reported full version 13.7; kernel `6.12.113+deb13-arm64`, architecture `aarch64`.
- 6 CPUs, 3.822 GiB RAM, approximately 39 GiB initially free disk space.
- Docker Engine 29.9.2, Compose 5.6.1; Docker firewall backend `iptables`, frontend iptables 1.8.11 (`nf_tables`). FORWARD jumps to DOCKER-USER.
- Hub image inspected ID: `sha256:2ecb2f5069ec517c5dd8ac8274f870ea19f1d491b7df0be4244b3d5a3323482b` (`arm64`).
- Notebook image inspected ID: `sha256:afc7e1da0077c0359e3d8891f07aeecf79ee8b139ad86be61af143781df957ed` (`arm64`).
- Both local image tags remained `0.1.0`; they do not identify the checkout. Hub build used cache; notebook build success was reported. This was not an uncached reproducibility test.
- User bridge `br-jhub-users`, subnet `172.30.250.0/24`, gateway `172.30.250.1`, Hub API `172.30.250.10:8081`. Docker network IPv6 disabled.
- Local DNS exception `192.168.64.1`; this environment-specific value is intentionally not committed as a default.
- Hub configuration added NativeAuthenticator template discovery and replaced the Hub username allowlist with `allow_all = True`, while retaining `open_signup = False` and administrator `jhubadmin`.

## Results

| Check | Observation |
| --- | --- |
| HTTPS in Mac browser through SSH tunnel | No certificate warning after trusting the VM mkcert CA and fixing key ownership |
| Admin bootstrap/login and JupyterLab spawn | Passed |
| Non-admin authorization | Unapproved login denied; approved login succeeded after removing the extra Hub allowlist; a further unapproved account remained denied |
| NativeAuthenticator management templates | Added during the session; authorization management was used. Navigation/visual coverage was not exhaustively recorded |
| Python/PyROOT | ROOT reported `6.40.04` |
| ROOT C++ | Maintainer reported working; no captured execution transcript |
| Workspace persistence | Test file contents survived notebook server stop/start |
| Persistent Conda environment/kernel | `analysis` environment created and registered; executable `/home/jovyan/work/.conda/envs/analysis/bin/python`, NumPy `2.5.4`; same result after notebook server replacement |
| Unit/static checks | 22 unit tests passed after adapting mocks and account-policy expectations; Compose contracts passed |
| Network layout | Traefik proxy-only, Hub both networks, notebook user-only, confirmed by container listing |
| Notebook-to-notebook bridge isolation | HTTP target returned 200 before rules; timed out after enabling bridge filtering; DROP counter increased by 5 packets / 300 bytes |
| Internet | DNS resolution and HTTPS 200 before/after policy activation; HTTPS 200 reported after reboot |
| Hub API | `/hub/health` on port 8081 returned 200 with rules active |
| Other Hub port | Port 8000 confirmed listening from Hub; notebook connection timed out |
| Host isolation | Host HTTP target on `172.30.250.1:9001` returned 200 locally; notebook timed out; INPUT DROP increased by 5 packets / 300 bytes |
| Private-network destination | Mac HTTP service `192.168.64.1:9002` returned 200 from VM; notebook timed out; `192.168.0.0/16` DROP increased by 5 packets / 300 bytes |
| Other Docker network | Target `172.19.0.2:9000` reachable from VM but timed out from notebook both with and without custom rules. **Inconclusive for this script**: private-range DROP counter remained zero |
| Lifecycle | Service active, single jumps in INPUT/DOCKER-USER; same after VM reboot. Notebook spawning and bridge isolation worked after reboot |
| Firewall removal/reapplication | systemd stop/start used during diagnosis; service and jump confirmed restored. Full connectivity restoration was not established |

Temporary HTTP services, test containers and test network were subsequently removed.

## Problems found and fixes

1. **Traefik default certificate:** key mode `0600`, owner UID 1000 prevented root Traefik with `cap_drop: ALL` from reading it. Setting host key ownership to `root:root`, retaining `0600`, and restarting Traefik fixed TLS. Do not make the private key world-readable.
2. **Silent bridge-filter bypass:** initial HTTP connection between containers still returned 200 and firewall counters remained zero. `br_netfilter` was absent. Loading it and setting `net.bridge.bridge-nf-call-iptables=1` made the same connection time out with a matching DROP counter. Module/sysctl configuration was persisted and verified after reboot.
3. **Two authorization gates:** NativeAuthenticator approval alone did not admit a user while Hub `allowed_users` contained only `jhubadmin`. Replaced it with `allow_all=True`; manual positive and negative approval tests then passed.
4. **Host-side tests importing a container dependency:** mock NativeAuthenticator module metadata when executing Hub configuration in standard-library unit tests; update assertions to the deliberate new approval policy.

## Automated follow-up on the updated working tree

After the manual session, the updated configuration/tests/script were copied to the same VM (original modifications backed up first). The maintainer installed the new firewall script and restarted its service using sudo. The agent then verified over SSH:

- Service `active`, `ExecMainStatus=0`; installed and checkout script SHA-256 both `2be3f29216b29d0a32b1a6895831a3342bb541b9baff264070e5b8e52372cafb` (VM-specific DNS override included).
- **27 unit tests passed**, Compose contracts passed, Bash syntax passed on Debian Python 3.13. Mocked tests cover missing Docker chain, missing/disabled bridge filtering, unconfigured DNS, successful rule installation and cleanup without prerequisites.
- **11 automated runtime checks passed**: temporary target reachable from Hub but not notebook, Hub API 8081 accessible and port 8000 blocked with a listening positive control, DNS, Internet HTTPS, verified Traefik HTTPS, PyROOT 6.40.04, IPv6 disabled on the user network, workspace owner/mode `1000:100 / 0700`.
- The persisted `jhubadmin` analysis environment executed in a temporary network-disabled container with a **read-only** workspace bind mount, reporting NumPy 2.5.4. This is an environment integrity check, not another Hub-spawn or WebSocket test.

The first automated smoke run incorrectly expected `analysis` in `prova2`'s workspace and failed that check; the environment actually belongs to `jhubadmin`. The optional environment check now requires an explicit path, and the owner's environment was tested separately. No user environment was created or modified to make the test pass.

See the [machine-readable recheck](validation-linux-recheck-2026-10-27.json) for tested-file hashes and results, and [reproduction instructions](../tests/integration/README.md). The temporary HTTP and read-only environment containers were removed. No credentials, API tokens or private keys are included.

## Limits and follow-up

- The updated preflight **positive path** now passed on the VM. Negative paths were tested with fake commands, not by disabling protections on the live VM. This is an uncommitted working-tree recheck, not validation of a future final release commit.
- IPv4 only. Disabled Docker IPv6 is not a general proof of no IPv6 bypass in other deployment configurations.
- No controlled link-local/metadata, CGNAT, or complete private-range matrix. DNS functionality passed, but explicit TCP/UDP resolver-exception rule coverage was not established (Docker's embedded DNS may use another path).
- No Linux upgrade from `v0.1.0`, backup restoration, timed lockout-expiration test, load test, amd64 build, native Docker nftables-backend support, or CD rehearsal.
- Docker daemon restart independent of host reboot and complete removal/connectivity restoration remain to be tested.
- The older 61-check Docker Desktop rehearsal used a different configuration and remains historical evidence; it must be repeated/adapted for the exact candidate if claimed for this release.
- No version/tag, push, hosted-CI result, image publication, or production-readiness approval is implied.

Original local evidence consisted of `build-hub.log`, `build-notebook.log`, `linux-validation-state.txt`, and `v0.2.0-changes.patch`. This report records the useful non-secret provenance and distinguishes captured counters from session-reported outcomes; private certificates, CA keys, Hub state and user data are not included.
