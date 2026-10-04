#!/bin/sh
set -eu

AUTHORITY_SOURCE=${1:?authority manifest path required}
RUNTIME_SOURCE=${2:?runtime config path required}

if ! getent group kk-f >/dev/null 2>&1; then
    groupadd --system kk-f
fi
if ! id -u kk-f >/dev/null 2>&1; then
    useradd --system --gid kk-f --home-dir /var/lib/kk-f --no-create-home --shell /usr/sbin/nologin kk-f
fi

install -d -o root -g root -m 0755 /etc/kk-f /opt/kk-f /opt/kk-f/src
install -d -o kk-f -g kk-f -m 0700 /var/lib/kk-f /run/kk-f
install -d -o root -g kk-f -m 0750 /run/kk-f-witness
install -d -o root -g root -m 0700 /var/lib/kk-f-witness

# Install a clean root-owned code snapshot; runtime service cannot modify it.
rm -rf /opt/kk-f/src/kk_f.new
cp -a src/kk_f /opt/kk-f/src/kk_f.new
find /opt/kk-f/src/kk_f.new -type d -exec chmod 0755 {} +
find /opt/kk-f/src/kk_f.new -type f -exec chmod 0644 {} +
chown -R root:root /opt/kk-f/src/kk_f.new
rm -rf /opt/kk-f/src/kk_f
mv /opt/kk-f/src/kk_f.new /opt/kk-f/src/kk_f

install -o root -g root -m 0644 "$AUTHORITY_SOURCE" /etc/kk-f/authority.json
install -o root -g root -m 0644 "$RUNTIME_SOURCE" /etc/kk-f/runtime.json
install -o root -g root -m 0644 deploy/kk-f-witness.service /etc/systemd/system/kk-f-witness.service
install -o root -g root -m 0644 deploy/kk-f.service /etc/systemd/system/kk-f.service
if [ ! -e /var/lib/kk-f-witness/witness.json ]; then
    PYTHONPATH=/opt/kk-f/src /usr/bin/python3 -m kk_f.witness_provision --authority /etc/kk-f/authority.json --runtime /etc/kk-f/runtime.json --state /var/lib/kk-f-witness/witness.json
fi
systemctl daemon-reload
