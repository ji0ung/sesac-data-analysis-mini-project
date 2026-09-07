#!/usr/bin/env python3
"""Validation-connected calibration entry. No authorization is issued by STEP 2.9-I."""
import argparse,json
from pathlib import Path
def require_authorization(path):
 p=Path(path)
 if not p.is_file():raise PermissionError('calibration authorization missing')
 a=json.loads(p.read_text(encoding='utf8'))
 if a.get('calibration_authorized') is not True:raise PermissionError('calibration not authorized')
 return a
def main():
 p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);a=p.parse_args();require_authorization(a.authorization)
 raise PermissionError('approved v02 generator hard-blocks calibration mode; generator revision approval required')
if __name__=='__main__':main()
