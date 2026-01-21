def detect_platform(url: str) -> dict | None:
    """ALWAYS returns dict or None - NEVER str/tuple"""
    u = url.lower().strip()

    # Adult platforms
    if any(site in u for site in ["pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "youporn.com"]):
        return {"adult": True, "format": "best[filesize<45M]/best"}

    # YouTube
    if "youtube.com" in u or "youtu.be" in u or "youtu.com" in u:
        return {"adult": False, "format": "bestvideo[height<=720]+bestaudio/best[height<=720]"}

    # Social media
    social_keywords = ["instagram.com", "tiktok.com", "facebook.com", "twitter.com", "x.com"]
    if any(kw in u for kw in social_keywords):
        return {"adult": False, "format": "best[filesize<45M]/best"}

    return None  # ✅ CRITICAL: Always dict or None
