import os

# Must match the jupyterhub service's ipv4_address in compose.yml.
HUB_IP = "172.30.250.10"

USERS_ROOT = "/srv/jupyterhub/users"


def create_user_dir_hook(spawner):
    username = spawner.user.name

    # Guard against path traversal in usernames (e.g. "../hub"):
    # the resolved directory must be directly under USERS_ROOT.
    root = os.path.realpath(USERS_ROOT)
    user_dir = os.path.realpath(os.path.join(root, username))
    if os.path.dirname(user_dir) != root:
        raise ValueError(f"Invalid user directory for {username!r}")

    os.makedirs(user_dir, mode=0o700, exist_ok=True)

    # Standard Jupyter Docker Stacks UID/GID:
    # jovyan:users = 1000:100
    os.chown(user_dir, 1000, 100)
    os.chmod(user_dir, 0o700)


c = get_config()

# Basic JupyterHub settings
c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/hub/jupyterhub_cookie_secret"
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/hub/jupyterhub.sqlite"
c.JupyterHub.log_level = "INFO"

# Do not start a notebook server immediately after login.
c.JupyterHub.redirect_to_server = False

# NativeAuthenticator
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"

# JupyterHub administrator
c.Authenticator.admin_users = {"jhubadmin"}

# Explicitly allowed users
c.Authenticator.allowed_users = {"jhubadmin"}

# Simple usernames only: no "/", "..", spaces, or uppercase letters.
c.Authenticator.username_pattern = r"^[a-z][a-z0-9_-]{1,31}$"

# Disable automatic signup approval; administrators authorize accounts.
c.NativeAuthenticator.open_signup = False

# Password policy
c.NativeAuthenticator.minimum_password_length = 12
c.NativeAuthenticator.check_common_password = True
c.NativeAuthenticator.allowed_failed_logins = 5
c.NativeAuthenticator.seconds_before_next_try = 600

# DockerSpawner
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.image = "jupyterhub-scientific-notebook:0.1.0"
c.DockerSpawner.network_name = "jupyterhub_net"
c.DockerSpawner.use_internal_ip = True

# The Hub API (port 8081) listens only on the user-network IP,
# not on the Traefik network.
c.JupyterHub.hub_ip = HUB_IP
c.JupyterHub.hub_connect_ip = HUB_IP

# Working directory inside the user container
notebook_dir = "/home/jovyan/work"
c.DockerSpawner.notebook_dir = notebook_dir

# Set bind-mount permissions before spawning.
c.Spawner.pre_spawn_hook = create_user_dir_hook

# Notebook environment variables
c.DockerSpawner.environment = {
    "CONDA_ENVS_PATH": "/home/jovyan/work/.conda/envs",
    "CONDA_PKGS_DIRS": "/home/jovyan/work/.conda/pkgs",
    "JUPYTER_PATH": "/home/jovyan/work/.jupyter/share/jupyter",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}

# Docker resolves bind mounts on the host, not inside the Hub container.
# The hook still uses /srv/jupyterhub/users, where Compose mounts this tree.
host_users_dir = os.environ.get("JUPYTERHUB_USERS_DIR", "/srv/jupyterhub/users")
if not os.path.isabs(host_users_dir):
    raise ValueError("JUPYTERHUB_USERS_DIR must be an absolute host path")
c.DockerSpawner.volumes = {os.path.join(host_users_dir, "{username}"): notebook_dir}

# Remove the container when the user stops the server.
# Data remains in the bind mount.
c.DockerSpawner.remove = True

# User-container resource limits
c.DockerSpawner.mem_limit = "2G"
c.DockerSpawner.cpu_limit = 1.0

# Basic user-container hardening
c.DockerSpawner.extra_host_config = {
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "pids_limit": 1024,
}
