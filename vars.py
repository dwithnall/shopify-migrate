# Process parent products
PROCESS_PARENT_PRODUCTS = True

# Process variants
PROCESS_VARIANTS = True

# Sync images
SYNC_IMAGES = False

# Create smart collections
CREATE_SMART_COLLECTIONS = False

# WooCommerce export file
CSV_FILE = 'short.csv'

line_number = 0

# Shopify credentials

API_VERSION = '2024-07'

# Global variables
DEFAULT_LOCATION_ID = None

# GraphQL endpoint
GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json"

# Headers for GraphQL requests
HEADERS = {
    'Content-Type': 'application/json',
    'X-Shopify-Access-Token': SHOPIFY_API_ACCESS_TOKEN
}

# Log file for dimensions that couldn't be parsed
DIMENSIONS_LOG_FILE = 'dimensions_to_process.csv'

# Store the default location ID
DEFAULT_LOCATION_ID = None

# Image errors log file
IMAGE_ERRORS_LOG_FILE = 'image_errors.csv'


# Store all unique categories for collection creation
ALL_CATEGORIES = set()