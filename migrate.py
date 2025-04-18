import pandas as pd

import time
from spUtilities import delete_all_product_images, create_media
from utilities import parse_tags, open_log_files, format_description, check_variant, check_parent, parse_decade, process_categories, process_attributes
from spUtilities import get_product_by_sku, get_locations, get_publication_ids, create_product, create_variable_product, update_product, create_smart_collection, add_variants
from vars import *
from keys import *
from utilities import get_child_products, check_parent, add_child_product

def resync_images(image_field, product_id, sku=None, name=None):
    if not image_field:
        return

    image_urls = [url.strip() for url in image_field.split(",") if url.strip()]
    if not image_urls:
        return

    # First remove all existing images
    delete_all_product_images(product_id)
    
    # Then upload new images
    create_media(product_id, image_urls, sku=sku, name=name, line_number=line_number)


def transform_product(row, parent_product=None):
    existing_product_id = get_product_by_sku(row.get('SKU', ''))

    # Process categories into unique tags and get designer name
    categories = row.get('Categories', '')
    tag_list, category_designer = process_categories(categories)
    
    # Process attributes and get dimensions and designer name
    attr_tags, dimension_metafields, attr_designer, product_attributes, variant_attributes = process_attributes(row, parent_product)
    
    # Determine the vendor (designer name)
    vendor = row.get('Brand', 'Vampt Vintage Design')
    
    # Use designer name from attributes or categories if available
    if attr_designer:
        ALL_CATEGORIES.add(attr_designer)
        vendor = attr_designer
    elif category_designer:
        vendor = category_designer
    
    # Get unique tags
    unique_tags = parse_tags(tag_list, attr_tags)
    
    # Get stock value, defaulting to 0 if empty
    stock_count = row.get('Stock', '')
    if not stock_count:
        stock_count = '0'
    
    # Get regular price, defaulting to 0.00 if empty
    regular_price = row.get('Regular price', '')
    if not regular_price:
        regular_price = '0.00'

    # Check if this is a variant
    parent_product_id = None
    if check_variant(row):
        parent_product_id = get_product_by_sku(row.get('Parent', ''))


    # Format description with proper HTML tags
    description = format_description(row.get('Short description', ''), product_attributes)

    # Set product status based on WooCommerce Published column
    published_value = row.get('Published', '0')
    status = ("ACTIVE" if published_value == '1' else "DRAFT")
    
    product = {
        "title": row.get('Name'),
        "shopifyExistingId": existing_product_id,
        "shopifyParentId": parent_product_id,
        "isNew": not existing_product_id,
        "isParent": check_parent(row),
        "isVariant": check_variant(row),
        "sku": row.get('SKU'),
        "descriptionHtml": description,
        "vendor": vendor,
        "productType": row.get('Type', 'Default'),
        "price": regular_price,
        "inventoryQuantity": stock_count, 
        "tags": unique_tags,
        "variantAttributes": variant_attributes,
        "status": status,
        "metafields": dimension_metafields,
        "images": row.get('Images', '')
    }


    # Return variant update mutation input
    return product

def upload_to_shopify(product, images_str=None):
    if not product:
        return

    # Create new product
    if product.get("isNew") and not product.get("isVariant"):
        response, productId = create_product(product)

        if response.status_code != 200:
            print(f"{line_number} ❌ Failed to create product: {response.text}")
            return

    # Update existing product
    if not product.get("isNew") and not product.get("isVariant"):
        response = update_product(product)
        if response.status_code != 200:
            print(f"{line_number} ❌ Failed to update product: {response.text}")
            return

    if response.status_code == 200:
        data = response.json()
        result = data.get('data', {})
        errors = data.get('errors', [])

        if errors:
            print(f"{line_number} ❌ Errors for {product.get('title', product.get('sku', 'Unknown'))}:")
            for error in errors:
                print(f"{error['message']}")
            return

        if "productId" in product:
            result = result.get('productVariantCreate', {})
            action = "Added variant"

        if not product.get("isNew"):
            result = result.get('productUpdate', {})
            action = "Updated"
        
        if product.get("isNew"):
            result = result.get('productCreate', {})
            action = "Created"
 
        user_errors = result.get('userErrors', [])
        
        if user_errors:
            print(f"{line_number} ❌ Errors for {product.get('title', product.get('sku', 'Unknown'))}:")
            for error in user_errors:
                print(f"  - {error['field']}: {error['message']}")
        else:
            print(f"{line_number} ✅ {action}: {product.get('title', product.get('sku', 'Unknown'))} (ID: {product.get('id', 'N/A')})")
            
            # Process images if this is a parent product
            if "productId" not in product and product.get('id'):
                if SYNC_IMAGES:
                    resync_images(images_str, product.get('id'), sku=product.get('variants', [{}])[0].get('sku', ''), name=product.get('title', ''), line_number=line_number)

    else:
        print(f"{line_number} ❌ Failed to process {product.get('title', product.get('sku', 'Unknown'))}")
        print(response.status_code, response.text)

    return result


def main():
    # Get the default location ID
    global DEFAULT_LOCATION_ID
    DEFAULT_LOCATION_ID = get_locations()
    
    if not DEFAULT_LOCATION_ID:
        print("❌ Could not find a valid location ID. Please check your Shopify store settings.")
        return
    
    print(f"✅ Using location ID: {DEFAULT_LOCATION_ID}")

    open_log_files()

    # Read CSV with all columns as strings to avoid type conversion issues
    df = pd.read_csv(CSV_FILE, dtype=str).fillna('')
    
    for index, row in df.iterrows():    
        sku = row.get('SKU', '').strip()
        is_parent = check_parent(row)

        if not sku and not is_parent:
            continue

        if not sku and is_parent:
            sku = 'id:' + row.get('ID', '').strip()
            
        # Skip variants in first pass
        if check_variant(row):
            continue

        product_data = transform_product(row)

        result, product_id = create_product(product_data)

        child_products = get_child_products(product_data.get('sku'), df)
        
        children = []
        for child_product in child_products:
            # Now transform the dictionary
            child_product_data = transform_product(child_product, product_data)
            # add_child_product(child_product_data)
            children.append(child_product_data)
    
        if children:
            add_variants(product_id, children, parent_product=result)

        # else:       
        # result = upload_to_shopify(product_data, row.get('Images', ''))

        time.sleep(0.2)  # Throttle requests
    
    if CREATE_SMART_COLLECTIONS:
        # Create smart collections for each unique category
        print("\nCreating smart collections for categories...")
        publication_ids = get_publication_ids()
        for category in sorted(ALL_CATEGORIES):
            category = parse_decade(category)
            create_smart_collection(category,publication_ids)
            time.sleep(0.2)  # Throttle requests


if __name__ == "__main__":
    main()
