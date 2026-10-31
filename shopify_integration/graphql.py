"""Versioned, allowlisted catalogue operations. No publication or order mutations."""
SCOPES_QUERY = '''query IntegrationScopes {
  shop { currencyCode }
  currentAppInstallation { accessScopes { handle } }
}'''
FILES_QUERY = '''query IntegrationFiles($query: String!) {
  files(first: 2, query: $query) { nodes { id fileStatus } }
}'''
FILE_QUERY = '''query IntegrationFile($id: ID!) {
  node(id: $id) { ... on MediaImage { id fileStatus } }
}'''
PRODUCT_SNAPSHOT = '''query IntegrationSnapshot($identifier: ProductIdentifierInput!, $after: String) {
  productByIdentifier(identifier: $identifier) {
    id title handle status descriptionHtml
    metafield(namespace: "teraifoods", key: "django_product_id") { value }
    media(first: 250) { nodes { id status } pageInfo { hasNextPage } }
    variants(first: 100, after: $after) {
      nodes { id price compareAtPrice sku selectedOptions { name value }
        inventoryItem { id tracked measurement { weight { value unit } } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}'''
FILE_CREATE = '''mutation IntegrationFileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id fileStatus }
    userErrors { field code }
  }
}'''
PRODUCT_SET = '''mutation IntegrationDraftSet($input: ProductSetInput!, $identifier: ProductSetIdentifiers) {
  productSet(input: $input, identifier: $identifier, synchronous: true) {
    product { id handle status }
    userErrors { field code }
  }
}'''

PUBLICATIONS_QUERY = '''query IntegrationPublications {
 publications(first: 50) { nodes { id name } pageInfo { hasNextPage } }
}'''
PUBLICATION_STATE = '''query IntegrationPublicationState($id: ID!, $publication: ID!) {
 product(id: $id) { id status publishedOnPublication(publicationId: $publication) }
}'''
PRODUCT_ACTIVATE = '''mutation IntegrationActivate($product: ProductUpdateInput!) {
 productUpdate(product: $product) { product { id status } userErrors { field } }
}'''
PUBLISH_PRODUCT = '''mutation IntegrationPublish($id: ID!, $input: [PublicationInput!]!) {
 publishablePublish(id: $id, input: $input) { userErrors { field } }
}'''
UNPUBLISH_PRODUCT = '''mutation IntegrationUnpublish($id: ID!, $input: [PublicationInput!]!) {
 publishableUnpublish(id: $id, input: $input) { userErrors { field } }
}'''
WEBHOOKS_QUERY = '''query IntegrationWebhooks($after: String) {
 webhookSubscriptions(first: 100, after: $after) { nodes { id topic uri } pageInfo { hasNextPage endCursor } }
}'''
WEBHOOK_CREATE = '''mutation IntegrationWebhookCreate($topic: WebhookSubscriptionTopic!, $input: WebhookSubscriptionInput!) {
 webhookSubscriptionCreate(topic: $topic, webhookSubscription: $input) {
  webhookSubscription { id topic uri } userErrors { field }
 }
}'''

_MONEY = '{ shopMoney { amount currencyCode } presentmentMoney { amount currencyCode } }'
_ADDRESS = '{ name phone address1 address2 city province zip countryCodeV2 }'
ORDER_QUERY = '''query IntegrationOrder($id: ID!, $after: String) {
 order(id: $id) {
  id name createdAt updatedAt email phone currencyCode cancelledAt taxesIncluded
  displayFinancialStatus displayFulfillmentStatus
  shippingAddress ADDRESS billingAddress ADDRESS
  currentTotalPriceSet MONEY currentSubtotalPriceSet MONEY currentTotalDiscountsSet MONEY
  currentTotalTaxSet MONEY currentShippingPriceSet MONEY totalRefundedSet MONEY
  totalTipReceivedSet MONEY
  currentTotalDutiesSet MONEY currentTotalAdditionalFeesSet MONEY
  fulfillments(first: 20) { id status trackingInfo { number url } }
  lineItems(first: 50, after: $after) {
   nodes { id name sku quantity currentQuantity variantTitle originalUnitPriceSet MONEY
    variant { id inventoryItem { measurement { weight { value unit } } } }
   }
   pageInfo { hasNextPage endCursor }
  }
 }
}'''.replace('ADDRESS', _ADDRESS).replace('MONEY', _MONEY)
ORDERS_QUERY = '''query IntegrationOrders($query: String!, $after: String) {
 orders(first: 50, query: $query, after: $after, sortKey: UPDATED_AT) {
  nodes { id updatedAt } pageInfo { hasNextPage endCursor }
 }
}'''
