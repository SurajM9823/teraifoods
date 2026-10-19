#!/bin/sh
set -eu
umask 077
backup_dir=/var/backups/teraifoods
mkdir -p "$backup_dir"
backup_file="$backup_dir/teraifoods-$(date -u +%Y%m%dT%H%M%SZ).dump"
runuser -u postgres -- pg_dump -Fc teraifoods > "$backup_file.tmp"
pg_restore --list "$backup_file.tmp" > /dev/null
mv "$backup_file.tmp" "$backup_file"
find "$backup_dir" -type f -name 'teraifoods-*.dump' -mtime +7 -delete
