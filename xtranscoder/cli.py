from __future__ import annotations
import argparse
from pathlib import Path
from .core import detect_format, read, write

def main() -> None:
    parser = argparse.ArgumentParser(description="Convert XRD files; input type is detected automatically.")
    parser.add_argument("input", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--format", default="0.csv", choices=["0.csv","1.xrdml","3.csv","4.csv","5.dat","6.xy","7.txt"])
    args = parser.parse_args()
    pattern=read(args.input); write(pattern,args.output,args.format)
    print(f"Detected {pattern.source_format}; wrote {len(pattern.points)} points to {args.output}")

if __name__ == "__main__": main()
