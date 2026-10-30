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
