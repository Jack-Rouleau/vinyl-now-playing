"""Provider URL policy shared by recognition, caching, and album identity."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


def artwork_candidates(source: str) -> list[str]:
    url = urlsplit(source)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        return []
    candidates = []
    if url.hostname.endswith(".mzstatic.com"):
        size = re.search(r"/(\d+)x(\d+)((?:cc|bb)\.(?:jpg|jpeg|png|webp))$", url.path, re.I)
        if size and (int(size[1]), int(size[2])) != (1200, 1200):
            path = url.path[: size.start()] + "/1200x1200" + size[3]
            candidates.append(urlunsplit(url._replace(path=path)))
    return list(dict.fromkeys([*candidates, source]))


def safe_artwork_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        url = urlsplit(value)
        if (
            url.scheme in ("http", "https")
            and url.hostname
            and not url.username
            and not url.password
        ):
            return value
    except ValueError:
        pass
    return None


def artwork_identity(source: str) -> str:
    url = urlsplit(source)
    if url.hostname and url.hostname.endswith(".mzstatic.com"):
        return "apple:" + re.sub(
            r"/\d+x\d+(?:cc|bb)\.(?:jpg|jpeg|png|webp)$", "", url.path, flags=re.I
        )
    return urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path, url.query, ""))
