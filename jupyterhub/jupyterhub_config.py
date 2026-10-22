import os

# Deve coincidere con ipv4_address del servizio jupyterhub in compose.yml
HUB_IP = "172.30.250.10"

USERS_ROOT = "/srv/jupyterhub/users"


def create_user_dir_hook(spawner):
    username = spawner.user.name

    # Difesa contro username con path traversal (es. "../hub"):
    # la directory risolta deve stare direttamente sotto USERS_ROOT.
    root = os.path.realpath(USERS_ROOT)
    user_dir = os.path.realpath(os.path.join(root, username))
    if os.path.dirname(user_dir) != root:
        raise ValueError(f"Directory utente non valida per {username!r}")

    os.makedirs(user_dir, mode=0o700, exist_ok=True)

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

# Non avviare subito un server notebook dopo il login
c.JupyterHub.redirect_to_server = False

# NativeAuthenticator
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"

# Utente admin JupyterHub
c.Authenticator.admin_users = {"jhubadmin"}

# Utenti ammessi esplicitamente
c.Authenticator.allowed_users = {"jhubadmin"}

# Solo username "semplici": niente "/", "..", spazi, maiuscole
c.Authenticator.username_pattern = r"^[a-z][a-z0-9_-]{1,31}$"

# Signup chiuso: gli account li autorizza l'admin
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

# L'API dell'Hub (porta 8081) ascolta solo sull'IP della rete utenti,
# non sulla rete di Traefik.
c.JupyterHub.hub_ip = HUB_IP
c.JupyterHub.hub_connect_ip = HUB_IP

# Directory di lavoro dentro il container studente
notebook_dir = "/home/jovyan/work"
c.DockerSpawner.notebook_dir = notebook_dir

# Sistema i permessi del bind mount
c.Spawner.pre_spawn_hook = create_user_dir_hook

# Variabili d'ambiente dei notebook
c.DockerSpawner.environment = {
    "CONDA_ENVS_PATH": "/home/jovyan/work/.conda/envs",
    "CONDA_PKGS_DIRS": "/home/jovyan/work/.conda/pkgs",
    "JUPYTER_PATH": "/home/jovyan/work/.jupyter/share/jupyter",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}

# Docker risolve i bind mount sull'host, non dentro il container dell'Hub.
# L'hook usa comunque /srv/jupyterhub/users, dove Compose monta questo albero.
host_users_dir = os.environ.get("JUPYTERHUB_USERS_DIR", "/srv/jupyterhub/users")
if not os.path.isabs(host_users_dir):
    raise ValueError("JUPYTERHUB_USERS_DIR must be an absolute host path")
c.DockerSpawner.volumes = {os.path.join(host_users_dir, "{username}"): notebook_dir}

# Rimuove il container quando lo studente ferma il server.
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
