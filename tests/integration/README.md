# Opt-in deployment checks

## Linux firewall/runtime recheck

On a disposable Linux Docker Engine VM with rules already installed, a running notebook, and the VM's mkcert CA:

```sh
python3 tests/integration/linux_firewall_smoke.py \
  --client jupyter-prova2 --ca "$(mkcert -CAROOT)/rootCA.pem"
```

This standard-library script checks bridge isolation with a reachable HTTP positive control, Hub ports, DNS/Internet, verified Traefik TLS, PyROOT, network IPv6 configuration and workspace permissions. It creates/removes only one temporary HTTP container, does not change firewall rules or existing user data, and needs Docker access (root-equivalent). It assumes the default UID/GID/mode policy. Optionally pass `--environment /home/jovyan/work/.conda/envs/analysis/bin/python` **only if that environment belongs to the selected client**. JSON is printed to stdout; a failed check returns nonzero. This is not a complete LAN/metadata, lifecycle, login or migration test.

## Docker Desktop migration rehearsal

This suite starts a disposable deployment from Git tag `v0.1.0`, creates an administrator and notebook server, writes persistent data and a real Conda environment, upgrades the fixture to the current checkout, restarts it, then restores the baseline snapshot and rolls back. It exercises HTTPS, OAuth session cookies, Python/ROOT/custom-kernel WebSockets, demo notebook execution, account restrictions, five-failure login lockout, rate limiting, container settings, and persistence. Lockout is exercised only against the disposable administrator, after the candidate lifecycle checks; rollback restores the baseline state.

It is **not** part of normal unit tests or automatic CI. It requires a local Docker daemon with spare resources, Python 3.12+, `uv`, `mkcert`, the existing mkcert CA, network access for Conda, and these already-built images:

- `jupyterhub-scientific-hub:0.1.0` and `jupyterhub-scientific-notebook:0.1.0` for baseline/rollback
- `jupyterhub-scientific-hub:0.2.0` and `jupyterhub-scientific-notebook:0.2.0` for the candidate
- `traefik:v3.7`

Review `smoke.py` before running: the disposable Hub and the baseline Traefik receive the Docker socket, which grants significant authority over the daemon. Use a development daemon, not an institutional production host.

## Run

From the repository root:

```sh
uv run --with-requirements tests/integration/requirements.txt \
  python tests/integration/smoke.py --report /tmp/jhub-rehearsal-report.json
```

The suite does not build, retag, or pull project images. It pins the fixture to the IDs of the local images found at startup. By default all stages reuse those images; optionally test separately built candidate images during the upgrade stage:

```sh
uv run --with-requirements tests/integration/requirements.txt \
  python tests/integration/smoke.py --report /tmp/jhub-candidate-report.json \
  --hub-image jupyterhub-scientific-hub:validation-COMMIT \
  --notebook-image jupyterhub-scientific-notebook:validation-COMMIT
```

Build candidate images under distinct local tags, using `docker build --pull --no-cache` if checking fresh package installation. Never overwrite rollback image references. Baseline and rollback always use the original `0.1.0` image IDs; only the current configuration uses the candidate images. Record build commands and base-image digests separately. Even a successful uncached build is not proof of dependency reproducibility.

## Isolation and cleanup

- The repository `.env`, production certificates, Hub database, and user directories are never loaded or mounted.
- Fixture storage and generated development certificates are under a private, randomly named directory in the current user's home directory, suitable for Docker Desktop bind mounts.
- Compose project/container names, spawner prefixes, ownership labels, network names, subnet, bridge name, and loopback ports are distinct from the normal deployment.
- Copied Hub and routing configuration are adjusted only for those fixture names, addresses, ports, image IDs, and paths. The baseline Docker provider is constrained to the fixture's label. These adaptations mean this is an isolated rehearsal of the migration procedure, not an in-place production upgrade.
- Existing running containers are recorded before the run; their IDs, start times, and network attachments are checked afterward.
- Normal teardown removes only fixture-labeled notebooks and the fixture's Compose services/networks. On success, private fixture storage is deleted; on failure it is retained for diagnosis and its path is printed. The sanitized JSON report contains no passwords, tokens, or cookies.
- An uncatchable interruption, daemon failure, or setup failure may leave fixture resources. Inspect only the printed `jhub-check-…` project and its exact label before removing anything. Never use global Docker prune commands. Retained fixture directories contain authentication state and test workspaces; keep them private and remove them when no longer needed.

The script performs real stop/removal operations only on its disposable resources. It does not install firewall rules, change the running normal deployment, or perform native Linux validation. It does not visually inspect the browser UI or graphical output, test hostile-workload containment, exhaust resource limits, or establish production readiness.
