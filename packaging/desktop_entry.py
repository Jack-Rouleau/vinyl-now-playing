"""Frozen executable entry. Divert multiprocessing children before GUI imports."""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from now_playing.desktop import main

    raise SystemExit(main())
