from django.core.management.base import BaseCommand
from cms.models import ContactSettings, FAQItem, ContactInquiry


class Command(BaseCommand):
    help = 'Seeds initial ContactSettings, FAQ items, and sample inquiries if not already present.'

    def handle(self, *args, **options):
        # 1. Contact Settings
        settings = ContactSettings.get_solo()
        settings.phone = "+44 20 7946 0912"
        settings.operating_hours = "24/7 Support"
        settings.whatsapp_number = "+447700900077"
        settings.whatsapp_title = "WhatsApp Fast Support"
        settings.whatsapp_subtitle = "Chat live with dispatch rep"
        settings.support_email = "support@teraifood.co.uk"
        settings.support_email_sla = "< 2 HR SLA"
        settings.support_email_subtext = "Orders, tracking, returns & refunds"
        settings.wholesale_email = "wholesale@teraifood.co.uk"
        settings.wholesale_email_subtext = "Bulk purchase orders & commercial B2B"
        settings.office_title = "London HQ & Central Depot"
        settings.office_address = "Unit 4B Peninsula Park, London SE10 0ER, UK"
        settings.social_heading = "Social Channels"
        settings.social_badge = "CONNECT"
        settings.social_text = "Follow us for new harvest arrivals, seasonal promotions, and rapid customer messaging."
        settings.facebook_url = "https://www.facebook.com/"
        settings.twitter_url = "https://www.twitter.com/"
        settings.instagram_url = "https://www.instagram.com/"
        settings.linkedin_url = "https://www.linkedin.com/"
        settings.map_badge = "4 HUBS ACTIVE"
        settings.map_subtitle = "Temperature-controlled fleet operates out of all 4 key hubs to guarantee next-day delivery across mainland UK."
        settings.save()
        self.stdout.write(self.style.SUCCESS("ContactSettings seeded."))

        # 2. Seed FAQs
        initial_faqs = [
            (
                1,
                "When will my grocery order be delivered?",
                "Orders placed before 1:00 PM (Monday through Friday) are packed same-day and delivered next day across mainland UK. Standard delivery timeline is 24 to 48 hours with real-time 1-hour carrier tracking windows via SMS."
            ),
            (
                2,
                "How do you guarantee fresh produce cold-chain?",
                "All perishable goods are packed in 100% recyclable wool-cool thermal liners with dry food-grade frozen gel chill packs. Internal parcel temperatures are maintained strictly below 4°C for up to 48 hours in transit."
            ),
            (
                3,
                "What happens if an item is damaged or missing?",
                "We offer an unconditional 100% Freshness Guarantee. Take a quick photo and email support@teraifood.co.uk or message our WhatsApp line. We issue an immediate refund or dispatch a priority replacement within 2 hours."
            ),
            (
                4,
                "Can businesses place wholesale or bulk trade orders?",
                "Yes! We supply restaurants, caterers, grocery retailers, and institutions with commercial discounts and pallet dispatch. Use our navbar Bulk Order button or choose \"Wholesale & Bulk Quote\" in the inquiry form."
            ),
            (
                5,
                "Which payment methods and currencies do you accept?",
                "We accept all major UK debit/credit cards (Visa, Mastercard, Amex), PayPal, Apple Pay, and Google Pay. All transactions are securely processed in GBP (£) with end-to-end 256-bit SSL encryption."
            ),
            (
                6,
                "How can I track my live order dispatch status?",
                "Visit our Track Order page and enter your 5-digit Order ID and billing email. You will see courier assignments, dispatch timestamps, and live route status."
            ),
            (
                7,
                "Do you ship to Scotland, Wales & Northern Ireland?",
                "Yes. Ambient pantry goods and spices ship to all UK postcodes including Highlands and Islands. Chilled produce delivers next-day across central Scotland and all of Wales through our Glasgow and Midlands hubs."
            ),
            (
                8,
                "Are your Himalayan spices certified organic and natural?",
                "Every spice blend, herb, and grain lot is ethically sourced directly from smallholder Himalayan farms and independently batch-tested in the UK for zero synthetic pesticides, heavy metals, and artificial preservatives."
            ),
        ]

        for order, q, a in initial_faqs:
            FAQItem.objects.get_or_create(
                question=q,
                defaults={"answer": a, "order": order, "is_active": True}
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(initial_faqs)} FAQs."))

        # 3. Seed a couple of demo inquiries if none exist
        if not ContactInquiry.objects.exists():
            ContactInquiry.objects.create(
                name="David Campbell",
                email="david.campbell@example.co.uk",
                phone="+44 7700 900118",
                topic="order-status",
                message="Hi team, I placed order #10842 yesterday morning. Could you confirm if the cold-chain parcel has been dispatched from the London Central depot?",
                status="new",
                admin_notes=""
            )
            ContactInquiry.objects.create(
                name="Sita Gurung",
                email="sita.gurung@himalayandelight.co.uk",
                phone="+44 7700 900542",
                topic="wholesale-quote",
                message="We are looking for monthly pallet delivery of Himalayan Basmati Rice (500kg) and Cold-Pressed Mustard Oil to our Reading restaurant. Please provide your wholesale tier rate sheet.",
                status="in_progress",
                admin_notes="Sent initial wholesale catalog via email. Awaiting reply on delivery access."
            )
            self.stdout.write(self.style.SUCCESS("Seeded sample ContactInquiries."))
