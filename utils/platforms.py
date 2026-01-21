def detect_platform(url: str):
    """Returns dict or None - NEVER tuple/str"""
    u = url.lower()

    # Adult sites
    adult_sites = ("pornhub", "xvideos", "xnxx", "xhamster", "youporn")
    if any(x in u for x in adult_sites):
        return {"adult": True, "format": "best[filesize<45M]/best"}

    # YouTube
    if "youtube" in u or "youtu.be" in u:
        return {"adult": False, "format": "bestvideo[height<=720]+bestaudio/best[height<=720]"}

    # Social media
    social = ("instagram", "tiktok", "facebook", "twitter", "x.com")
    if any(x in u for x in social):
        return {"adult": False, "format": "best[filesize<45M]/best"}

    return None  # ✅ Always dict or None
