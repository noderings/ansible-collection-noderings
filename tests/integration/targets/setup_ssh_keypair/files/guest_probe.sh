#!/bin/sh
# Prints facts about a guest, one key=value per line. Run as root over SSH.
cloud-init status --wait >/dev/null 2>&1
. /etc/os-release
echo "os=${ID}-${VERSION_ID}"
echo "machine=$(cat /etc/machine-id)"
echo "hostname=$(hostname)"
echo "cloudinit=$(cloud-init status 2>/dev/null | tr -d ' ' | tr '\n' ',')"
echo "net4=$(ping -c1 -W3 1.1.1.1 >/dev/null 2>&1 && echo ok || echo fail)"
echo "net6=$(ping -6 -c1 -W3 2606:4700:4700::1111 >/dev/null 2>&1 && echo ok || echo fail)"
echo "dns=$(getent hosts noderings.com >/dev/null && echo ok || echo fail)"
