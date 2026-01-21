from urllib.parse import urlparse

ADULT = {
    "pornhub.org", "xvideos.com", "xnxx.com", "xhamster44.desi", "youporn.com"
}

def is_adult(url):
    return urlparse(url).netloc.replace("www.", "https") in ADULT
