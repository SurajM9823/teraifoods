from .models import ContactSettings


def contact_settings(request):
    return {'contact_info': ContactSettings.objects.filter(pk=1).first() or ContactSettings()}
