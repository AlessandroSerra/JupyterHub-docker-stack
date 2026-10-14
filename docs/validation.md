# Infrastructure validation

## Project release: 0.1.0

The release uses `jupyterhub-scientific-hub:0.1.0` and `jupyterhub-scientific-notebook:0.1.0`. The local images used for the tests below were retagged without rebuilding; Docker image IDs were verified identical before and after renaming. These release labels do not change the recorded upstream runtime versions.

Compose validation and all 15 unit tests passed after updating the image references. Existing notebook sessions were not restarted solely to change their displayed image names; new containers use the release tags after the Hub reloads its configuration.

## Smoke test: 2026-10-14

The deployment was built and exercised locally on macOS / Apple Silicon using Docker Desktop **4.95.0**, Docker Engine **29.8.2**, and Compose **5.6.0**. Containers ran natively as `linux/arm64`.

This initial smoke test predates the HTTPS configuration and used HTTP. It used a separate Compose project, fresh storage under the tester's home directory, and loopback-only published ports. It did not use a production database or workspace. The committed authentication configuration was used with `open_signup = False`.

### Verified

| Check | Result |
| --- | --- |
| Compose configuration and both image builds | Passed |
| Traefik routing and dashboard HTTP response | Passed |
| Fresh `jhubadmin` signup, browser-session login, and admin page | Passed |
| Authenticated Hub API | Passed |
| DockerSpawner launch and notebook-to-Hub connection | Passed |
| JupyterLab access through Traefik, Hub proxy, and OAuth redirects | Passed |
| NumPy, SciPy, Matplotlib, pandas, SymPy, and PyROOT imports | Passed |
| Python and ROOT C++ kernels installed | Passed |
| `pyroot.ipynb`: all seven code cells and graphical output | Passed |
| `croot.ipynb`: both code cells and graphical output | Passed |
| Workspace writes by the notebook user | Passed |
| 2 GB RAM, 1 CPU, process limit, dropped capabilities, no-new-privileges | Confirmed via Docker inspection |
| Conda environment creation and helper registration | Passed |
| Notebook stop removes the container | Passed |
| Hub restart preserves login credentials and API token | Passed |
| Replacement notebook container preserves workspace and Conda environment | Passed |
| Running Jupyter server discovers the persistent custom kernel | Passed |
| Persistent custom kernel launches and executes from its own environment | Passed |
| Fresh unapproved non-admin account denied login | Passed |

Resolved runtime versions included JupyterHub **5.4.4** in the Hub, JupyterHub **5.3.0** in the notebook image, JupyterLab **4.4.5**, Jupyter Server **2.16.0**, and ROOT **6.40.04**. The Hub/single-user version difference did not prevent the tested workflow; it should still be reviewed when upgrading. Builds are not dependency-locked, so future rebuilds may resolve differently.

### Changes resulting from testing

1. Host storage paths are now configurable through `JUPYTERHUB_HUB_DIR` and `JUPYTERHUB_USERS_DIR`. Defaults remain `/srv/jupyterhub/hub` and `/srv/jupyterhub/users`. DockerSpawner receives the host users path rather than incorrectly using the Hub's internal path when storage is relocated.
2. `JUPYTER_PATH` includes the persistent kernelspec directory. Before this fix, registration succeeded but the kernel was not discovered by Jupyter.
3. Fresh-admin instructions no longer require temporarily enabling automatic signup approval; NativeAuthenticator authorizes configured administrators.

Unit tests cover storage mapping and kernel registration without requiring Docker. CI checks do not automatically reproduce this full runtime smoke test.

## Local HTTPS follow-up: 2026-10-14

After configuring Traefik TLS and recreating the services, the following were verified against the running deployment:

| Check | Result |
| --- | --- |
| HTTP request to `/hub/login` on port 8000 | **301**, redirects to `https://localhost:8443/hub/login` |
| HTTPS request to `/hub/login` on port 8443 | **200** with certificate verification against the local mkcert CA |
| Certificate/key pairing and localhost SAN coverage | Passed |
| Host port bindings | Only `127.0.0.1:8000` and `127.0.0.1:8443` |
| Traefik dashboard and insecure API | Disabled in running configuration; port 8080 not published |
| Certificate/private-key files and local `.env` | Ignored by Git and not tracked |

The user also confirmed the browser workflow and certificate trust work after enabling HTTPS. The initial automated notebook lifecycle tests were not repeated as a new complete HTTPS test suite; the HTTPS follow-up checks routing, certificate verification, and exposure configuration.

These certificates are locally trusted development certificates, not public production certificates. No certificate-verification bypass was used for the HTTPS check.

## Pre-publication checks: 2026-10-14

- All **15 unit tests**, Python syntax checks, and notebook structure checks passed in clean Python **3.10.22** and **3.12.15** containers, matching the workflow's Python version matrix.
- Compose configuration and local documentation links validated successfully.
- Gitleaks **8.24.3** reported no leaks in the existing Git history (one commit) or a snapshot of tracked and non-ignored untracked working-tree files. This is an automated check, not a guarantee that every possible secret is detectable.
- No files were staged at the time of review. Local `.env`, certificates, and private keys were ignored and absent from the index; the entire `traefik/certs/` directory is now excluded regardless of file extension.
- During the initial pre-publication review, no GitHub remote was configured, so an actual GitHub Actions run could not be checked. A remote was subsequently added and the workflow restored after repository reinitialization. Its checks were exercised locally; hosted Actions status must be verified after pushing the workflow.

No commit, staging, or push was performed during this pass.

## Scope and limitations

This is a functional smoke test, not proof of production security or reliability. The following were **not** validated:

- Native Linux host permissions or amd64 builds.
- Multiple simultaneous users, load, or long-running workloads.
- Publicly trusted TLS/ACME issuance, external DNS, or public-network access.
- Disk quotas, backup restoration, or disaster recovery.
- Browser-side rendering of interactive ROOT HTML/JavaScript: notebook execution produced graphical outputs, but no visual browser inspection was performed.
- Exhaustion of memory/CPU limits: settings were inspected, not stress-tested.

Docker Desktop virtualizes bind-mount ownership. The notebook could write its workspace, but this does not establish native Linux permission behavior.

## Rechecking a deployment

Use fresh test storage and trusted access. Build both images, validate Compose, and follow the README's startup instructions. Then:

1. Create/login as the administrator and open JupyterLab.
2. Upload and run both demo notebooks using their respective kernels.
3. Create a Python environment and register its kernel using the README commands.
4. Confirm the kernel appears in JupyterLab and can execute code.
5. Save a workspace file; stop the notebook server; verify its container is removed.
6. Restart the Hub and notebook server; verify login, saved files, environment, and kernel still work.
7. Verify that an unapproved non-admin account cannot log in.
8. Inspect the notebook container's resource and security configuration with `docker inspect`.
9. Stop notebook servers through the Hub before taking the Compose services down.

Do not use production data for destructive lifecycle or account-policy experiments.
