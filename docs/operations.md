# Operations guide

## Account administration

The committed policy in `jupyterhub/jupyterhub_config.py` is deliberately narrow:

- `jhubadmin` is the administrator and the only username in the explicit allowlist. NativeAuthenticator also maintains its own approval policy.
- NativeAuthenticator open signup is disabled.
- Passwords require at least twelve characters and are checked against common passwords.
- Five failed logins trigger a 600-second retry delay.

### Existing deployment

Preserve `/srv/jupyterhub/hub`. It contains the SQLite database and cookie secret; copying the repository does not copy accounts or credentials.

### Fresh deployment

Bootstrap only on a trusted, locally accessible host, not on a publicly exposed endpoint:

1. Build the images and create the host directories as described in the README.
2. Start the services with `docker compose up -d`.
3. Use NativeAuthenticator's signup page (`/hub/signup`) to create `jhubadmin` with a strong, unique password. Configured administrators are automatically authorized even with `open_signup = False`; no temporary open-signup change is required.
4. Confirm that it can log in and access administration.
5. Verify account policy before granting network access. A fresh unapproved non-admin account was confirmed unable to log in during the smoke test.

`open_signup` is NativeAuthenticator's automatic authorization policy; it is not necessarily a switch that removes the signup form. The username allowlist is a separate JupyterHub policy. See the [NativeAuthenticator documentation](https://native-authenticator.readthedocs.io/) for the pinned version's authorization behavior.

### Additional users

Multi-user container spawning is configured, but general student access is **not** enabled by the committed authentication policy. Deliberately revise the allowlist and NativeAuthenticator approval policy before onboarding users. Test with a non-admin account; do not assume that creating an account or approving it overrides every access restriction.

## Storage and permissions

| Host path | Container path | Contents |
| --- | --- | --- |
| `${JUPYTERHUB_HUB_DIR:-/srv/jupyterhub/hub}` | `/srv/jupyterhub/hub` in Hub | SQLite database and cookie secret |
| `${JUPYTERHUB_USERS_DIR:-/srv/jupyterhub/users}/<username>` | `/home/jovyan/work` in notebook container | Notebooks, user environments, caches, kernelspecs |

Before spawning, the Hub creates the user's directory and sets ownership to UID **1000**, GID **100**, mode **0700**. The host paths must be writable by the Hub container. The same user-storage tree is mounted into the Hub so its permission hook can operate on it.

When overriding storage paths, the Hub still sees the user tree at `/srv/jupyterhub/users`, while DockerSpawner uses the configured **host** path for notebook bind mounts. Both must refer to the same storage tree. On Docker Desktop, filesystem ownership is virtualized and may not report native Linux UID/GID values; workspace write access was verified in the smoke test.

Only the workspace is persisted. Changes elsewhere in a notebook container may disappear when it is removed. Container resource limits do not impose disk quotas; monitor the user tree, especially Conda package caches.

### Backups

Back up both host trees to a secure location outside the repository. For a consistent simple backup:

1. Have users save work and stop their notebook servers through JupyterHub.
2. Confirm no user servers remain running. Compose does not manage the containers created by DockerSpawner.
3. Run `docker compose stop` to stop the Hub before copying its SQLite database.
4. Back up the host trees, preserving ownership, modes, and hidden files.
5. Start the services again with `docker compose up -d`.

Treat backups as sensitive: they contain credentials/authentication state and user data. Test restoration on a separate host. Do not copy a live SQLite database casually or commit it to Git.

## Image updates

Compose does not have `build:` declarations. Build the Hub and notebook images explicitly.

- Hub image reference: `compose.yml`.
- Notebook image reference: `jupyterhub/jupyterhub_config.py`.
- Current project release: `jupyterhub-scientific-hub:0.1.0` and `jupyterhub-scientific-notebook:0.1.0`.
- Match build tags to these references; do not update one without the other.
- Recreate the Hub after a Hub image update: `docker compose up -d --force-recreate jupyterhub`.
- Stop and restart notebook servers to pick up a new notebook image. Existing running containers retain their current image.

Back up persistent state before upgrading Hub/authenticator versions because database migrations may affect rollback. Review upstream compatibility and release notes. Future reproducibility work can pin image digests and Conda dependencies after verifying the working environment.

## Kernel discovery

`register-conda-kernel` installs Python kernels under a persistent custom prefix. To inspect the result:

```sh
jupyter --paths
jupyter kernelspec list
ls /home/jovyan/work/.jupyter/share/jupyter/kernels
```

