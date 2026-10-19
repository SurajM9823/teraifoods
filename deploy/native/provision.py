"""Run as root after reviewing native service files. Never prints secrets."""
import os
from pathlib import Path
import subprocess as sp
import pwd

def run(*args, **kwargs):
    return sp.run(args, check=True, **kwargs)
try:
    pwd.getpwnam('teraifoods')
except KeyError:
    run('useradd', '--system', '--home-dir', '/opt/teraifoods', '--shell', '/usr/sbin/nologin', 'teraifoods')
env = dict(line.split('=', 1) for line in Path('.env.server').read_text().splitlines() if line and not line.startswith('#'))
password = env['POSTGRES_PASSWORD'].replace("'", "''")
sql = f"CREATE ROLE teraifoods LOGIN PASSWORD '{password}';\nCREATE DATABASE teraifoods OWNER teraifoods;\n"
exists = sp.check_output(['runuser','-u','postgres','--','psql','-Atc',"SELECT 1 FROM pg_roles WHERE rolname='teraifoods'"]).strip()
if not exists:
    run('runuser','-u','postgres','--','psql','-v','ON_ERROR_STOP=1', input=sql, text=True, stdout=sp.DEVNULL)
account = pwd.getpwnam('teraifoods')
os.chown('.env.server', 0, account.pw_gid)
Path('.env.server').chmod(0o640)
for name in ['web','worker']:
    run('install','-m','644',f'deploy/native/teraifoods-{name}.service',f'/etc/systemd/system/teraifoods-{name}.service')
run('install','-m','644','deploy/native/teraifoods-proxy.conf','/etc/nginx/teraifoods-proxy.conf')
run('install','-m','644','deploy/native/teraifoods.nginx','/etc/nginx/sites-available/teraifoods')
p = Path('/etc/nginx/sites-enabled/teraifoods')
if not p.exists():
    p.symlink_to('/etc/nginx/sites-available/teraifoods')
# Cache and task queue share Redis; noeviction preserves queued messages.
p = Path('/etc/redis/redis.conf')
s = p.read_text()
if '# Terai Foods memory budget' not in s:
    p.write_text(s+'\n# Terai Foods memory budget\nmaxmemory 128mb\nmaxmemory-policy noeviction\n')
    run('systemctl','restart','redis-server')
if not Path('/swapfile').exists():
    run('fallocate','-l','2G','/swapfile')
    Path('/swapfile').chmod(0o600)
    run('mkswap','/swapfile')
    run('swapon','/swapfile')
    with Path('/etc/fstab').open('a') as f:
        f.write('\n/swapfile none swap sw 0 0\n')
Path('/etc/sysctl.d/90-teraifoods.conf').write_text('vm.swappiness=10\nvm.vfs_cache_pressure=50\n')
run('sysctl','-p','/etc/sysctl.d/90-teraifoods.conf')
# Initialize only this application's database.
run('/opt/teraifoods/.venv/bin/python','manage.py','migrate','--noinput',env={**os.environ,**env})
run('/opt/teraifoods/.venv/bin/python','manage.py','collectstatic','--noinput',env={**os.environ,**env},stdout=sp.DEVNULL)
run('nginx','-t')
run('systemctl','daemon-reload')
run('systemctl','enable','--now','teraifoods-web','teraifoods-worker')
run('systemctl','reload','nginx')
