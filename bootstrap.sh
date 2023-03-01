#!/bin/bash

set -euo pipefail

# Convert to read-write system, just for this boot...
/sbin/fake-hwclock load force
echo "Current date:"
date

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
find "${SCRIPT_DIR}"

# These variables will be templated
USER="${IMG_NAME}"
STATIC_IP="${STATIC_IP_ADDR}"
RSYNC_DEST="${RSYNC_DEST_ADDR}"

# These variables are filled out by the templates
HOME="/home/${USER}"
INSTALL_DIR="${HOME}/panopticon"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
STATIC_ROUTER="$(cut -d'.' -f1-3 <<<"${STATIC_IP}").1"
RSYNC_DEST_HOST="$(cut -d'@' -f2 <<<"${RSYNC_DEST}" | cut -d':' -f1)"

echo "Received variables:"
echo "  -> USER: ${USER}"
echo "  -> STATIC_IP: ${STATIC_IP}"
echo "  -> RSYNC_DEST_HOST: ${RSYNC_DEST_HOST}"

# Disable the other sshd host key regeneration (we did this manually)
systemctl disable regenerate_ssh_host_keys.service
systemctl disable userconfig.service

# Install `.py` files to our user account
mkdir -p "${INSTALL_DIR}"
cp -a ${SCRIPT_DIR}/src/*.py "${INSTALL_DIR}/"
cp -a ${SCRIPT_DIR}/config/* "${INSTALL_DIR}/"
chmod +x ${INSTALL_DIR}/*.py
chown "${USER}:${USER}" -R "${INSTALL_DIR}"

# Install systemd user scripts
mkdir -p "${SYSTEMD_USER_DIR}"
cp ${SCRIPT_DIR}/etc/*.service ${SCRIPT_DIR}/etc/*.timer "${SYSTEMD_USER_DIR}/"
chown "${USER}:${USER}" -R "${HOME}"
sync

# Enable the timers
for TIMER in ${SCRIPT_DIR}/etc/*.timer; do
    sudo -u "${USER}" systemctl --user enable "$(basename ${TIMER})"
done
# Equivalent of `loginctl enable-linger ${USER}`
mkdir -p /var/lib/systemd/linger
touch /var/lib/systemd/linger/${USER}

# Give the user control over `/data`
chown "${USER}:${USER}" -R /data

# Embed my SSH keys
mkdir -p "${HOME}/.ssh"
curl -L "https://github.com/staticfloat.keys" >> "${HOME}/.ssh/authorized_keys"
chmod 0600 "${HOME}/.ssh/authorized_keys"
chmod 0700 "${HOME}/.ssh"

# Get the host key of the server we're upload to
ssh-keyscan -H "${RSYNC_DEST_HOST}" >> "${HOME}/.ssh/known_hosts"

chown "${USER}:${USER}" -R "${HOME}"
sync

echo "TODO: Enable wireguard" >&2

# NOTE: Use tab-indentation here, as otherwise the heredocs won't work!
# Set up the IP address
if [[ -n "${STATIC_IP}" ]]; then
    cat >>/etc/dhcpcd.conf <<-EOF
	interface eth0
	static ip_address=${STATIC_IP}
	static routers=${STATIC_ROUTER}
	static domain_name_servers=8.8.8.8 8.8.4.4 4.4.4.4 1.1.1.1
	EOF
    echo "Set network to static IP '${STATIC_IP}'"
fi
