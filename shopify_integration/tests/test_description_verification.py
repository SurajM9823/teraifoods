from django.test import SimpleTestCase

from shopify_integration.draft_sync import description_tokens
from shopify_integration.graphql import PRODUCT_ACTIVATE


class DescriptionVerificationTests(SimpleTestCase):
    def test_shopify_entity_serialization_is_equivalent(self):
        self.assertEqual(description_tokens('<p>Pepsi&#x27;s &amp; tea &quot;box&quot;<br>Fresh</p>'),
                         description_tokens('<p>Pepsi\'s &amp; tea "box"<br/>Fresh</p>\n'))

    def test_description_text_changes_are_rejected(self):
        self.assertNotEqual(description_tokens('<p>Rice 1kg</p>'), description_tokens('<p>Rice 5kg</p>'))

    def test_encoded_markup_is_not_equivalent_to_real_markup(self):
        self.assertNotEqual(description_tokens('<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>'),
                            description_tokens('<p><script>alert(1)</script></p>'))

    def test_html_attributes_and_structure_still_matter(self):
        self.assertNotEqual(description_tokens('<p>Rice<br>Fresh</p>'), description_tokens('<p>Rice Fresh</p>'))
        self.assertNotEqual(description_tokens('<p class="one">Rice</p>'), description_tokens('<p class="two">Rice</p>'))

    def test_activation_uses_generic_user_error_fields(self):
        self.assertIn('userErrors { field }', PRODUCT_ACTIVATE)
        self.assertNotIn('field code', PRODUCT_ACTIVATE)
