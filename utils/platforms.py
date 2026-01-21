import re

PLATFORMS = {
    "youtube": {
        "patterns": [
            r"(youtube\.com/watch)",
            r"(youtu\.be/)",
            r"(youtube\.com/shorts)"
        ],
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best"
    },
    "instagram": {
        "patterns": [
            r"(instagram\.com/p/)",
            r"(instagram\.com/reel/)"
        ],
        "format": "best[ext=mp4]/best"
    },
    "tiktok": {
        "patterns": [
            r"(tiktok\.com/)"
        ],
        "format": "best[ext=mp4]/best"
    },
    "twitter": {
        "patterns": [
            r"(twitter\.com/)",
            r"(x\.com/)"
        ],
        "format": "best[ext=mp4]/best"
    },
    "facebook": {
        "patterns": [
            r"(facebook\.com/)",
            r"(fb\.watch/)"
        ],
        "format": "best[ext=mp4]/best"
    }
}

def detect_platform(url: str):
    for name, data in PLATFORMS.items():
        for p in data["patterns"]:
            if re.search(p, url, re.IGNORECASE):
                return name, data["format"]
    return None, None
