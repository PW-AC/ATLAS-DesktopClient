#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup-Skript fuer Dev-Auth (Pubkey-Login im Entwicklungsmodus).

Verwendung:
    python setup_dev_auth.py

Erzeugt dev_keys/atlas_dev.key und dev_keys/atlas_dev.pub.
Kopiere den Inhalt von atlas_dev.pub nach Local_dev_Backend/config/dev_auth_keys.txt
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dev_auth import generate_keypair

if __name__ == "__main__":
    generate_keypair()
