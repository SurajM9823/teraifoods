"""Application operations, kept separate from request handling and reads."""
from web.selectors import list_pages
from web.serializers import serialize_page


def build_page_directory():
    """Build the public route directory from the approved page registry."""
    return {"pages": [serialize_page(page) for page in list_pages()]}
