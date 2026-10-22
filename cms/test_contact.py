from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client
from .models import ContactSettings, FAQItem, ContactHub, ContactInquiry


class ContactTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_seed_preserves_content_and_admin_edits(self):
        self.assertEqual(FAQItem.objects.count(), 8)
        self.assertEqual(ContactHub.objects.count(), 4)
        settings = ContactSettings.objects.get(pk=1)
        settings.phone = '+44 1234567890'
        settings.save()
        faq = FAQItem.objects.first()
        faq.answer = 'Edited answer'
        faq.save()
        import_module('cms.migrations.0005_contact_content').seed(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        settings.refresh_from_db()
        faq.refresh_from_db()
        self.assertEqual(settings.phone, '+44 1234567890')
        self.assertEqual(faq.answer, 'Edited answer')
        self.assertFalse(ContactInquiry.objects.exists())

    def test_page_reads_published_content_and_escapes_it(self):
        FAQItem.objects.update(is_active=False)
        FAQItem.objects.create(question='Dynamic question', answer='<script>bad()</script>')
        ContactHub.objects.update(is_active=False)
        ContactHub.objects.create(name='Dynamic hub', tag='Hub', legend='New location', description='<script>bad()</script>', latitude=52, longitude=-1)
        settings = ContactSettings.objects.get(pk=1)
        settings.facebook_url = 'https://facebook.com/teraiexample'
        settings.save()
        response = self.client.get('/contact/')
        self.assertContains(response, 'Dynamic question')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertContains(response, 'New location')
        self.assertContains(response, settings.facebook_url)
        self.assertNotContains(response, 'When will my grocery order be delivered?')

    def test_enquiry_validation_persistence_throttling_and_csrf(self):
        data = dict(name='Customer', email='customer@example.com', phone='07946091234', topic='other', message='Please help with my order.')
        self.assertEqual(self.client.post('/api/contact/inquiries/', {**data, 'topic': 'invalid'}).status_code, 400)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/contact/inquiries/', data).status_code, 403)
        self.assertEqual(self.client.post('/api/contact/inquiries/', data).status_code, 201)
        self.assertEqual(ContactInquiry.objects.get().message, data['message'])
        self.assertEqual(self.client.post('/api/contact/inquiries/', data).status_code, 429)

    def test_admin_can_manage_contact_content_and_enquiry_status(self):
        user = get_user_model().objects.create_superuser(username='contactadmin', email='admin@example.com', password='test-password')
        self.client.force_login(user)
        for model in ('contactsettings', 'faqitem', 'contacthub', 'contactinquiry'):
            self.assertEqual(self.client.get('/admin/system/cms/' + model + '/').status_code, 200)
        inquiry = ContactInquiry.objects.create(name='Customer', email='customer@example.com', message='Help')
        response = self.client.post(f'/admin/system/cms/contactinquiry/{inquiry.pk}/change/', {'status': 'resolved', 'admin_notes': 'Handled by support', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, 'resolved')
