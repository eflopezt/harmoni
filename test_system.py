import os, sys
sys.path.insert(0, 'D:/Harmoni')
os.environ['DJANGO_SETTINGS_MODULE'] = 'harmoni.settings'

# Find the actual settings module
import subprocess
result = subprocess.run(['D:/Harmoni/.venv/Scripts/python.exe', 'manage.py', 'shell', '-c', 'from django.conf import settings; print(settings.SETTINGS_MODULE if hasattr(settings, "SETTINGS_MODULE") else "unknown")'], capture_output=True, text=True, cwd='D:/Harmoni')
print("settings module:", result.stdout.strip(), result.stderr[:200] if result.stderr else "")
