#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <macOS NCM interface, e.g. en7>" >&2
    exit 2
fi
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ADDRESS=$(ipconfig getifaddr "$1")
case "$ADDRESS" in
    10.77.0.*) ;;
    *) echo "No DHCP address in 10.77.0.0/24 on $1: $ADDRESS" >&2; exit 1 ;;
esac
ping -c 2 -W 2000 10.77.0.1
ssh -i "$BASE/out/ssh/client_ed25519" \
    -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="$BASE/out/ssh/known_hosts" root@10.77.0.1 \
    'ip -4 addr show dev lo | grep -q 127.0.0.1/8 &&
     ip -4 addr show dev usb0 | grep -q 10.77.0.1/24 &&
     test -s /run/udhcpd.pid && test -s /run/dropbear.pid &&
     echo NETWORK_PROOF_OK'
