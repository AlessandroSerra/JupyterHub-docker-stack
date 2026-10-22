#!/usr/bin/env bash
# Isolamento di rete dei container utente JupyterHub (solo Linux, Docker Engine nativo).
#
# STATO: NON ANCORA TESTATO su un host Linux reale (sviluppato da macOS).
# Validare al primo deploy seguendo deploy/linux/README.md.
#
# Cosa fa:
#   - container utente <-> container utente: bloccato
#   - container utente -> Hub: solo API (tcp/8081)
#   - container utente -> host, LAN, link-local, CGNAT, altre reti Docker: bloccato
#   - DNS verso i resolver indicati: consentito
#   - Internet: consentito (servono conda/pip)
set -euo pipefail

BR="br-jhub-users"          # com.docker.network.bridge.name in compose.yml
HUB_IP="172.30.250.10"      # ipv4_address dell'Hub in compose.yml
DNS_SERVERS=("CHANGE_ME")   # resolver reali, es. ("192.168.1.1" "1.1.1.1")

for ns in "${DNS_SERVERS[@]}"; do
  if [ "$ns" = "CHANGE_ME" ]; then
    echo "Imposta DNS_SERVERS in $0 (vedi README)" >&2
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

# --- traffico che attraversa l'host (container <-> container, container -> esterno) ---
iptables -N JHUB-USERS

# risposte a connessioni già autorizzate (dentro la rete utenti)
iptables -A JHUB-USERS -i "$BR" -o "$BR" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
# container utente -> Hub: solo l'API (porta 8081)
iptables -A JHUB-USERS -i "$BR" -o "$BR" -d "$HUB_IP" -p tcp --dport 8081 -j ACCEPT
# Hub -> container utente: tutto
iptables -A JHUB-USERS -i "$BR" -o "$BR" -s "$HUB_IP" -j ACCEPT
# container utente <-> container utente: bloccato
iptables -A JHUB-USERS -i "$BR" -o "$BR" -j DROP

# DNS verso i resolver indicati
for ns in "${DNS_SERVERS[@]}"; do
  iptables -A JHUB-USERS -i "$BR" -d "$ns" -p udp --dport 53 -j ACCEPT
  iptables -A JHUB-USERS -i "$BR" -d "$ns" -p tcp --dport 53 -j ACCEPT
done

# verso LAN, link-local (metadata cloud), CGNAT, altre reti Docker: bloccato
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do
  iptables -A JHUB-USERS -i "$BR" -d "$net" -j DROP
done
iptables -A JHUB-USERS -j RETURN

iptables -I DOCKER-USER 1 -j JHUB-USERS

# --- traffico verso l'host stesso (catena INPUT) ---
iptables -N JHUB-USERS-INPUT
iptables -A JHUB-USERS-INPUT -i "$BR" -j DROP
iptables -I INPUT 1 -j JHUB-USERS-INPUT
