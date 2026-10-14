import os

def create_user_dir_hook(spawner):
    username = spawner.user.name
    user_dir = f"/srv/jupyterhub/users/{username}"

    os.makedirs(user_dir, exist_ok=True)

    # UID/GID standard delle Jupyter Docker Stacks:
    # jovyan:users = 1000:100
    os.chown(user_dir, 1000, 100)
    os.chmod(user_dir, 0o700)

c = get_config()

# Base JupyterHub
c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/hub/jupyterhub_cookie_secret"
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/hub/jupyterhub.sqlite"
c.JupyterHub.log_level = "INFO"

# Per ora non proviamo ad avviare subito un server notebook dopo il login
c.JupyterHub.redirect_to_server = False

# NativeAuthenticator
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"

# Utente admin JupyterHub
c.Authenticator.admin_users = {"jhubadmin"}

# Per ora permettiamo esplicitamente solo questo utente
c.Authenticator.allowed_users = {"jhubadmin"}

# Signup temporaneamente aperto per creare il primo admin
# primo admin creato, chiudiamo open signup
c.NativeAuthenticator.open_signup = False

# Password policy base
c.NativeAuthenticator.minimum_password_length = 8
c.NativeAuthenticator.check_common_password = True
c.NativeAuthenticator.allowed_failed_logins = 5
c.NativeAuthenticator.seconds_before_next_try = 600

# DockerSpawner
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.image = "jupyterhub-scientific-notebook:0.1.0"
c.DockerSpawner.network_name = "jupyterhub_net"
c.DockerSpawner.use_internal_ip = True

# Il container JupyterHub si chiama "jhub" sulla rete Docker
c.JupyterHub.hub_ip = "jhub"
c.JupyterHub.hub_connect_ip = "jhub"

# Directory di lavoro dentro il container studente
notebook_dir = "/home/jovyan/work"
c.DockerSpawner.notebook_dir = notebook_dir

# hook per sistemare i permessi del bind mount
c.Spawner.pre_spawn_hook = create_user_dir_hook

# notebook environment variables
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
c.DockerSpawner.volumes = {
    os.path.join(host_users_dir, "{username}"): notebook_dir
}

# Rimuove il container quando lo studente stoppa il server.
# I dati restano nel bind mount.
c.DockerSpawner.remove = True

# Limiti risorse container studenti
c.DockerSpawner.mem_limit = "2G"
c.DockerSpawner.cpu_limit = 1.0

# Hardening base container studenti
c.DockerSpawner.extra_host_config = {
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "pids_limit": 1024,
}
