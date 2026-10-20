import uuid
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from catalog.models import Product
from catalog.services import adjust_stock


class Command(BaseCommand):
    help = "Confirm stock for unconfirmed products or all products so they can be purchased."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantity",
            type=int,
            default=50,
            help="Initial stock units to assign (default: 50).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Also top up products that already have confirmed stock.",
        )
        parser.add_argument(
            "--product-id",
            type=int,
            help="Target a specific product ID.",
        )
        parser.add_argument(
            "--reason",
            default="Initial inventory count confirmation",
            help="Reason recorded in stock audit history.",
        )

    def handle(self, *args, **options):
        quantity = options["quantity"]
        reason = options["reason"]
        User = get_user_model()
        actor = User.objects.filter(is_staff=True).first()

        queryset = Product.objects.all().order_by("pk")
        if options.get("product_id"):
            queryset = queryset.filter(pk=options["product_id"])
        elif not options.get("all"):
            queryset = queryset.filter(stock_confirmed=False)

        count = queryset.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No unconfirmed products found. All products already have confirmed stock!"))
            return

        self.stdout.write(f"Confirming stock ({quantity} units each) for {count} product(s)...")

        confirmed_count = 0
        for product in queryset:
            with transaction.atomic():
                key = f"confirm-stock-{product.pk}-{uuid.uuid4().hex[:8]}"
                if not product.stock_confirmed:
                    adjust_stock(
                        product.pk,
                        quantity,
                        reason=reason,
                        actor=actor,
                        key=key,
                        kind="initial",
                    )
                else:
                    adjust_stock(
                        product.pk,
                        quantity,
                        reason=reason,
                        actor=actor,
                        key=key,
                        kind="manual_increase",
                    )
                confirmed_count += 1
                self.stdout.write(f"  [OK] ID #{product.pk}: {product.name[:40]} -> Stock: {quantity}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully confirmed stock for {confirmed_count} product(s)!"
            )
        )