The committed spawner environment includes `/home/jovyan/work/.jupyter/share/jupyter` in `JUPYTER_PATH`. If a persistent kernelspec exists but is not discovered, confirm that the running server has picked up this configuration; stop and restart older notebook containers after restarting the Hub. If you customize `JUPYTER_PATH`, retain this entry.

Setting the variable only in a terminal does not change the already-running Jupyter server's environment. `JUPYTER_KERNELS_PREFIX` changes where the helper installs files; it does not itself configure discovery.

The helper requires Python and ipykernel in the target environment. It does not create environments or register ROOT C++ kernels.

## Security and exposure

This is a working development deployment, not a public-service security baseline:

- **Development HTTPS:** Traefik terminates TLS on host port 8443 using a locally issued certificate. HTTP on port 8000 redirects to HTTPS. Clients must trust the issuing development CA; use publicly trusted certificates and an appropriate hostname before public deployment.
- **Dashboard disabled:** both dashboard and insecure API access are disabled; port 8080 is not published.
- **Local access only:** ports 8000 and 8443 bind to `127.0.0.1`, and the router matches `localhost`. Network access requires deliberate binding, hostname, certificate, and firewall changes.
- **Docker socket access:** the Hub can control Docker on the host. Treat Hub compromise as host compromise. Traefik has no Docker socket access; it uses the file provider for routing.
- **Containers are not a complete hostile-code sandbox:** capability dropping and resource limits help, but do not replace host hardening, patching, or stronger isolation for untrusted workloads.
- **Network segmentation:** Traefik and the Hub share `jupyterhub_proxy_net`; only the Hub and notebook containers join `jupyterhub_net`. Notebook-to-notebook isolation requires the optional native Linux firewall rules, which remain untested; see [Linux network isolation](../README.md#linux-network-isolation).
- **No disk quotas or automated backups:** implement these operationally if needed.

The `.gitignore` provides guardrails, not secret detection. Review staged files before publishing. There is no checked-in password. Compose's optional storage variables are documented in `.env.example`; no environment variables are required when using the Linux defaults.

## Troubleshooting

### Hub startup or login failures

```sh
docker compose ps
docker compose logs --tail=100 jupyterhub
docker compose logs --tail=100 traefik
```

Check directory permissions and account authorization. The Traefik HTTPS route for `localhost` forwards requests to the Hub's internal port 8000. Its HTTP entrypoint redirects to `https://localhost:8443`.

### HTTPS failures

Generate the certificates using the README instructions before starting Traefik. Confirm `traefik/certs/local.pem` and `traefik/certs/local-key.pem` exist and match the paths in `traefik/dynamic/tls.yml`.

```sh
curl -I http://localhost:8000/hub/login
curl -I https://localhost:8443/hub/login
```

The first request should redirect to HTTPS; the second should succeed with certificate verification enabled. If your curl uses a different trust store, test explicitly with `curl --cacert "$(mkcert -CAROOT)/rootCA.pem" -I https://localhost:8443/hub/login`. Do not disable certificate verification as a fix. Use `localhost`, not an IP address, because the router matches that hostname. Never distribute the CA private key.

### Notebook spawning failures

```sh
docker image inspect jupyterhub-scientific-notebook:0.1.0
docker network inspect jupyterhub_net
docker ps -a
```

Check the Hub logs for the relevant user's spawn attempt. Confirm the image exists on the **same Docker daemon** used by the Hub, the network exists, and the user bind mount is writable with UID/GID 1000:100. The notebook server connects back to the Hub API at `172.30.250.10:8081` on `jupyterhub_net`. Keep this address aligned with `HUB_IP` in `jupyterhub/jupyterhub_config.py` and the Hub's `ipv4_address` in `compose.yml`.

### ROOT notebook failures

Inside the notebook container:

```sh
python -c 'import ROOT; print(ROOT.gROOT.GetVersion())'
jupyter kernelspec list
```

Check that the running server uses the rebuilt image containing `root`, not an older container. Select the correct kernel for the notebook. ROOT's interactive HTML output may need the notebook to be trusted and browser access to JSROOT assets; do not trust notebooks from unknown sources simply to enable output.

## Upstream references

- [JupyterHub](https://jupyterhub.readthedocs.io/)
- [DockerSpawner](https://jupyterhub-dockerspawner.readthedocs.io/)
- [NativeAuthenticator](https://native-authenticator.readthedocs.io/)
- [Jupyter Docker Stacks](https://jupyter-docker-stacks.readthedocs.io/)
- [CERN ROOT](https://root.cern/)
- [Traefik](https://doc.traefik.io/traefik/)
