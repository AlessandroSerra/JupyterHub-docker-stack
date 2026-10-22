"""Check cross-file contracts from `docker compose config --format json` on stdin.

This is a static check: it does not create networks, contact the Hub, or test Linux
firewall enforcement. It requires no third-party Python packages.
"""

import ipaddress
import json
from pathlib import Path
import re
import sys

from test_hub_config import load_config


ROOT = Path(__file__).resolve().parents[1]


def validate(compose):
    services = compose["services"]
    hub = services["jupyterhub"]
    traefik = services["traefik"]
    config, namespace = load_config(hub.get("environment", {}))
    networks = compose["networks"]
    user_key = next(key for key, value in networks.items() if value["name"] == config.DockerSpawner.network_name)
    assert set(traefik["networks"]) == {"proxy_net"}, "Traefik must not join the user network"
    assert set(hub["networks"]) == {"proxy_net", user_key}
    address = hub["networks"][user_key]["ipv4_address"]
    assert address == namespace["HUB_IP"] == config.JupyterHub.hub_ip == config.JupyterHub.hub_connect_ip
    assert any(ipaddress.ip_address(address) in ipaddress.ip_network(entry["subnet"]) for entry in networks[user_key]["ipam"]["config"])
    script = (ROOT / "deploy_linux/jhub-net-rules.sh").read_text()
    assert re.search(r'^HUB_IP="([^"]+)"', script, re.M).group(1) == address
    bridge = re.search(r'^BR="([^"]+)"', script, re.M).group(1)
    assert networks[user_key]["driver_opts"]["com.docker.network.bridge.name"] == bridge
    readme = (ROOT / "README.md").read_text()
    assert f"docker build -t {config.DockerSpawner.image} ./singleuser" in readme
    assert f"docker build -t {hub['image']} ./jupyterhub" in readme
    assert not any("docker.sock" in mount.get("source", "") or "docker.sock" in mount["target"] for mount in traefik["volumes"])
    assert any(mount["target"] == "/var/run/docker.sock" for mount in hub["volumes"])
    assert not any(arg.startswith("--providers.docker") for arg in traefik["command"])
    assert "--providers.file.directory=/etc/traefik/dynamic" in traefik["command"]
    assert traefik["read_only"] and "ALL" in traefik["cap_drop"]
    for service in (hub, traefik):
        assert "no-new-privileges:true" in service["security_opt"]
    for port in traefik["ports"]:
        assert port["host_ip"] == "127.0.0.1", "Default exposure must remain loopback-only"
    assert not hub.get("ports"), "Hub must not publish host ports"
    assert "http://jhub:8000" in (ROOT / "traefik/dynamic/jupyterhub.yml").read_text()
    users_source = next(mount["source"] for mount in hub["volumes"] if mount["target"] == namespace["USERS_ROOT"])
    assert config.DockerSpawner.volumes == {str(Path(users_source) / "{username}"): config.DockerSpawner.notebook_dir}


if __name__ == "__main__":
    validate(json.load(sys.stdin))
    print("Compose / Hub / firewall configuration contracts: OK")
