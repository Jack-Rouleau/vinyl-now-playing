"""Run from a source download without installing tools globally."""

from multiprocessing import freeze_support

from bootstrap import main

if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
