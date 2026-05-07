"""
pytest 把 .app/ 和 仓库根加到 sys.path，这样 test 里可以 `from publish import ...`
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / ".app"

for p in (str(ROOT), str(APP)):
    if p not in sys.path:
        sys.path.insert(0, p)
