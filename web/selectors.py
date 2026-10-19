"""Read-only page lookup; future catalog reads and cache boundaries belong here."""
from web.pages import PAGES


def get_page(key):
    return PAGES.get(key)


def list_pages():
    return tuple(PAGES.values())
