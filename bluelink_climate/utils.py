from urllib.parse import urlparse

def get_base_host(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc