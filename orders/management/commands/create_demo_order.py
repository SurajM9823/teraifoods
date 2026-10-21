import uuid
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand, CommandError
from catalog.models import Product
from orders.services import create_order
from orders.payments import demo_enabled, confirm_demo


class Command(BaseCommand):
    help = 'Create a clearly labelled local demo order; optionally simulate payment confirmation.'

    def add_arguments(self, parser):
        parser.add_argument('--product', type=int)
        parser.add_argument('--quantity', type=int, default=1)
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        if not demo_enabled():
            raise CommandError('Requires DEBUG and ORDER_PAYMENT_MODE=demo. This command cannot create production payments.')
        products=Product.objects.filter(is_published=True,is_active=True,is_archived=False,stock_confirmed=True,stock__gte=options['quantity'])
        if options['product']:
            products=products.filter(pk=options['product'])
        product=products.first()
        if not product:
            raise CommandError('No available product. Configure local sample inventory first.')
        order=create_order(AnonymousUser(),'local-demo-command',{
            'email':'demo@example.invalid',
            'address':{'name':'Local demo customer','phone':'07700900123','line1':'1 Example Street',
                       'city':'London','postcode':'SW1A 1AA','instructions':'LOCAL DEMO ONLY — do not dispatch'},
            'items':[{'product_id':product.pk,'quantity':options['quantity']}]},uuid.uuid4().hex)
        if options['confirm']:
            confirm_demo(order.pk)
        self.stdout.write(f'{order.number}: local demo, no money charged. Admin: /admin/orders/{order.public_id}/')
