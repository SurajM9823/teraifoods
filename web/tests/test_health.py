from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase


class HealthTests(TestCase):
    def test_database_readiness(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_unavailable_database_does_not_leak_details(self):
        with patch('web.views.connection.cursor', side_effect=DatabaseError('private details')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
