#!/bin/bash
set -e
D="$(cd "$(dirname "$0")/.." && pwd)/lab-config/ssh-keys"
if [ ! -f "$D/lab_runner_key" ]; then
    ssh-keygen -t ed25519 -N "" -C "pfg-lab-runner" -f "$D/lab_runner_key" -q
fi
cp "$D/lab_runner_key.pub" "$D/lab_authorized_keys"
cp "$D/lab_runner_key.pub" "$D/restic_b_authorized_keys"
chmod 600 "$D/lab_runner_key"
echo "Claves listas en $D"
