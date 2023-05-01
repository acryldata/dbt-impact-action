import sys
import pathlib

here = pathlib.Path(__file__).parent
src = here.parent / "src"

sys.path.insert(0, str(src))
