#!/bin/bash

set -euo pipefail

# We occasionally reach out to the internet, which requires some idea of what time it is.
/sbin/fake-hwclock load force
echo "Current date:"
date

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Extract some base configuration values from `config.py`
read_config() {
	python3 "${SCRIPT_DIR}/src/config_print.py" "${SCRIPT_DIR}/config/config.py" $1 || true
}
USER="panopticon"
STATIC_IP="$(read_config static_ip)"
RSYNC_DEST="$(read_config rsync_dest)"
PASSWORD="$(read_config camera_auth.password)"

# Calculate some values based off of our config values
HOME="/home/${USER}"
INSTALL_DIR="${HOME}/panopticon"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
STATIC_ROUTER="$(cut -d'.' -f1-3 <<<"${STATIC_IP}").1"
RSYNC_DEST_HOST="$(cut -d'@' -f2 <<<"${RSYNC_DEST}" | cut -d':' -f1)"
HOSTNAME="panopticon-${CONFIG_NAME}"

echo "Received variables:"
echo "  -> USER: ${USER}"
echo "  -> STATIC_IP: ${STATIC_IP}"
echo "  -> RSYNC_DEST_HOST: ${RSYNC_DEST_HOST}"

# Disable `userconfig.service`
systemctl disable userconfig.service

# Enable `/data` expansion automatically
systemctl enable grow_data_partition.service

# Set up wireguard
if [[ -f "${SCRIPT_DIR}/config/wg0.conf" ]]; then
	echo "Setting up wireguard..."
	mkdir -p /etc/wireguard
	cp "${SCRIPT_DIR}/config/wg0.conf" /etc/wireguard/wg0.conf
	systemctl enable wg-quick@wg0.service

	# We don't need the `wg0.conf` file anymore (don't need it in `INSTALL_DIR`)
	rm -f "${SCRIPT_DIR}/config/wg0.conf"
fi

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

# Give the user control over `/data` and `/data/pics`
mkdir -p /data/pics
chown "${USER}:${USER}" -R /data

# Embed my SSH keys
mkdir -p "${HOME}/.ssh"
curl -L "https://github.com/staticfloat.keys" >> "${HOME}/.ssh/authorized_keys"
chmod 0600 "${HOME}/.ssh/authorized_keys"
chmod 0700 "${HOME}/.ssh"

# Get the host key of the server we're uploading to
ssh-keyscan -H "${RSYNC_DEST_HOST}" >> "${HOME}/.ssh/known_hosts"
chown "${USER}:${USER}" -R "${HOME}"

# Set password of our user to match the camera:
echo "Setting password for ${USER}"
echo "${USER}:${PASSWORD}" | chpasswd

echo "Setting hostname to ${HOSTNAME}"
echo "${HOSTNAME}" > /etc/hostname
sed -i /etc/hosts -e "s/panopticon/${HOSTNAME}/g"
hostname "${HOSTNAME}"

# We always use static DNS, since we don't want `resolv.conf` auto-generated:
cat >/etc/resolv.conf <<-EOF
search local
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 4.4.4.4
nameserver 1.1.1.1
EOF

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

# Disable annoying SSH banners
rm -f /etc/profile.d/wifi-check.sh
cat >/usr/share/userconf-pi/sshd_banner <<-EOF
The panopticon sees all and knows all.
EOF
