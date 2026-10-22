# Opt-in Docker Desktop rehearsal

This suite starts a disposable deployment from Git tag `v0.1.0`, creates an administrator and notebook server, writes persistent data and a real Conda environment, upgrades the fixture to the current checkout, restarts it, then restores the baseline snapshot and rolls back. It exercises HTTPS, OAuth session cookies, Python/ROOT/custom-kernel WebSockets, demo notebook execution, account restrictions, rate limiting, container settings, and persistence.

It is **not** part of normal unit tests or automatic CI. It requires a local Docker daemon with spare resources, Python 3.12+, `uv`, `mkcert`, the existing mkcert CA, network access for Conda, and these already-built images:

- `jupyterhub-scientific-hub:0.1.0`
- `jupyterhub-scientific-notebook:0.1.0`
- `traefik:v3.7`

Review `smoke.py` before running: the disposable Hub and the baseline Traefik receive the Docker socket, which grants significant authority over the daemon. Use a development daemon, not an institutional production host.

## Run

From the repository root:

```sh
uv run --with-requirements tests/integration/requirements.txt \
  python tests/integration/smoke.py --report /tmp/jhub-rehearsal-report.json
```

The suite does not build, retag, or pull project images. It pins the fixture to the IDs of the local images found at startup; this is not a clean-build or dependency-reproducibility test.

## Isolation and cleanup

- The repository `.env`, production certificates, Hub database, and user directories are never loaded or mounted.
- Fixture storage and generated development certificates are under a private, randomly named directory in the current user's home directory, suitable for Docker Desktop bind mounts.
- Compose project/container names, spawner prefixes, ownership labels, network names, subnet, bridge name, and loopback ports are distinct from the normal deployment.
- Copied Hub and routing configuration are adjusted only for those fixture names, addresses, ports, image IDs, and paths. The baseline Docker provider is constrained to the fixture's label. These adaptations mean this is an isolated rehearsal of the migration procedure, not an in-place production upgrade.
- Existing running containers are recorded before the run; their IDs, start times, and network attachments are checked afterward.
- Normal teardown removes only fixture-labeled notebooks and the fixture's Compose services/networks. On success, private fixture storage is deleted; on failure it is retained for diagnosis and its path is printed. The sanitized JSON report contains no passwords, tokens, or cookies.
- An uncatchable interruption, daemon failure, or setup failure may leave fixture resources. Inspect only the printed `jhub-check-…` project and its exact label before removing anything. Never use global Docker prune commands. Retained fixture directories contain authentication state and test workspaces; keep them private and remove them when no longer needed.

The script performs real stop/removal operations only on its disposable resources. It does not install firewall rules, change the running normal deployment, or perform native Linux validation. It does not visually inspect the browser UI or graphical output, test hostile-workload containment, exhaust resource limits, or establish production readiness.
