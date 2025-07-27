import requests
import json
import time
import re
from datetime import datetime
import py7zr
from io import BytesIO,StringIO

# Venue URLs
venue_urls = [
   "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/freshful-now-67ecf9a6e78872a14652406a/assortment/categories/slug/{}?language=ro",
    "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/profi-baia-de-arama-3491-67fce8707ec55f4e5199f8d2/assortment/categories/slug/{}?language=ro",
    "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/penny-4469-67ee32d9a0c535a55340303e/assortment/categories/slug/{}?language=ro",
   "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/auchan-hypermarket-titan-67e2bd731248946a75c7a535/assortment/categories/slug/{}?language=ro",
   "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/carrefour-hypermarket-mega-mall-9139-67ee8dde26be843d2832a717/assortment/categories/slug/{}?language=ro",
    "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/kaufland-pantelimon-2470-67ecfaaae78872a1465240a6/assortment/categories/slug/{}?language=ro"

]

# Unit conversion factors
CONVERSION_FACTORS = {
    "kg": ("g", 1000),
    "l": ("ml", 1000),
    "spalari":("buc",1),
    "bucati":("buc",1),
    "gr":("g",1),
    "oua":("buc",1),

}

class FailedRequest:
    """Class to store information about failed requests for retry"""
    def __init__(self, url, request_type="main", base_url=None, category_id=None):
        self.url = url
        self.request_type = request_type  # "main" or "pagination"
        self.base_url = base_url
        self.category_id = category_id
        self.attempts = 0
        self.last_error = None

def evaluate_quantity(quant):
    """Safely evaluate a quantity string (e.g., "4*2" -> 8)"""
    try:
        quant = quant.replace("x", "*").replace("X", "*")
        return eval(quant)
    except (SyntaxError, NameError, TypeError):
        try:
            return float(quant)
        except ValueError:
            return None

def convert_to_smallest_unit(quant, unit):
    """Convert a quantity to the smallest unit"""
    if unit in CONVERSION_FACTORS:
        smallest_unit, factor = CONVERSION_FACTORS[unit]
        return quant * factor, smallest_unit
    return quant, unit

def preprocess_title(title):
    # Normalize spaces and fix common patterns

    # 6X0 33L → 6X0,33L or 6*0 33L
    title = re.sub(r'([x*])0\s+(\d+)(?=\s*(kg|g|gr|l|ml)\b)', r'\g<1>0,\2', title, flags=re.IGNORECASE)

    # 0 33L or 0 ,33L → 0.33L
    title = re.sub(r'\b0\s*[.,\s]\s*(\d+)(?=\s*(kg|g|gr|l|ml)\b)', r'0.\1', title, flags=re.IGNORECASE)

    # 033L → 0,33L
    title = re.sub(r'\b0(\d{2,})(?=\s*(kg|g|gr|l|ml)\b)', r'0,\1', title, flags=re.IGNORECASE)

    # FIXED: Handle /QUANTITYUNIT (e.g., /100G) by removing the slash and adding space
    title = re.sub(r'/\s*(\d+(?:[.,]\d+)?)\s*(kg|g|gr|l|ml)\b', r' \1\2', title, flags=re.IGNORECASE)

    return title

def extract_all_units_and_quantities(title):
    if not title:
        return 1, "buc"

    title_lower = title.lower()

    # Apply preprocessing first
    title_cleaned = preprocess_title(title_lower)   

    # Handle special cases first
    if "per bucata" in title_lower or "pe bucata" in title_lower:
        return 1, "buc"
    
    if re.search(r"vrac\s*/?\s*100G", title_cleaned):
        return 100, "g"
    
    if re.search(r"vrac\s*/?\s*kg", title_cleaned):
        return 1000, "g"

    # Main pattern matching
    indicators = r"kg|gr|g|bucati|buc|ml|l|spalari|oua"
    # Updated pattern to better handle the cleaned title
    pattern = rf"(\d+(?:[.,]\d+)?(?:\s*[x*]\s*\d+(?:[.,]\d+)?)?)\s*({indicators})\b"

    matches = re.findall(pattern, title_cleaned)
    
    if matches:
        last_match = matches[-1]
        quant = last_match[0].strip().replace(" ", "").replace(",", ".")
        unit = last_match[1].strip().lower()
        quant = evaluate_quantity(quant)

        if quant is not None:
            quant, unit = convert_to_smallest_unit(quant, unit)
            return quant, unit

    # Only fall back to vrac special case if no units were found at all
    if "vrac" in title_cleaned and not re.search(rf'\b({indicators})\b', title_cleaned):
        print(f"DEBUG: Vrac fallback triggered")  # Debug line
        return 1000, "g"

    return 1, "buc"

