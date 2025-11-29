import sys
from pathlib import Path

root = Path(__file__).resolve().parent
src_dir = root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from goetia_bot.app import main  # noqa: E402

if __name__ == "__main__":
    main()
