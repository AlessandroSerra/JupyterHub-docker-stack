#!/usr/bin/env bash
# Network isolation for JupyterHub user containers (native Linux Docker Engine only).
#
# STATUS: NOT YET TESTED on a native Linux host (developed on macOS).
# Validate on first deployment using the "Linux network isolation" section in README.md.
#
# Policy:
#   - user container <-> user container: blocked
#   - user container -> Hub: API only (tcp/8081)
#   - user container -> host, LAN, link-local, CGNAT, other Docker networks: blocked
#   - DNS to the specified resolvers: allowed
#   - Internet: allowed (required for conda/pip)
set -euo pipefail

BR="br-jhub-users"          # com.docker.network.bridge.name in compose.yml
HUB_IP="172.30.250.10"      # Hub ipv4_address in compose.yml
DNS_SERVERS=("CHANGE_ME")   # actual resolvers, e.g. ("192.168.1.1" "1.1.1.1")

for ns in "${DNS_SERVERS[@]}"; do
  if [ "$ns" = "CHANGE_ME" ]; then
    echo "Set DNS_SERVERS in $0 (see README)" >&2
    exit 1
  fi
done

remove() {
  iptables -D DOCKER-USER -j JHUB-USERS 2>/dev/null || true
  iptables -D INPUT -j JHUB-USERS-INPUT 2>/dev/null || true
  for chain in JHUB-USERS JHUB-USERS-INPUT; do
    iptables -F "$chain" 2>/dev/null || true
    iptables -X "$chain" 2>/dev/null || true
  done
}

if [ "${1:-start}" = "stop" ]; then
  remove
  exit 0
fi

remove
iptables -N DOCKER-USER 2>/dev/null || true

# --- forwarded traffic (container <-> container, container -> external network) ---
iptables -N JHUB-USERS

# Replies to previously allowed connections within the user network
iptables -A JHUB-USERS -i "$BR" -o "$BR" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
# User container -> Hub: API only (port 8081)
iptables -A JHUB-USERS -i "$BR" -o "$BR" -d "$HUB_IP" -p tcp --dport 8081 -j ACCEPT
# Hub -> user container: allow all traffic
iptables -A JHUB-USERS -i "$BR" -o "$BR" -s "$HUB_IP" -j ACCEPT
# User container <-> user container: blocked
iptables -A JHUB-USERS -i "$BR" -o "$BR" -j DROP

# DNS to the specified resolvers
for ns in "${DNS_SERVERS[@]}"; do
  iptables -A JHUB-USERS -i "$BR" -d "$ns" -p udp --dport 53 -j ACCEPT
  iptables -A JHUB-USERS -i "$BR" -d "$ns" -p tcp --dport 53 -j ACCEPT
done

# Block access to LAN, link-local (cloud metadata), CGNAT, and other Docker networks.
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do
  iptables -A JHUB-USERS -i "$BR" -d "$net" -j DROP
done
iptables -A JHUB-USERS -j RETURN

iptables -I DOCKER-USER 1 -j JHUB-USERS

# --- traffic to the host itself (INPUT chain) ---
iptables -N JHUB-USERS-INPUT
iptables -A JHUB-USERS-INPUT -i "$BR" -j DROP
iptables -I INPUT 1 -j JHUB-USERS-INPUT
