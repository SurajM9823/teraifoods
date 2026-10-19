from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.db.models import Count, Q


def get_dashboard_summary(*, user):
    """Bounded queries; no complete user lists loaded into the dashboard."""
    counts = get_user_model().objects.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        staff=Count("pk", filter=Q(is_staff=True, is_active=True)),
    )
    activity = LogEntry.objects.filter(user_id=user.pk).select_related("content_type").order_by("-action_time")[:5]
    return {"user_counts": counts, "recent_activity": activity}