def get_with_retries(url, max_retries=10, initial_wait=1, max_wait=20):
    """Make HTTP request with exponential backoff retry logic"""
    wait_time = initial_wait
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            
            # Success cases
            if response.status_code == 200:
                return response
            elif response.status_code == 404:
                return response  # Let caller handle 404s
            elif response.status_code == 429:
                print(f"429 Too Many Requests. Waiting {wait_time} seconds before retrying (Attempt {attempt + 1})...")
            else:
                print(f"HTTP {response.status_code}. Waiting {wait_time} seconds before retrying (Attempt {attempt + 1})...")
            
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, max_wait)  # Exponential backoff with cap
            
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.5, max_wait)
        except requests.exceptions.ConnectionError:
            print(f"Connection error on attempt {attempt + 1}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.5, max_wait)
        except Exception as e:
            print(f"Request error on attempt {attempt + 1}: {e}")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.5, max_wait)
    
    raise Exception(f"Failed after {max_retries} retries")

def get_with_infinite_retries(url, initial_wait=1, max_wait=21):
    """Make HTTP request with infinite retries until success"""
    wait_time = initial_wait
    attempt = 0
    
    while True:
        attempt += 1
        try:
            response = requests.get(url, timeout=30)
            
            # Success cases
            if response.status_code == 200:
                return response
            elif response.status_code == 404:
                return response  # Let caller handle 404s
            elif response.status_code == 429:
                print(f"429 Too Many Requests. Waiting {wait_time} seconds before retrying (Attempt {attempt})...")
            else:
                print(f"HTTP {response.status_code}. Waiting {wait_time} seconds before retrying (Attempt {attempt})...")
            
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.2, max_wait)  # Gradual backoff with cap
            
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.1, max_wait)
        except requests.exceptions.ConnectionError:
            print(f"Connection error on attempt {attempt}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.1, max_wait)
        except Exception as e:
            print(f"Request error on attempt {attempt}: {e}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.1, max_wait)

def chateg():
    with open(r'C:\Users\bibo\Desktop\proj\!mainFinish\finalusechateg.json', 'r', encoding='utf-8') as f1:
        reader1 = json.load(f1)
    fdata = reader1
    return fdata

def data_getting(url, data, all_data, slugs_data, last_main_slug=None):
    """
    Process API response and extract product data, using the last main slug
    if the current data's items are empty.
    Returns the main slug to be used for the next iteration.
    """
    # Extract store name
    after_slug = url.split('/slug/')[1]
    before_assortment = after_slug.split('/assortment')[0]
    parts = re.split(r'\d', before_assortment, maxsplit=1)
    store_name = parts[0].rstrip('-')

    categtoreplace = chateg()
    category_map = {row['Original Category']: row['New Category'] for row in categtoreplace}

    def clean(category_string):
        return re.sub(r'[^a-z0-9]', '', category_string.lower())

    cleanedcategory_map = {clean(k): v for k, v in category_map.items()}

    # Get items (handle as list)
    items = data.get('items', [])
    if not isinstance(items, list):
        items = [items] if items else []

    # Get category information
    category_info = data.get('category', {})
    category_name = category_info.get('name', 'N/A')
    category_slug = category_info.get('slug', 'N/A')
    
    # Save slug and store information
    slug_entry = {
        "category_name": category_name,
        "category_slug": category_slug,
        "store_name": store_name,
        "store_slug": before_assortment,
        "has_items": bool(items)
    }
    
    # Add to slugs data if not already present
    existing_slug = next((s for s in slugs_data if s["category_slug"] == category_slug and s["store_slug"] == before_assortment), None)
    if not existing_slug:
        slugs_data.append(slug_entry)
    


    # Process items (only if there are any)
    for item in items:
        # Safe price conversion
        current_priceunrd = item.get('price', 0) / 100 if item.get('price') else 0
        current_price = round(current_priceunrd, 2)
        old_price = item.get('original_price', 0) / 100 if item.get('original_price') else 0

        # Get image URL
        image_url = "N/A"
        if item.get('images'):
            if isinstance(item['images'], list) and item['images']:
                image_url = item['images'][0].get('url', "N/A")
            elif isinstance(item['images'], dict):
                image_url = item['images'].get('url', "N/A")

        # Build product data
        prod_id = item.get('id', "N/A")
        product_link = f"https://wolt.com/en/rou/bucharest/venue/{before_assortment}/{prod_id}"
        title = item.get('name', "N/A")

        # Extract quantity and unit from title
        quant, unit = extract_all_units_and_quantities(title)

        # Calculate price per unit metric
        try:
            price_metric = current_price / quant if quant and current_price else 0
        except (TypeError, ZeroDivisionError):
            price_metric = 0
            print(f"Price calculation error - Title: {title}, Quantity: {quant}, Price: {current_price}")

        if price_metric < 0.0003:
            low_valflag = "Low"
        else:
            low_valflag = "Norm"

        cleanedcategory_name = clean(category_name)

        useChateg = cleanedcategory_map.get(cleanedcategory_name, "Miscellaneous") 

        category_data = {
            "Image URL": image_url,
            "Current Price": current_price,
            "Old Price": old_price,
            "Description": item.get('description', "N/A"),
            "Title": title,
            "Store": store_name,
            "Product Link": product_link,
            "Prod ID": prod_id,
            "Unit": unit,
            "MetrPrice": price_metric,
            "Quantity": quant,
            "LowValFlag": low_valflag,
            "catheg": category_name,
            "Cathegori": useChateg,
            "CategorySlug": category_slug
        }

        all_data.append(category_data)
    
    # Return the main slug to be used for the next iteration

def process_category(base_url, category_id, all_data, slugs_data, failed_requests):
    """Process a single category and handle pagination"""
    url = base_url.format(category_id)
    
    try:
        response = get_with_retries(url)
        
        if response.status_code == 404:
            return False  # No more categories
        
        data = response.json()
        
        # Check if category not found
        if 'detail' in data and 'not found' in data['detail']:
            return False  # No more categories
        
        category_name = data.get('category', {}).get('name', 'N/A')
        print(f"Category {category_id}: {category_name}")
        
        # Process main page
        data_getting(url, data, all_data, slugs_data)
        
        # Handle pagination
        nextpt = data.get('metadata', {}).get('next_page_token')
        while nextpt:
            urlpg = url + "&page_token=" + nextpt
            try:
                response = get_with_retries(urlpg)
                data = response.json()
                data_getting(url, data, all_data, slugs_data)
                nextpt = data.get('metadata', {}).get('next_page_token')
            except Exception as e:
                print(f"Failed pagination request for category {category_id}: {e}")
                failed_req = FailedRequest(urlpg, "pagination", base_url, category_id)
                failed_req.last_error = str(e)
                failed_requests.append(failed_req)
                break  # Stop pagination for this category, will retry later
                
        return True  # Successfully processed category
        
    except Exception as e:
        print(f"Failed main request for category {category_id}: {e}")
        failed_req = FailedRequest(url, "main", base_url, category_id)
        failed_req.last_error = str(e)
        failed_requests.append(failed_req)
        return True  # Continue to next category

def retry_failed_requests(failed_requests, all_data, slugs_data):
    """Retry all failed requests until they succeed"""
    if not failed_requests:
        return
        
    print(f"\n=== RETRYING {len(failed_requests)} FAILED REQUESTS UNTIL SUCCESS ===")
    
    while failed_requests:
        print(f"\n{len(failed_requests)} requests remaining to retry...")
        
        # Create a copy of failed requests to iterate over
        current_failures = failed_requests.copy()
        failed_requests.clear()  # Clear the original list
        
        for failed_req in current_failures:
            failed_req.attempts += 1
            print(f"Retrying (attempt {failed_req.attempts}): Category {failed_req.category_id} - {failed_req.request_type}")
            
            try:
                if failed_req.request_type == "main":
                    # Retry main category request with infinite retries
                    response = get_with_infinite_retries(failed_req.url)
                    
                    if response.status_code == 404:
                        print(f"✓ Category {failed_req.category_id} not found (404 - expected)")
                        continue  # Don't add back to failed requests
                    
                    data = response.json()
                    if 'detail' in data and 'not found' in data['detail']:
                        print(f"✓ Category {failed_req.category_id} not found (expected)")
                        continue  # Don't add back to failed requests
                    
                    # Successfully got data, process it
                    data_getting(failed_req.url, data, all_data, slugs_data)
                    
                    # Also handle pagination for retried main requests
                    nextpt = data.get('metadata', {}).get('next_page_token')
                    while nextpt:
                        urlpg = failed_req.url + "&page_token=" + nextpt
                        try:
                            response = get_with_infinite_retries(urlpg)
                            data = response.json()
                            data_getting(failed_req.url, data, all_data, slugs_data)
                            nextpt = data.get('metadata', {}).get('next_page_token')
                        except Exception as e:
                            print(f"Failed pagination in retry: {e}")
                            new_failed = FailedRequest(urlpg, "pagination", failed_req.base_url, failed_req.category_id)
                            new_failed.last_error = str(e)
                            failed_requests.append(new_failed)
                            break
                    
                    print(f"✓ Successfully retried main request for category {failed_req.category_id}")
                        
                elif failed_req.request_type == "pagination":
                    # Retry pagination request with infinite retries
                    response = get_with_infinite_retries(failed_req.url)
                    data = response.json()
                    data_getting(failed_req.base_url.format(failed_req.category_id), data, all_data, slugs_data)
                    print(f"✓ Successfully retried pagination request for category {failed_req.category_id}")
                    
            except KeyboardInterrupt:
                print("\n🛑 Retry process interrupted by user")
                failed_requests.extend(current_failures[current_failures.index(failed_req):])
                break
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Unexpected error for category {failed_req.category_id}: {error_msg}")
                failed_req.last_error = error_msg
                failed_requests.append(failed_req)  # Add back to retry queue
            
            # Add a small delay between individual retries
            time.sleep(0.2)
        
        # If we have requests that still need retrying, wait before next batch
        if failed_requests:
            wait_time = min(2 + len(current_failures) * 0.1, 10)  # Short wait between batches
            print(f"Waiting {wait_time:.1f} seconds before next retry batch...")
            time.sleep(wait_time)
    
    print(f"\n✅ All failed requests successfully retried!")

def remove_duplicates(products):
    """Remove duplicate products based on image URL"""
    unique_products = {}
    for product in reversed(products):
        image_url = product.get("Image URL")
        if image_url not in unique_products:
            unique_products[image_url] = product
    return list(reversed(unique_products.values()))

def main():
    """Main scraping function"""
    active_venues = {url: True for url in venue_urls}
    all_data = []
    slugs_data = []  # New list to store slug information
    failed_requests = []
 
    i = 1
    while any(active_venues.values()):
        for base_url in venue_urls:
            if not active_venues[base_url]:
                continue

            success = process_category(base_url, i, all_data, slugs_data, failed_requests)
            if not success:
                print(f"Done with venue at slug {i}")
                active_venues[base_url] = False

            time.sleep(0.1)

        i += 1

    # Retry all failed requests at the end
    retry_failed_requests(failed_requests, all_data, slugs_data)

    # Remove duplicates
    unique_products = remove_duplicates(all_data)
    
    print(f"\nScraping complete! Collected {len(unique_products)} unique products")
    print(f"Collected {len(slugs_data)} unique category slugs")
    if failed_requests:
        print(f"⚠️  Warning: {len(failed_requests)} requests could not be recovered")

    

    today = datetime.now()
    date_str = today.strftime("%d-%m-%Y")

    # Create JSON string
    json_str = json.dumps(unique_products, ensure_ascii=False)
    json_bytes = json_str.encode("utf-8")

    # Use BytesIO instead of StringIO for binary data
    json_io = BytesIO(json_bytes)

    # Write to 7z archive
    with py7zr.SevenZipFile(f"products_{date_str}.7z", "w") as archive:
        archive.writef(json_io, f"products_{date_str}.json")

    
    print(F"Product data saved to products_{date_str}.json")
    
    # Save slugs data
    with open('slugs.json', 'w', encoding='utf-8') as json_file:
        json.dump(slugs_data, json_file, indent=4, ensure_ascii=False)
    
    print("Slugs data saved to slugs.json")
   

if __name__ == "__main__":
    main()