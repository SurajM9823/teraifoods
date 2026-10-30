from urllib.parse import urlsplit
from django.conf import settings
from .client import ShopifyClient, ShopifyError
from .graphql import WEBHOOKS_QUERY, WEBHOOK_CREATE, SCOPES_QUERY
from .webhooks import TOPICS


def setup_webhooks(connection, *, apply=False):
    origin = settings.ORDER_PUBLIC_ORIGIN.rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path:
        raise ShopifyError('public_https_webhook_origin_required')
    target = origin + '/api/shopify/webhook/'
    client = ShopifyClient(connection)
    scopes = {s['handle'] for s in client.query(SCOPES_QUERY)['currentAppInstallation']['accessScopes']}
    if 'read_orders' not in scopes:
        raise ShopifyError('read_orders_scope_required')
    existing, after = set(), None
    for _ in range(20):
        page = client.query(WEBHOOKS_QUERY,{'after':after})['webhookSubscriptions']
        existing.update((row['topic'],row['uri']) for row in page['nodes'])
        if not page['pageInfo']['hasNextPage']:
            break
        after = page['pageInfo']['endCursor']
    else:
        raise ShopifyError('webhook_pagination_incomplete')
    plan = []
    for topic in TOPICS:
        enum = topic.upper().replace('/','_')
        missing = (enum,target) not in existing
        plan.append({'topic':topic,'uri':target,'action':'create' if missing else 'unchanged'})
        if apply and missing:
            client.mutate(WEBHOOK_CREATE,{'topic':enum,'input':{'uri':target,'format':'JSON'}})
    return plan
