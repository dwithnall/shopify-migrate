
from vars import *
from secrets import *
from utilities import log_image_error, parse_images
import json

def get_product_by_sku(sku):
    query = """
    query getProductBySku($sku: String!) {
      products(first: 1, query: $sku) {
        edges {
          node {
            id
            variants(first: 1) {
              edges {
                node {
                  sku
                }
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "sku": f"sku:{sku}"
    }
    
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables}
    )
    
    if response.status_code == 200:
        data = response.json()
        products = data.get('data', {}).get('products', {}).get('edges', [])
        if products:
            return products[0]['node']['id']
    return None

def get_product_by_title(title):
    query = """
    query getProductByTitle($title: String!) {
      products(first: 1, query: $title) {
        edges {
          node {
            id
            title
          }
        }
      }
    }
    """
    
    variables = {
        "title": f"title:'{title}'"
    }
    
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables}
    )
    
    if response.status_code == 200:
        data = response.json()
        products = data.get('data', {}).get('products', {}).get('edges', [])
        if products:
            return products[0]['node']['id']
    return None

def get_locations():  
    """Get available locations from Shopify"""
    query = """
    query {
      locations(first: 10) {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query}
    )
    
    if response.status_code == 200:
        data = response.json()
        locations = data.get('data', {}).get('locations', {}).get('edges', [])
        
        # If no active location found, use the first location
        if locations:
            return locations[0].get('node', {}).get('id')
    
    return None


def get_product_image_ids(product_id):
    query = """
    query getMedia($id: ID!) {
      product(id: $id) {
        images(first: 100) {
          edges {
            node {
              id
              originalSrc
            }
          }
        }
      }
    }
    """
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": {"id": product_id}}
    )
    data = response.json()
    image_ids = [
        edge["node"]["id"].split("/")[-1]  # Extract just the numeric ID
        for edge in data["data"]["product"]["images"]["edges"]
    ]
    return image_ids

def delete_images_rest_api(product_id, image_ids):
    for image_id in image_ids:
        url = f"https://{SHOPIFY_STORE}/admin/api/2023-07/products/{product_id.split('/')[-1]}/images/{image_id}.json"
        response = requests.delete(url, headers={
            "X-Shopify-Access-Token": SHOPIFY_API_ACCESS_TOKEN
        })
        if response.status_code == 200:
            print(f"🗑️ Deleted image {image_id}")
        else:
            print(f"❌ Failed to delete image {image_id}: {response.text}")

def delete_all_product_images(product_id):
    image_ids = get_product_image_ids(product_id)
    if not image_ids:
        print("ℹ️ No images to delete.")
        return
    delete_images_rest_api(product_id, image_ids)

def build_variant_input(child, option_names, use_selected_options=True):
    base = {
        "title": child["title"],
        "sku": child["sku"],
        "price": child["price"],
        "inventoryManagement": "SHOPIFY"
    }

    if use_selected_options:
        base["selectedOptions"] = [
            {"name": k, "value": child["variantAttributes"][k]} for k in option_names
        ]
    else:
        for i, key in enumerate(option_names[:3]):
            base[f"option{i+1}"] = child["variantAttributes"][key]
    
    return base

def build_all_variant_inputs(product, use_selected_options=True):
    """
    Given a product object and flag for using selectedOptions or optionN format,
    return a list of ProductVariantInput objects ready for mutation.
    """
    option_names = list(product.get("variantAttributes", {}).keys())
    variant_inputs = []

    for child in product.get("children", []):
        base = {
            "title": child.get("title"),
            "sku": child.get("sku"),
            "price": child.get("price"),
            "inventoryManagement": "SHOPIFY"
        }

        if use_selected_options:
            base["selectedOptions"] = [
                {
                    "name": key,
                    "value": child.get("variantAttributes", {}).get(key, "")
                }
                for key in option_names
            ]
        else:
            # Fall back to option1, option2, option3
            for i, key in enumerate(option_names[:3]):
                base[f"option{i+1}"] = child.get("variantAttributes", {}).get(key, "")

        variant_inputs.append(base)

    return variant_inputs

