#!/usr/bin/env python3
"""Run the original-296 analysis and submission pipeline with one command."""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db',type=Path,required=True); p.add_argument('--output-dir',type=Path,required=True); a=p.parse_args()
    root=a.output_dir.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f'Output directory must be empty: {root}')
    root.mkdir(parents=True,exist_ok=True)
    scripts=Path(__file__).resolve().parent; analysis=root/'analysis'; submission=root/'submission'
    subprocess.run([sys.executable,str(scripts/'analyze_original_296.py'),'--db',str(a.db.resolve()),'--output-dir',str(analysis)],check=True)
    subprocess.run([sys.executable,str(scripts/'build_submission_report.py'),'--analysis-dir',str(analysis),'--output-dir',str(submission)],check=True)
    print(root)
if __name__=='__main__': main()
