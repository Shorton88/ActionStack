"""Isolated regex evaluation; parent enforces a wall-clock timeout."""
import json
import re
import sys

if __name__=='__main__':
    jobs=json.load(sys.stdin)
    print(json.dumps([re.fullmatch(pattern,value) is not None for pattern,value in jobs]))
