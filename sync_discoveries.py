#!/usr/bin/env python3
"""CLI utility for targeted synchronization of discoveries to FamilySearch via GEDCOM X REST API."""

import sys
from src.familysearch.sync import main

if __name__ == "__main__":
    main()
