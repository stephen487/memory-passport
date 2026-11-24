"""Put the kit root on sys.path so tests can import base/."""
import pathlib
import sys

KIT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))
