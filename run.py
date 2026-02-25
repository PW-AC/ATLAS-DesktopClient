#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startskript fuer ACENCIA ATLAS.

Verwendung:
    python run.py                    -- Normale App starten
    python run.py --background-update -- Headless Hintergrund-Update
"""

import sys
import os

# Fuege src-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if '--background-update' in sys.argv:
    from background_updater import run_background_update
    sys.exit(run_background_update())

from main import main

if __name__ == "__main__":
    main()



