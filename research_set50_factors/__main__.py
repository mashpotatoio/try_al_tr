from pathlib import Path
import sys
from .runner import run,verify

if __name__ == "__main__":
    if len(sys.argv)==2 and sys.argv[1]=="run":run()
    elif len(sys.argv)==3 and sys.argv[1]=="verify":print(verify(Path(sys.argv[2])))
    else:raise SystemExit("Usage: python -m research_set50_factors run | verify <result-directory>")
