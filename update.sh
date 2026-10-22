#!/usr/bin/env bash
# Run from the project directory with: sudo bash update.sh
set -Eeuo pipefail

trap 'echo "Update failed at line $LINENO. Review the error above before retrying." >&2' ERR

if [[ $EUID -ne 0 ]]; then
    echo "Run this script with sudo bash $0" >&2
    exit 1
fi

cd /opt/teraifoods
python=.venv/bin/python
manage=deploy/native/manage.py

echo 'Backing up the database...'
systemctl start teraifoods-backup.service

echo 'Pulling updates...'
git pull --ff-only

echo 'Installing dependencies...'
"$python" -m pip install -r requirements.lock

echo 'Creating and applying migrations...'
"$python" "$manage" makemigrations --noinput
"$python" "$manage" migrate --noinput

echo 'Collecting static files and checking the application...'
"$python" "$manage" collectstatic --noinput
"$python" "$manage" check

echo 'Updating Nginx configuration and media permissions...'
install -m 644 deploy/native/teraifoods.nginx /etc/nginx/sites-available/teraifoods
mkdir -p /opt/teraifoods/media/products /opt/teraifoods/staticfiles
chown -R teraifoods:teraifoods /opt/teraifoods/media /opt/teraifoods/staticfiles
chmod -R u+rwX,g+rwX,a+rX /opt/teraifoods/media /opt/teraifoods/staticfiles
nginx -t

echo 'Restarting project services...'
systemctl daemon-reload
systemctl restart teraifoods-web teraifoods-worker
systemctl reload nginx
systemctl --no-pager --full status teraifoods-web teraifoods-worker

echo 'Checking application health...'
curl --fail --silent --show-error --max-time 10 \
    --retry 10 --retry-delay 2 --retry-connrefused \
    http://178.105.139.193/health/
echo
echo 'Update completed successfully.'