def create_media(product_id, image_urls, sku=None, name=None):
    """
    Upload images to a product using the productCreateMedia mutation.
    """
    if not image_urls:
        return

    mutation = """
    mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
      productCreateMedia(productId: $productId, media: $media) {
        media {
          alt
          status
          mediaContentType
          ... on MediaImage {
            image {
              originalSrc
            }
          }
        }
        mediaUserErrors {
          field
          message
        }
      }
    }
    """

    media_inputs = [
        {
            "alt": name,
            "originalSource": url,
            "mediaContentType": "IMAGE"
        }
        for url in image_urls
    ]

    variables = {
        "productId": product_id,
        "media": media_inputs
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": mutation, "variables": variables}
    )

    result = response.json()
    errors = result.get("data", {}).get("productCreateMedia", {}).get("mediaUserErrors", [])
    if errors:
        print(f"⚠️ Media Error at line {line_number}: {errors[0]['message']}")
        # Log the error
        log_image_error(sku or '', name or '', errors.length, image_urls, errors[0]['message'], line_number or 'N/A')
    else:
        print(f"✅ Uploaded {len(image_urls)} images to product {product_id}")

def add_variants(parent_id, child_products, parent_product=None):
    DEFAULT_LOCATION_ID = get_locations()
    
    mutation = """
    mutation productVariantsBulkCreate(
      $productId: ID!, 
      $strategy: ProductVariantsBulkCreateStrategy!,
      $variants: [ProductVariantsBulkInput!]!
      ) {
      productVariantsBulkCreate(
        productId: $productId, 
        strategy: $strategy, 
        variants: $variants
      ) {
        productVariants {
          id
          title
          sku
          price
          inventoryQuantity
          selectedOptions {
            name
            value
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    # Create variant inputs for each child product
    variants = []
    
    for child_product in child_products:
        # Get variant attributes
        variant_attributes = child_product.get('variantAttributes', {})
        
        metafields = [
            {
                "namespace": "custom",
                "key": "woocommerce_sku",
                "value": child_product.get('sku', ''),
                "type": "single_line_text_field"
            }
        ]

        if child_product.get('metafields'):
            metafields.extend(child_product.get('metafields'))

        # Create the variant input
        variant = {
            "price": child_product.get('price', '0.00'),
            "inventoryItem": {
                "sku": child_product.get('sku', ''),
                "tracked": True
            },
            "inventoryQuantities": {
                "locationId": DEFAULT_LOCATION_ID,
                "availableQuantity": int(child_product.get('inventoryQuantity', 0))
            },
            "metafields": metafields,
            "optionValues": [
                {
                    "name": name,
                    "optionName": value
                }
                for name, value in variant_attributes.items()
            ]
        }
        
        variants.append(variant)

    variables = {
        "productId": parent_id,
        "strategy": "REMOVE_STANDALONE_VARIANT",
        "variants": variants
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": mutation, "variables": variables}
    )

    result = response.json()
    user_errors = result.get("data", {}).get("productVariantsBulkCreate", {}).get("userErrors", [])
    result_errors = result.get("errors", [])

    print("🎯 Add Variants Response:")
    if user_errors:
        print(f"❌ User Errors creating variants:")
        print(json.dumps(user_errors, indent=2))
    
    if result_errors:
        print(f"❌ Result Errors creating variants:")
        print(json.dumps(result_errors, indent=2))
    
    if not user_errors and not result_errors:
        print(f"✅ Variants created successfully")
        print(json.dumps(result, indent=2))
    
    return result


def create_variable_product(product):
    # Step 1: Create product without variants
    mutation_create_product = """
    mutation productCreate($input: ProductInput!) {
      productCreate(input: $input) {
        product {
          id
          title
          variants(first: 1) {
            edges {
              node {
                id
                price
                inventoryQuantity
              }
            }
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    option_names = list(product["variantAttributes"].keys())

    product_input = {
        "title": product["title"],
        "bodyHtml": product.get("descriptionHtml", ""),
        "vendor": product["vendor"],
        "productType": product["productType"],
        "tags": product["tags"],
        "options": option_names,
        "status": product.get("status", "DRAFT")
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": mutation_create_product, "variables": {"input": product_input}}
    )
    result = response.json()
    print("🎯 Product Create Response:")
    print(json.dumps(result, indent=2))

    errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
    if errors:
        print(f"❌ Errors creating product: {errors[0]['message']}")
        return response, None

    product_id = result["data"]["productCreate"]["product"]["id"]

    # Step 2: Create variants using productVariantCreate
    result = add_variants(product_id, product)


    # Step 3: Upload images
    create_media(product_id, parse_images(product.get("images")), product.get("sku"), product.get("title"))

    return response, product_id


def create_product(product):
    # Create new product
    mutation = """
    mutation productCreate($input: ProductInput!, $media: [CreateMediaInput!]!) {
      productCreate(input: $input, media: $media) {
        product {
          id
          title
          variants(first: 1) {
            edges {
              node {  
                id
                title
              }
            }
          }
          options {
            name
            values
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    # Extract variant attributes if they exist
    variant_attributes = product.get('variantAttributes', {})
    
    # Create options from variant attributes
    options = []
    if variant_attributes:
        for option_name in variant_attributes.keys():
            # Format option values as array of objects with name property
            option_values = []
            for value in variant_attributes[option_name].split(','):
                option_values.append({"name": value.strip()})
                
            options.append({
                "name": option_name, 
                "values": option_values
            })
    
    # Create a default variant with price and inventory
    variants = []
    if product.get('price') or product.get('inventoryQuantity'):
        variant = {
            "price": product.get('price', '0.00'),
            "inventoryManagement": "SHOPIFY",
            "inventoryQuantity": int(product.get('inventoryQuantity', 0)),
            "sku": product.get('sku', '')
        }
        
        # Add option values if we have options
        if options:
            for i, option in enumerate(options):
                option_name = option['name']
                if option_name in variant_attributes:
                    # Get the first value for this option
                    option_values = variant_attributes[option_name].split(',')
                    if option_values:
                        variant[f"option{i+1}"] = option_values[0].strip()
        
        variants.append(variant)
    
    # Process images if they exist
    media = []
    if product.get('images'):
        image_urls = parse_images(product.get('images'))
        for url in image_urls:
            media.append({
                "alt": product.get('title', ''),
                "originalSource": url,
                "mediaContentType": "IMAGE"
            })
    
    # Add metafields
    metafields = [
        {
            "namespace": "custom",
            "key": "woocommerce_sku",
            "value": product.get('sku', ''),
            "type": "single_line_text_field"
        }
    ]
    if product.get('metafields'):
        product_input["metafields"].extend(product.get('metafields'))

    # Build the product input
    product_input = {
        "title": product.get('title', ''),
        "descriptionHtml": product.get('descriptionHtml', ''),
        "vendor": product.get('vendor', ''),
        # "productType": product.get('productType', ''),
        "tags": product.get('tags', []),
        "status": product.get('status', 'ACTIVE'),
        # "productOptions": options,
        # "variants": variants,
        # "media": media,
        "metafields": metafields
    }

    variables = {
        "input": product_input,
        "media": media
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": mutation, "variables": variables}
    )

    result = response.json()
    user_errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
    result_errors = result.get("errors", [])

    print("🎯 Product Create Response:")
    if user_errors:
        print(f"❌ User Errors creating product:")
        print(json.dumps(user_errors, indent=2))
    
    if result_errors:
        print(f"❌ Result Errors creating product:")
        print(json.dumps(result_errors, indent=2))
    
    productId = None
    if not user_errors and not result_errors:
        productId = result.get("data", {}).get("productCreate", {}).get("product", {}).get("id")
        print(f"✅ Product created successfully (productId: {productId})")
    return result, productId

def update_product(product):
  # Update existing product
  mutation = """
  mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
      product {
          id
          title
      }
      userErrors {
          field
          message
      }
      }
  }
  """

  variables = {
      "input": {
          "title": product.get('title'),
          "bodyHtml": product.get('descriptionHtml'),
          "status": product.get('status'),
          "vendor": product.get('vendor'),
          "productType": product.get('productType'),
          "tags": product.get('tags'),
          "metafields": product.get('metafields'),
          "published": product.get('published'),
          "variants": [{
              "price": product.get('price', '0.00'),
              "inventoryManagement": "SHOPIFY",
              "sku": product.get('sku', '')
          }]
      }
  }
  
  response = requests.post(
      GRAPHQL_URL,
      headers=HEADERS,
      json={"query": mutation, "variables": variables}
  )

  result = response.json()
  errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
  if errors:
      print(f"❌ Errors creating product: {errors[0]['message']}")
  
  if not errors and SYNC_IMAGES:
      delete_all_product_images(product.get('shopifyExistingId'))
      create_media(product.get('shopifyExistingId'), parse_images(product.get('images')), product.get('sku'), product.get('title'))

  return response


def set_inventory_quantity(product_id, inventory_item_id, location_id, quantity):
  # Update existing product
  mutation = """
  mutation adjustInventory($input: InventoryAdjustQuantityInput!) {
    inventoryAdjustQuantity(input: $input) {
      inventoryLevel {
        id
        available
      }
      userErrors {
        field
        message
      }
    }
  }
  """

  variables = {
      "input": {
          "inventoryItemId": inventory_item_id,
          "locationId": location_id,
          "availableDelta": quantity
      }
  }
  
  response = requests.post(
      GRAPHQL_URL,
      headers=HEADERS,
      json={"query": mutation, "variables": variables}
  )

  result = response.json()
  errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
  if errors:
      print(f"❌ Errors creating product: {errors[0]['message']}")
  
  return response


def get_publication_ids():
    query = """
    {
      publications(first: 10) {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query}
    )
    data = response.json()
    return {
        edge["node"]["name"]: edge["node"]["id"]
        for edge in data["data"]["publications"]["edges"]
    }

def adjust_inventory_quantity(inventory_item_id, location_id, delta):

    mutation = """
    mutation adjustInventory($input: InventoryAdjustQuantityInput!) {
      inventoryAdjustQuantity(input: $input) {
        inventoryLevel {
          id
          available
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    variables = {
        "input": {
            "inventoryItemId": inventory_item_id,
            "availableDelta": delta,
            "locationId": location_id
        }
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": mutation, "variables": variables}
    )

    result = response.json()
    errors = result.get("data", {}).get("productVariantCreate", {}).get("userErrors", [])
    if errors:
        print(f"❌ Errors creating variant: {errors[0]['message']}")
    
    return response

def publish_collection(collection_id, publication_ids):
    """
    Publish a collection to the Shopify online store.
    """
    # Extract the numeric ID from the GraphQL ID
    numeric_id = collection_id.split('/')[-1]
    
    # Use the REST API to publish the collection to the online store
    publish_url = f"https://{SHOPIFY_STORE}/admin/api/2023-07/smart_collections/{numeric_id}.json"

    # Update the collection to make it published to the online store
    update_data = {
        "smart_collection": {
            "published": True,
            "published_scope": "web"  # "web" = Online Store; "global" = all channels
        }
    }
    
    update_response = requests.put(
        publish_url,
        headers={"X-Shopify-Access-Token": SHOPIFY_API_ACCESS_TOKEN},
        json=update_data
    )

    # Update the collection to make it published to the online store
    update_data = {
        "smart_collection": {
            "published": True,
            "published_scope": "global"  # "web" = Online Store; "global" = all channels
        }
    }
    
    update_response = requests.put(
        publish_url,
        headers={"X-Shopify-Access-Token": SHOPIFY_API_ACCESS_TOKEN},
        json=update_data
    )

    if update_response.status_code == 200:
        print(f"📢 Published collection to online store")
    else:
        print(f"❌ Failed to publish collection to online store: {update_response.text}")

def create_smart_collection(title, publication_ids):
    """Create a smart collection based on a tag"""
    mutation = """
    mutation collectionCreate($input: CollectionInput!) {
      collectionCreate(input: $input) {
        collection {
          id
          title
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    
    variables = {
        "input": {
            "title": title,
            "ruleSet": {
                "appliedDisjunctively": False,
                "rules": [
                    {
                        "column": "TAG",
                        "relation": "EQUALS",
                        "condition": title
                    }
                ]
            }
        }
    }
    
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": mutation, "variables": variables}
    )
    
    if response.status_code == 200:
        data = response.json()
        result = data.get('data', {}).get('collectionCreate', {})
        errors = data.get('errors', [])
        collection = result.get('collection', {})
        user_errors = result.get('userErrors', [])
        
        if errors:
            print(f"❌ Errors creating collection '{title}':")
            for error in errors:
                print(f"  - {error['message']}")
        elif user_errors:
            print(f"❌ Errors creating collection '{title}':")
            for error in user_errors:
                print(f"  - {error['message']}")
        else:
            collection_id = collection.get('id', '')
            publish_collection(collection_id, publication_ids)
            print(f"✅ Created collection: {title} (ID: {collection_id})")

    else:
        print(f"❌ Failed to create collection '{title}'")
        print(response.status_code, response.text)
