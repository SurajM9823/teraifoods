from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase,override_settings
from shopify_integration.client import ShopifyError
from shopify_integration.graphql import (PUBLICATIONS_QUERY,PUBLICATION_STATE,PRODUCT_ACTIVATE,
    PUBLISH_PRODUCT,UNPUBLISH_PRODUCT,SCOPES_QUERY,PRODUCT_SET)
from shopify_integration.models import ShopifySyncJob,ShopifyProductMapping
from shopify_integration.publication import prepare_publication,execute_publication
from . import test_draft_sync as draft_fixtures


@override_settings(SHOPIFY_ENABLED=True,SHOPIFY_DRAFT_SYNC_ENABLED=True,SHOPIFY_PUBLICATION_ENABLED=True,
    SHOPIFY_SHOP_DOMAIN='test.myshopify.com',SHOPIFY_MEDIA_ORIGIN='https://media.example.com')
class PublicationTests(TestCase):
    run_job=draft_fixtures.DraftSyncTests.run_job

    def setUp(self):
        draft_fixtures.DraftSyncTests.setUp(self)
        self.targets=set()
        self.shop.publication_ids=['gid://shopify/Publication/1'];self.shop.save()
        patcher=patch('shopify_integration.publication.ShopifyClient',return_value=self.api)
        patcher.start();self.addCleanup(patcher.stop)
        self.assertEqual(self.run_job().status,'succeeded')
        self.api.mutate.reset_mock()

    def query(self,document,variables=None):
        if document==PUBLICATIONS_QUERY:
            return {'publications':{'nodes':[{'id':'gid://shopify/Publication/1','name':'Online Store'}],
                                   'pageInfo':{'hasNextPage':False}}}
        if document==PUBLICATION_STATE:
            return {'product':{'id':self.remote['id'],'status':self.remote['status'],
                'publishedOnPublication':variables['publication'] in self.targets}}
        result=draft_fixtures.DraftSyncTests.query(self,document,variables)
        if document==SCOPES_QUERY:
            result['currentAppInstallation']['accessScopes'].append({'handle':'write_publications'})
        return result

    def mutate(self,document,variables):
        if document==PRODUCT_ACTIVATE:
            self.remote['status']='ACTIVE'
            return {'product':{'id':self.remote['id'],'status':'ACTIVE'}}
        if document in (PUBLISH_PRODUCT,UNPUBLISH_PRODUCT):
            ids={item['publicationId'] for item in variables['input']}
            self.targets.update(ids) if document==PUBLISH_PRODUCT else self.targets.difference_update(ids)
            return {'userErrors':[]}
        active=bool(self.remote and self.remote['status']=='ACTIVE')
        result=draft_fixtures.DraftSyncTests.mutate(self,document,variables)
        if document==PRODUCT_SET and active:
            self.remote['status']='ACTIVE';result['product']['status']='ACTIVE'
        return result

    def publish(self):
        return execute_publication(prepare_publication(self.shop,self.product.pk,operation='publish',reviewed=True).pk)

    def test_sync_never_publishes_without_separate_review(self):
        self.assertFalse(self.targets)
        with self.assertRaisesMessage(ShopifyError,'current_product_review_and_sync_required'):
            prepare_publication(self.shop,self.product.pk,operation='publish')
        self.api.mutate.assert_not_called()

    def test_explicit_publish_activates_and_targets_only_configured_publication(self):
        self.assertEqual(self.publish().status,'succeeded')
        self.assertEqual(self.targets,{'gid://shopify/Publication/1'})
        self.assertEqual(self.remote['status'],'ACTIVE')
        self.assertTrue(ShopifyProductMapping.objects.get().publication_approved)

    def test_unpublish_does_not_archive_and_is_not_reversed_by_sync(self):
        self.publish()
        job=prepare_publication(self.shop,self.product.pk,operation='unpublish')
        self.assertEqual(execute_publication(job.pk).status,'succeeded')
        self.assertFalse(self.targets);self.assertEqual(self.remote['status'],'ACTIVE')
        self.assertEqual(self.run_job().status,'succeeded')
        self.assertFalse(self.targets)

    def test_approved_live_product_can_receive_price_updates_without_republishing(self):
        self.publish();self.api.mutate.reset_mock()
        self.product.regular_price=Decimal('12.00');self.product.save()
        self.assertEqual(self.run_job().status,'succeeded')
        self.assertEqual(self.remote['status'],'ACTIVE')
        self.assertFalse(any(c.args[0] in (PUBLISH_PRODUCT,UNPUBLISH_PRODUCT,PRODUCT_ACTIVATE) for c in self.api.mutate.call_args_list))

    def test_source_change_after_review_blocks_activation(self):
        job=prepare_publication(self.shop,self.product.pk,operation='publish',reviewed=True)
        self.product.name='Changed after review';self.product.save()
        result=execute_publication(job.pk)
        self.assertEqual(result.status,'failed');self.assertEqual(result.error_code,'product_changed_after_publication_review')
        self.api.mutate.assert_not_called()

    def test_failed_publication_never_automatically_unpublishes_archives_or_deletes(self):
        real=self.mutate
        def fail(document,variables):
            if document==PUBLISH_PRODUCT:raise ShopifyError('transport_error')
            return real(document,variables)
        self.api.mutate.side_effect=fail
        self.assertEqual(self.publish().status,'failed')
        self.assertEqual(self.remote['status'],'ACTIVE')
        self.assertFalse(any(c.args[0]==UNPUBLISH_PRODUCT for c in self.api.mutate.call_args_list))

    def test_unpublish_allowed_when_local_product_archived(self):
        self.publish();self.product.is_archived=True;self.product.save()
        job=prepare_publication(self.shop,self.product.pk,operation='unpublish')
        self.assertEqual(execute_publication(job.pk).status,'succeeded')
        self.assertFalse(self.targets)

    def test_publication_permissions_and_targets_required(self):
        staff=get_user_model().objects.create_user('no-publish',is_staff=True)
        with self.assertRaises(PermissionDenied):prepare_publication(self.shop,self.product.pk,operation='publish',reviewed=True,actor=staff)
        self.shop.publication_ids=[];self.shop.save()
        with self.assertRaises(ShopifyError):prepare_publication(self.shop,self.product.pk,operation='publish',reviewed=True)

    def test_admin_requires_confirmation_page_before_queueing_publish(self):
        staff=get_user_model().objects.create_superuser('publication-admin','admin@example.com','testpass')
        self.client.force_login(staff)
        before=ShopifySyncJob.objects.count()
        url='/admin/system/shopify_integration/shopifycatalogueproduct/'
        response=self.client.post(url,{'action':'publish_products','_selected_action':[str(self.product.pk)]})
        self.assertContains(response,'Confirm explicit Shopify publish')
        self.assertEqual(ShopifySyncJob.objects.count(),before)
        self.api.mutate.assert_not_called()
