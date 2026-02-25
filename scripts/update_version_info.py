"""
Aktualisiert version_info.txt basierend auf der VERSION-Datei.
Ausfuehren vor jedem Build: python scripts/update_version_info.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

version_path = os.path.join(ROOT, "VERSION")
info_path = os.path.join(ROOT, "version_info.txt")

with open(version_path, 'r', encoding='utf-8-sig') as f:
    version = f.read().strip()

parts = version.split('.')
major = int(parts[0]) if len(parts) > 0 else 0
minor = int(parts[1]) if len(parts) > 1 else 0
patch_str = parts[2] if len(parts) > 2 else '0'
patch = int(re.match(r'\d+', patch_str).group())

with open(info_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r'filevers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)',
    f'filevers=({major}, {minor}, {patch}, 0)',
    content
)
content = re.sub(
    r'prodvers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)',
    f'prodvers=({major}, {minor}, {patch}, 0)',
    content
)
content = re.sub(
    r"u'FileVersion',\s*u'[\d.]+'",
    f"u'FileVersion', u'{major}.{minor}.{patch}.0'",
    content
)
content = re.sub(
    r"u'ProductVersion',\s*u'[\d.]+'",
    f"u'ProductVersion', u'{major}.{minor}.{patch}.0'",
    content
)

with open(info_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"version_info.txt aktualisiert auf {major}.{minor}.{patch}.0")
