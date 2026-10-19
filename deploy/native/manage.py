"""Load the private server environment and run a Django management command."""
import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from dotenv import load_dotenv
load_dotenv(root / '.env.server')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.ip_preview')
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
