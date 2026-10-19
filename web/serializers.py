"""Explicit JSON representations without adding an unused REST framework."""
from django.urls import reverse


def serialize_page(page):
    return {"slug": page.key, "url": reverse(f"web:{page.key}")}
