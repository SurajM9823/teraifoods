from allauth.account.decorators import verified_email_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@never_cache
@verified_email_required
@require_safe
def profile(request):
    return render(request, "customers/profile.html")
