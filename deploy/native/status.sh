#!/bin/sh
set -eu
systemctl --no-pager status teraifoods-web teraifoods-worker redis-server
free -h
swapon --show
curl --fail --max-time 5 http://178.105.139.193/health/
