# Migrating from v0.1.0 to post-release development

These instructions describe the changes from Git tag `v0.1.0` (`8bc65b9`) to the current post-release configuration. They are a maintenance plan, not a tested migration procedure or a new release announcement. Rehearse the upgrade and rollback on a separate host before using valuable data.

## What changes

| Area | v0.1.0 | Post-release configuration |
| --- | --- | --- |
| Traefik routing | Docker provider and Hub labels | File provider and `traefik/dynamic/jupyterhub.yml` |
| Traefik Docker socket | Mounted read-only | Not mounted |
| Networks | One shared `jupyterhub_net` | `jupyterhub_proxy_net` plus `jupyterhub_net` |
| User network | Docker-selected subnet and bridge | `172.30.250.0/24`, bridge `br-jhub-users` |
| Hub API | `jhub:8081` | `172.30.250.10:8081` |
| Account policy | Minimum password length 8, no explicit username pattern | Minimum 12, username pattern `^[a-z][a-z0-9_-]{1,31}$` |
| Linux firewall | Not provided | Optional, manually configured, untested |

Host storage defaults, storage environment variables, notebook mount paths, and project image references remain unchanged. The Hub still controls Docker through its socket. This is not a migration to a fully isolated or production-hardened platform.

## Before maintenance

1. Record the source and target commit IDs, Compose project name and options, local overrides, `.env` storage paths, and actual Docker image IDs/digests. Retain the old image contents for rollback; a mutable tag is not an image backup.
2. Review changes to Compose, Hub configuration, and the entire `traefik/dynamic/` directory together. Preserve intentional hostname, TLS, authentication, resource-policy, and storage customizations. Do not combine the old Docker-provider flags/labels with the new routing configuration accidentally.
3. Check that `172.30.250.0/24` does not overlap host, VPN, LAN, or Docker routes. If changed, keep the Compose subnet and Hub address, `HUB_IP` in `jupyterhub/jupyterhub_config.py`, and the optional firewall script aligned.
4. Review existing usernames, including administrator accounts. The new pattern accepts 2–32 lowercase characters, starting with a letter, followed by letters, digits, underscores, or hyphens. Plan any required account/storage changes separately; do not simply rename workspace directories without reconciling authentication state.
5. Review password policy with existing users. Raising the configured minimum does not establish that stored passwords already meet it, and is not a documented forced-reset mechanism. Test the pinned authenticator's behavior and arrange password changes where needed.
6. Schedule downtime and follow the [backup procedure](operations.md#backups). Verify that backups contain both Hub state and user workspaces, including hidden Conda and Jupyter directories, with permissions preserved.

## Stop and replace the network

Perform shutdown using the **old checkout and its original Compose project/options**, before switching to the target revision:

1. Have users save work and stop every notebook server through JupyterHub. Compose does not manage DockerSpawner-created containers.
2. Inspect `docker network inspect jupyterhub_net` and confirm no notebook containers or unrelated services remain attached. Resolve remaining endpoints deliberately; do not force-disconnect active users.
3. Stop the Hub and Traefik, take the consistent backup described above, then remove the old Compose containers and network:

   ```sh
   docker compose stop
   # Complete and verify the backup before continuing.
   docker compose down
   ```

   Use the same project/options as the original deployment. Do not use `--volumes`, delete storage trees, or run a global Docker prune.

4. Verify the old `jupyterhub_net` was removed. If it remains, investigate ownership and attached containers before proceeding. Do not remove networks belonging to other deployments.

The existing network cannot simply acquire the new IPAM subnet and bridge options through `docker compose up`. It must be recreated. A live network switch for existing notebook servers is not supported by this procedure.

## Start the target configuration

1. Check out the exact target revision, restore/reapply reviewed local configuration, and preserve `.env`, certificates, Hub state, and user workspaces. Do not mix the target configuration with running old services.
2. Ensure the local Hub and notebook images exist and record their IDs. Follow the [build instructions](../README.md#start-the-services) if builds are required. Rebuilding a `0.1.0` tag can resolve different upstream dependencies; retain rollback images before overwriting tags.
3. Validate and start, using the original Compose project/options:

   ```sh
   docker compose config --quiet
   docker compose up -d
   docker compose ps
   ```

4. Inspect network membership: Traefik only on `jupyterhub_proxy_net`; Hub on both networks with user-network address `172.30.250.10`; newly spawned notebook containers only on `jupyterhub_net`.
5. Check HTTP-to-HTTPS redirection and trusted TLS, administrator login, fresh notebook spawning, HTTP/WebSocket access, Hub API connectivity, scientific kernels, and persistent workspaces/environments. Follow the complete [deployment recheck](validation.md#rechecking-a-deployment). Verify account restrictions and inspect effective container security/resource settings.
6. On native Linux only, configure and validate the [optional firewall](../README.md#linux-network-isolation) separately. It is not activated by Compose, has not been tested on native Linux, and is not provided as a Docker Desktop host-firewall solution. Do not claim notebook-to-notebook isolation merely because the proxy network is separate.

## Rollback

1. Stop notebook servers through the target Hub, then stop the target services. If installed, disable the optional firewall service while its configured script is still available: `sudo systemctl disable --now jhub-net-rules.service`. Verify its rules were removed.
2. With no remaining notebook endpoints, run `docker compose down` using the target configuration and the same project/options to remove its containers and networks. Investigate any network-removal failures rather than forcing disconnections.
3. Restore the old checkout and reviewed local configuration, retained image contents, and consistent Hub/workspace backups as required by the recovery plan. Restore the two data trees consistently; restoring a snapshot discards subsequent changes, so preserve newer user work separately first. Do not assume a rebuilt image is equivalent to the original.
4. Start the old deployment and repeat login, spawning, kernel, and persistence checks. Reverting to `v0.1.0` also restores its Docker socket exposure in Traefik, shared network, and older account policy; keep access restricted during recovery.

Upgrade and rollback remain unvalidated end-to-end. Record the exact commits, image IDs, platform, results, and any deviations when rehearsing this plan.
