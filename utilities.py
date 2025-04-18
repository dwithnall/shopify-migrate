"""
Utility functions for the Shopify migration script.
"""
import re
from vars import *
from keys import *

def parse_tags(tag_list, attr_tags):
    """
    Extract unique tags from category tags and attribute tags.
    
    Args:
        tag_list: List of category tags
        attr_tags: List of attribute tags
        
    Returns:
        List of unique tags with proper formatting
    """
    # Combine category tags and attribute tags, handling None values
    decade_tag = None
    unique_tags = []

    all_tags = []
    if tag_list:
        all_tags.extend(tag_list)
    if attr_tags:
        all_tags.extend(attr_tags)
    
    # Remove duplicates while preserving order
    for tag in all_tags:
        if tag and tag not in unique_tags:  # Only add non-empty tags
            # Check if tag is a decade and parse it
            decade_tag = parse_decade(tag)
            if decade_tag != None:
                decade_tag = decade_tag.title()
                unique_tags.append(decade_tag)
            else:
                # Apply normal title case
                if tag.title() != '[]':
                    unique_tags.append(tag.title())
    
    # Set tags to None if empty
    if len(unique_tags) == 0:
        unique_tags = None
        
    return unique_tags

def parse_decade(value):
    """
    Parse decade values in various formats and standardize to lowercase 's' format.
    Examples:
    - "1950S" -> "1950s"
    - "1950's" -> "1950s"
    - "1950s" -> "1950s"
    - "1950" -> "1950s"
    - "50s" -> "1950s"
    - "50's" -> "1950s"
    - "50S" -> "1950s"
    - "1953" -> "1950s"
    - "1967" -> "1960s"
    """
    if not value:
        return None
    
    # Remove any whitespace
    value = value.strip()
    year = None

    # Pattern 1: Full year with uppercase S (e.g., "1950S")
    pattern1 = r'^(\d{4})S$'
    match1 = re.match(pattern1, value)
    if match1:
        year = match1.group(1)
    
    # Pattern 2: Full year with apostrophe and s (e.g., "1950's")
    pattern2 = r'^(\d{4})\'s$'
    match2 = re.match(pattern2, value)
    if match2:
        year = match2.group(1)
    
    # Pattern 3: Full year with lowercase s (e.g., "1950s")
    pattern3 = r'^(\d{4})s$'
    match3 = re.match(pattern3, value)
    if match3:
        year = match3.group(1)
    
    # Pattern 4: Full year without s (e.g., "1950")
    pattern4 = r'^(\d{4})$'
    match4 = re.match(pattern4, value)
    if match4:
        year = match4.group(1)
    
    # Pattern 5: Two-digit year with s (e.g., "50s")
    pattern5 = r'^(\d{2})s$'
    match5 = re.match(pattern5, value)
    if match5:
        year = match5.group(1)
        # Assume 20th century for two-digit years
        if int(year) >= 50:
            year = f"19{year}"
        else:
            year = f"20{year}"
    
    # Pattern 6: Two-digit year with apostrophe and s (e.g., "50's")
    pattern6 = r'^(\d{2})\'s$'
    match6 = re.match(pattern6, value)
    if match6:
        year = match6.group(1)
        # Assume 20th century for two-digit years
        if int(year) >= 50:
            year = f"19{year}"
        else:
            year = f"20{year}"
    
    # Pattern 7: Two-digit year with uppercase S (e.g., "50S")
    pattern7 = r'^(\d{2})S$'
    match7 = re.match(pattern7, value)
    if match7:
        year = match7.group(1)
        # Assume 20th century for two-digit years
        if int(year) >= 50:
            year = f"19{year}"
        else:
            year = f"20{year}"

    if year:
        # Floor to nearest decade
        year_num = int(year)
        decade = (year_num // 10) * 10
        return f"{decade}s"
    
    # If no pattern matches, return none
    return None

def format_description(text, product_attributes):
  """Format description text with proper HTML tags"""
  if not text:
      return ''
  
  # First split by double newlines to get paragraphs
  paragraphs = text.split('\\n\\n')
  
  # Process each paragraph
  formatted_paragraphs = []
  for p in paragraphs:
      # Replace single newlines with <br /> and wrap in <p> tags if not empty
      if p.strip():
          p = p.replace('\\n', '<br />')
          formatted_paragraphs.append(f"<p>{p}</p>")
  
  # Join all paragraphs
  description = ''.join(formatted_paragraphs)

  # Add product attributes to the product input
  if product_attributes:
      # Create a formatted HTML table of attributes
      attributes_html = "<br/><br/><b>Product Attributes:</b><table style='border-collapse: collapse; width: 100%;'>"
      for attr_name, attr_value in product_attributes.items():
          attributes_html += f"<tr><td style='border: 1px solid #ddd; padding: 8px;'><b>{attr_name}</b></td><td style='border: 1px solid #ddd; padding: 8px;'>{attr_value}</td></tr>"
      attributes_html += "</table>"
      description = f"{description}{attributes_html}"

  return description

def check_variant(row):
    """Helper function to check if a row represents a variant"""
    product_type = row.get('Type', '').strip().lower()
    return product_type == 'variation'

def check_parent(row):
    """Helper function to check if a row represents a parent product"""
    product_type = row.get('Type', '').strip().lower()
    return product_type == 'variable'

def process_categories(categories_str):
    """Process categories string into unique tags and extract designer name"""
    if not categories_str:
        return [], None
    
    # Split by comma to get individual categories
    categories = [cat.strip() for cat in categories_str.split(',') if cat.strip()]
    
    # Split each category by ' > ' and flatten the list
    all_tags = []
    designer_name = ''
    
    for category in categories:
        # Split by ' > ' and add each part as a tag
        parts = [part.strip() for part in category.split('>') if part.strip()]
        
        # Check if the first part is "Designers" and use the second part as designer name
        if parts and len(parts) > 1 and parts[0].lower() == 'designers':
            designer_name = parts[1]
        # # Otherwise check if the first part looks like a designer name
        # elif parts and designer_name == '':
        #     # Check if this looks like a designer name (no spaces or camelCase)
        #     if ' ' not in parts[0] or parts[0][0].isupper():
        #         designer_name = parts[0]
        
        all_tags.extend(parts)
    
    # Remove duplicates while preserving order
    unique_tags = []
    for tag in all_tags:
        if tag and tag not in unique_tags:  # Only add non-empty tags
            unique_tags.append(tag)
    
    # Remove "Designers" tag if present
    if "Designers" in unique_tags:
        unique_tags.remove("Designers")
        unique_tags.append("Designer")
    
    # Add to global categories set
    for tag in unique_tags:
        ALL_CATEGORIES.add(tag)
    
    return unique_tags, designer_name

def process_attributes(row, parent_product=None):
    """Process attribute fields and extract dimensions and designer name"""
    all_tags = []
    dimensions = None
    designer_name = None
    product_attributes = {}  # Dictionary to store attribute name -> value pairs
    variant_attributes = {}

    is_variant = check_variant(row)
    is_parent = check_parent(row)

    # Get parent variant attributes if available
    parent_variant_attrs = {}
    if parent_product and isinstance(parent_product, dict):
        parent_variant_attrs = parent_product.get('variantAttributes', {})
    
    # Check for attribute columns (they start with 'Attribute')
    for col in row.index:
        if col.startswith('Attribute') and 'name' in col:
            attr_num = col.split(' ')[1]  # Get the attribute number
            # Convert to string before calling strip()
            attr_name = str(row.get(col, '')).strip()
            attr_visible = str(row.get(f'Attribute {attr_num} visible', '')).strip()
            attr_value = str(row.get(f'Attribute {attr_num} value(s)', '')).strip()
            
            if not attr_name:
                continue
            
            if is_parent and attr_visible == '0':
                variant_attributes[attr_name] = attr_value
                continue
            
            # For variants, check if this attribute is in the parent's variant attributes
            if is_variant:
                # Check if the attribute name exists in the parent's variant attributes
                if attr_name in parent_variant_attrs:
                    variant_attributes[attr_name] = attr_value
                    continue
            
            # Store attribute name and value
            if attr_value:  # Only add non-empty values
                product_attributes[attr_name] = attr_value

            # Check if this is a Dimensions attribute
            if attr_name.lower() == 'dimensions':
                dimensions = parse_dimensions(attr_value)
            # Check if this is a Designer attribute
            elif attr_name.lower() == 'designer':
                designer_name = attr_value
            else:
                # Handle values
                if ',' in attr_value:
                    values = [val.strip() for val in attr_value.split(',') if val.strip()]
                    all_tags.extend(values)
                else:
                    if attr_value:  # Only add non-empty values
                        all_tags.append(attr_value)
    
    if len(all_tags) == 0:
        all_tags = None
        
    if len(variant_attributes) == 0:
        variant_attributes = None

    dimension_metafields = None
    if dimensions is not None:
        dimension_metafields = [
            {
                "namespace": "custom",
                "key": "width",
                "value": str(dimensions["width"]),
                "type": "single_line_text_field"
            },
            {
                "namespace": "custom",
                "key": "height",
                "value": str(dimensions["height"]),
                "type": "single_line_text_field"
            },
            {
                "namespace": "custom",
                "key": "depth",
                "value": str(dimensions["depth"]),
                "type": "single_line_text_field"
            }
        ]
        
    return all_tags, dimension_metafields, designer_name, product_attributes, variant_attributes

def parse_dimensions(dim_str):
    """Parse dimensions string into width, height, depth"""
    if not dim_str:
        return None
    
    # Remove spaces and convert to lowercase for easier parsing
    dim_str = dim_str.lower().replace(' ', '')
    
    # Try to extract dimensions using regex patterns
    # Pattern 1: "80cm x 80cm x 45.5(h)cm" or "80cm x 80cm x 45.5cm(h)"
    pattern1 = r'(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)(?:cm)?\s*\(h\)'
    match1 = re.search(pattern1, dim_str)
    if match1:
        width, depth, height = match1.groups()
        return {
            "width": float(width),
            "height": float(height),
            "depth": float(depth)
        }
    
    # Pattern 2: "134cm - 239cm x 85cm x 72cm(h)"
    pattern2 = r'(\d+(?:\.\d+)?)cm\s*-\s*(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)(?:cm)?\s*\(h\)'
    match2 = re.search(pattern2, dim_str)
    if match2:
        width_min, width_max, depth, height = match2.groups()
        # Use the average of the range
        width = (float(width_min) + float(width_max)) / 2
        return {
            "width": width,
            "height": float(height),
            "depth": float(depth)
        }
    
    # Pattern 3: "29.5cm(h)" - height only
    pattern3 = r'(\d+(?:\.\d+)?)(?:cm)?\s*\(h\)'
    match3 = re.search(pattern3, dim_str)
    if match3:
        height = match3.group(1)
        return {
            "width": 0,
            "height": float(height),
            "depth": 0
        }
    
    # Pattern 4: "160cm x 105cm(h)" - width and height
    pattern4 = r'(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)(?:cm)?\s*\(h\)'
    match4 = re.search(pattern4, dim_str)
    if match4:
        width, height = match4.groups()
        return {
            "width": float(width),
            "height": float(height),
            "depth": 0
        }
    
    # Pattern 5: "70cm x 70cm x 47.5cm" - standard format without (H)
    pattern5 = r'(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)cm\s*x\s*(\d+(?:\.\d+)?)cm'
    match5 = re.search(pattern5, dim_str)
    if match5:
        width, depth, height = match5.groups()
        return {
            "width": float(width),
            "height": float(height),
            "depth": float(depth)
        }
    
    
    # If no pattern matches, return None
    return None

def open_log_files():  
  # Create or clear the dimensions log file
  with open(DIMENSIONS_LOG_FILE, 'w') as f:
      f.write("Line Number,SKU,Name,Dimensions\n")
  
  # Create or clear the image errors log file
  with open(IMAGE_ERRORS_LOG_FILE, 'w') as f:
      f.write("Line Number,SKU,Name,Image URLs,Error Message\n")
    
def log_dimensions(sku, name, dimensions_str):
    """Log dimensions that couldn't be parsed for later processing"""
    with open(DIMENSIONS_LOG_FILE, 'a') as f:
        f.write(f"{line_number},{sku},{name},{dimensions_str}\n")

def log_image_error(sku, name, image_urls, error_message, line_number):
    """Log image upload errors for a product"""
    with open(IMAGE_ERRORS_LOG_FILE, 'a') as f:
        urls = ','.join(image_urls)
        f.write(f"{line_number},{sku},{name},\"{urls}\",{error_message}\n")

def parse_images(images_str):
    """Parse images string into a list of image URLs"""
    if not images_str:
        return []
    
    return [url.strip() for url in images_str.split(',') if url.strip()]

def get_child_products(parent_id, df):
    """
    Find all child products of a parent product in a pandas DataFrame.
    
    Args:
        parent_id: The ID of the parent product
        df: pandas DataFrame containing all products
        
    Returns:
        DataFrame containing all child products that have the parent_id in their 'parent' field
    """
    child_products = []

    for index, row in df.iterrows():  
        if not check_variant(row):
            continue
        
        parent_sku = row.get('Parent', '').strip()
        if not parent_sku:
            continue

        if parent_sku == parent_id:
            child_products.append(row)
            continue
        


    return child_products


def add_child_product(parent_product, child_product):
    """
    Add a child product to the parent product's children list.
    
    Args:
        parent_product: The parent product dictionary
        child_product: The child product dictionary
        
    Returns:
        The updated parent product with the child added to its children list
    """
    # Initialize the children list if it doesn't exist
    if 'children' not in parent_product:
        parent_product['children'] = []
    
    # Create a simplified child product object with only the necessary fields
    child_data = {
        'title': child_product.get('title', ''),
        'sku': child_product.get('sku', ''),
        'price': child_product.get('price', '0.00'),
        'variantAttributes': child_product.get('variantAttributes', {})
    }
    
    # Add the child to the parent's children list
    parent_product['children'].append(child_data)
    
    return parent_product