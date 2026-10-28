#!/usr/bin/env python3
"""CLI utility to export pedigree knowledge graph to standard GEDCOM 5.5.1 format."""

import argparse
import sys
from pathlib import Path

from src.gedcom import GedcomExporter
from src.storage.db import Database


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export SQLite pedigree tree to standard GEDCOM 5.5.1 format."
    )
    parser.add_argument(
        "--out",
        type=str,
        default="data/pedigree.ged",
        help="Target output GEDCOM file path (default: data/pedigree.ged).",
    )
    parser.add_argument(
        "--max-gen",
        type=int,
        default=None,
        help="Maximum generation to export (e.g. 5 or 10; default: all available).",
    )
    parser.add_argument(
        "--direct-only",
        action="store_true",
        help="Export direct ancestors only (excluding collateral spouses without direct descendancy).",
    )
    parser.add_argument(
        "--no-sources",
        action="store_true",
        help="Exclude source citations from the export.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/pedigree.sqlite",
        help="Path to SQLite database (default: data/pedigree.sqlite).",
    )

    args = parser.parse_args()
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: Database file '{db_path}' not found.", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)
    db = Database(db_path=db_path)
    exporter = GedcomExporter(db=db)

    print("==================================================")
    print(" GEDCOM 5.5.1 Pedigree Exporter")
    print("==================================================")
    print(f"Source Database:   {db_path}")
    print(f"Output File:       {out_path}")
    if args.max_gen is not None:
        print(f"Max Generation:    {args.max_gen}")
    else:
        print("Max Generation:    All available (0–15)")
    print(f"Direct Ancestors:  {'Yes' if args.direct_only else 'No (Includes Spouses & Collateral)'}")
    print(f"Include Sources:   {'No' if args.no_sources else 'Yes'}")
    print("--------------------------------------------------")
    print("Exporting records...", end=" ", flush=True)

    stats = exporter.export_to_file(
        output_path=out_path,
        max_generation=args.max_gen,
        direct_only=args.direct_only,
        include_sources=not args.no_sources,
    )

    file_size_kb = out_path.stat().st_size / 1024
    print("Done!")
    print("\nExport Summary:")
    print(f"  - Individuals (INDI):  {stats['individuals']:,}")
    print(f"  - Families (FAM):      {stats['families']:,}")
    print(f"  - Source Citations:    {stats['sources']:,}")
    print(f"  - File Size:           {file_size_kb:,.1f} KB ({out_path.stat().st_size:,} bytes)")
    print("==================================================")
    print(f"Ready for review in desktop or online software: {out_path.resolve()}\n")


if __name__ == "__main__":
    main()
