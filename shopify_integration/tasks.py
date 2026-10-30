from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from .draft_sync import execute_draft
from .models import ShopifySyncJob


@shared_task
def run_draft_job(job_id):
    job = execute_draft(job_id)
    return {'id': job.pk, 'status': job.status, 'error_code': job.error_code}


@shared_task
def dispatch_draft_jobs():
    pending = ShopifySyncJob.objects.filter(operation='draft_sync').filter(
        Q(status='pending') | Q(status='retry', next_retry_at__lte=timezone.now()))
    for pk in pending.order_by('pk').values_list('pk', flat=True)[:20]:
        run_draft_job.apply_async(args=[pk], queue='shopify')
