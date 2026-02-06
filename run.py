#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startskript für das GDV Tool.

Verwendung:
    python run.py
"""

import sys
import os

# Füge src-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import main

if __name__ == "__main__":
    main()



