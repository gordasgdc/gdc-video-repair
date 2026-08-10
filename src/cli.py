#!/usr/bin/env python3
"""
GDC Video Repair — linie de comanda.

Utilizare:
    python3 cli.py --corrupt fisier_corupt.mp4 --reference fisier_sanatos.mp4 --output reparat.mp4
"""

import argparse
import os
import sys

import repair_engine


def main():
    parser = argparse.ArgumentParser(
        description="Repara fisiere video MP4/MOV corupte, folosind un fisier de referinta sanatos "
                    "(filmat cu aceeasi camera si aceleasi setari)."
    )
    parser.add_argument("--corrupt", "-c", required=True, help="Calea catre fisierul corupt")
    parser.add_argument("--reference", "-r", required=False, default=None,
                         help="Calea catre fisierul de referinta sanatos (necesar doar daca remuxarea rapida esueaza)")
    parser.add_argument("--output", "-o", required=True, help="Calea unde se salveaza fisierul reparat")
    args = parser.parse_args()

    if not os.path.isfile(args.corrupt):
        print(f"EROARE: fisierul corupt nu exista: {args.corrupt}")
        sys.exit(1)
    if args.reference and not os.path.isfile(args.reference):
        print(f"EROARE: fisierul de referinta nu exista: {args.reference}")
        sys.exit(1)

    def report(msg):
        print(f"-> {msg}")

    result = repair_engine.repair(args.corrupt, args.reference, args.output, progress_callback=report)

    print()
    if result.success:
        print(f"REUSIT ({result.method_used}): {result.message}")
        print(f"Fisier salvat la: {result.output_path}")
        sys.exit(0)
    else:
        print(f"EȘUAT: {result.message}")
        sys.exit(2)


if __name__ == "__main__":
    main()
