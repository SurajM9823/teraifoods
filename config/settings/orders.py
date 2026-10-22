import os
ORDER_PAYMENT_MODE = os.getenv('ORDER_PAYMENT_MODE', 'stripe')

# Test mode is mandatory until a separate, explicit production payment rollout.
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_TEST_PUBLISHABLE_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_TEST_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_TEST_WEBHOOK_SECRET', '')
ORDER_PUBLIC_ORIGIN = os.getenv('ORDER_PUBLIC_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
ORDER_RESERVATION_MINUTES = 30
ORDER_GUEST_ACCESS_DAYS = 30
ORDER_DELIVERY_PIN_REQUIRED = os.getenv('ORDER_DELIVERY_PIN_REQUIRED', 'true').lower() == 'true'
# Zero permits requests for manual review; it does not promise automatic eligibility.
ORDER_RETURN_DAYS = int(os.getenv('ORDER_RETURN_DAYS', '0'))
CHANNEL_LAYERS = {'default': {'BACKEND':'channels_redis.core.RedisChannelLayer',
    'CONFIG':{'hosts':[os.getenv('CHANNEL_REDIS_URL', 'redis://127.0.0.1:6379/2')],
              'capacity':100, 'expiry':60}}}
CELERY_BEAT_SCHEDULE = {
    'order-outbox': {'task':'orders.tasks.dispatch_pending', 'schedule':30.0},
    'expire-orders': {'task':'orders.tasks.expire_reservations', 'schedule':60.0},
}
