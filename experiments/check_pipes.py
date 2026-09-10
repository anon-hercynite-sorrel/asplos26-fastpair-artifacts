#!/usr/bin/env python3
"""Check raw boost evidence, selection, clock acceptance and the submitted five-bin figure."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'figures'))
from pipes_data import load, CAMPAIGN

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true',help='Validate against the accepted submitted values (default).')
    ap.add_argument('--campaign',type=Path,default=CAMPAIGN)
    ap.add_argument('--output',type=Path,help='Optional regenerated direction JSON; no archived files are changed.')
    args=ap.parse_args()
    try:
        accepted, directions=load(args.campaign)
        if args.output:
            args.output.write_text(json.dumps(directions,indent=2)+'\n')
        for chip, value in accepted.items():
            print(f'{chip}: validated {value["winner"]}; {len(value["cells"])} winner/recommended cells')
        print('PASS: five devices, 40 accepted launches; selection, byte checks, clocks, elapsed denominators, five-bin conservation and submitted values.')
    except (ValueError, AssertionError, OSError, KeyError) as error:
        print(f'FAIL: pipes: {error}',file=sys.stderr)
        return 1
    return 0
if __name__=='__main__':
    raise SystemExit(main())
