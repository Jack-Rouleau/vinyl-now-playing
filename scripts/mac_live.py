"""Compatibility entry point; setup lives in the shared bootstrap."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bootstrap import main  # noqa: E402

if __name__ == "__main__":
    config = ROOT / "config.mac.generated.toml"
    args = (["--config", str(config)] if config.exists() else []) + sys.argv[1:]
    raise SystemExit(main(args))
