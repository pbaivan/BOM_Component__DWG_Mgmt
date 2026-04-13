from __future__ import annotations

import base64
import os
import urllib.parse


def extract_site_name(target_url: str) -> str:
    parsed = urllib.parse.urlparse(target_url)
    segments = [seg for seg in parsed.path.split("/") if seg]
    lowered = [seg.lower() for seg in segments]
    if "sites" in lowered:
        idx = lowered.index("sites")
        if idx + 1 < len(segments):
            return urllib.parse.unquote(segments[idx + 1])
    return parsed.netloc.split(".")[0] or "SharePoint"


def encode_share_id(target_url: str) -> str:
    encoded = base64.urlsafe_b64encode(target_url.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"u!{encoded}"


def get_target_urls() -> list[str]:
    raw = os.getenv("SHAREPOINT_TARGET_URL", "")
    return [item.strip() for item in str(raw).split(",") if item.strip()]
