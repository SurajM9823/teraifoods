from .models import ContactSettings


def contact_settings(request):
    """Provides contact_info globally to all templates."""
    try:
        return {'contact_info': ContactSettings.get_solo()}
    except Exception:
        return {'contact_info': None}
