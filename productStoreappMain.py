import py7zr
import streamlit as st
import pandas as pd
import base64
import math
import uuid
from datetime import datetime
from pathlib import Path
from io import BytesIO
import tempfile
import shutil

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def generate_product_uuid(store, title, price, quantity):
    """Generate a unique UUID for each product based on its attributes"""
    unique_string = f"{store}|{title}|{price}|{quantity}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

st.set_page_config(layout="wide")

st.markdown("""
<style>
.image-wrapper {
    position: relative;
    display: inline-block;
    padding-top: 0;
}

.fullscreen-icon {
    position: absolute;
    top: 5px;
    right: 5px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 4px 6px;
    border-radius: 3px;
    font-size: 12px;
    text-decoration: none;
    z-index: 10;
}

.fullscreen-icon:hover {
    background: rgba(0, 0, 0, 0.9);
    color: white;
    text-decoration: none;
}

.scroll-box {
    max-height: 500px;
    overflow-y: auto;
    padding-right: 10px;
}

.quantity-controls {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    margin: 5px 0;
}

.total-price {
    font-size: 18px;
    font-weight: bold;
    color: #2e7d32;
    padding: 4px;
    background-color: #e8f5e8;
    border-radius: 5px;
    text-align: center;
    margin-bottom: 5px;
    
    
}

/* PRODUCT TITLE HOVER TOOLTIP */
.product-title-container {
    position: relative;
    display: inline-block;
    width: 100%;
    margin-bottom: 20px;
}

.product-title-short {
    font-weight: bold;
    cursor: help;
    color: #333;
    border-bottom: 1px dotted #666;
    display: inline-block;
    font-size: 14px;
    padding: 2px 4px;
    background-color: #f8f9fa;
    border-radius: 3px;
}

.product-title-container:hover .tooltip {
    visibility: visible;
    opacity: 1;
}

.tooltip {
    visibility: hidden;
    opacity: 0;
    width: 230px;
    height: 55px;
    background-color: #2c3e50;
    color: #ffffff;
    text-align: left;
    border-radius: 8px;
    padding: 12px 16px;
    position: absolute;
    z-index: 1001;
    bottom: auto;
    left: 50%;
    margin-left: -150px;
    transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
    font-size: 14px;
    line-height: 1.4;
    box-shadow: 0 6px 20px rgba(0,0,0,0.25);
    word-wrap: break-word;
    white-space: normal;
    font-weight: normal;
    border: 1px solid #34495e;
    overflow-y: auto;
    top: 105%;
}

.tooltip::after {
    content: "";
    position: absolute;
    top: -8px;
    left: 50%;
    margin-left: -8px;
    border-width: 8px;
    border-style: solid;
    border-color: #2c3e50 transparent transparent transparent;
    overflow-y: auto;
    
}

/* For mobile/small screens */
@media (max-width: 768px) {
    .tooltip {
        width: 250px;
        margin-left: -125px;
    }
}

/* Price text styling */
.price-text {
    margin-top: 8px;
    font-size: 13px;
    color: #555;
}

/* Filter section styling */
.filter-section {
    margin-bottom: 20px;
    padding: 10px;
    background-color: #f8f9fa;
    border-radius: 8px;
    border-left: 4px solid #007bff;
}

.filter-title {
    font-weight: bold;
    margin-bottom: 10px;
    font-size: 16px;
    color: #333;
}

.multiselect-container {
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)


# Load and cache data - only once per session

@st.cache_data
def load_product_data():
    script_dir = Path(__file__).parent
    filename = script_dir / f"products_25-06-2025.7z"

    # Use a temporary directory for extraction
    with tempfile.TemporaryDirectory() as tmpdirname:
        with py7zr.SevenZipFile(filename, mode='r') as archive:
            archive.extractall(path=tmpdirname)

        # Assuming there's only one file inside
        extracted_dir = Path(tmpdirname)
        extracted_file = next(extracted_dir.glob("*.json"))

        # Read the JSON file
        df = pd.read_json(extracted_file)

    df = df.sort_values('MetrPrice', ascending=True)
    df['product_uuid'] = df.apply(lambda row: generate_product_uuid(
        row['Store'], row['Title'], row['Current Price'], row['Quantity']), axis=1)
    return df

@st.cache_data
def create_product_lookup(df):
    lookup = {}
    for _, row in df.iterrows():
        lookup[row['product_uuid']] = {
            'store': row['Store'],
            'title': row['Title'],
            'price': row['Current Price'],
            'quantity': row['Quantity'],
            'unit': row['Unit'],  # ADD THIS LINE - Include unit in lookup
            'image_url': row['Image URL'],
            'metr_price': row['MetrPrice'],
            'prod_link' : row['Product Link']
        }
    return lookup

df = load_product_data()
product_lookup = create_product_lookup(df)

# Define the original store order from the full dataset
ORIGINAL_STORE_ORDER = list(df['Store'].unique())

script_dir = Path(__file__).parent
# Get the parent directory (which contains the icon folder)
parent_dir = script_dir.parent
icon_dir = parent_dir / "icon"

STORE_LOGOS = {
    'auchan-hypermarket-titan': icon_dir / "Auchan_2018.svg",
    'carrefour-hypermarket-mega-mall': icon_dir / "Carrefour_2009_(Horizontal).svg",
    'freshful-now': icon_dir / "Freshful-logo.svg",
    'kaufland-pantelimon': icon_dir / "Kaufland_1984_wordmark.svg",
    'Penny': icon_dir / "Penny_Markt_2012.svg",
    'profi-baia-de-arama': icon_dir / "Profi_2016_no_symbol.svg"
}

@st.cache_data
def get_store_logo(store_name):
    # First check the predefined logos
    logo_path = STORE_LOGOS.get(store_name)
    if logo_path and logo_path.exists():
        return str(logo_path)
    
    # If not found, try to find it in the icon directory
    if icon_dir.exists():
        for file in icon_dir.iterdir():
            if store_name.lower().replace(' ', '-') in file.name.lower():
                return str(file)
    
    return None

# Initialize selected products - simplified initialization
if 'selected_products' not in st.session_state:
    st.session_state.selected_products = {store: set() for store in df['Store'].unique()}

# Initialize product quantities - NEW
if 'product_quantities' not in st.session_state:
    st.session_state.product_quantities = {}

if 'units_multiselect' not in st.session_state:
    st.session_state.units_multiselect = []

if 'categories_multiselect' not in st.session_state:
    st.session_state.categories_multiselect = []

# Add a counter to force widget recreation when needed
if 'widget_reset_counter' not in st.session_state:
    st.session_state.widget_reset_counter = 0

min_price = math.floor(df['Current Price'].min())
max_price = math.ceil(df['Current Price'].max())

def clear_all_selections():
    st.session_state.selected_products = {store: set() for store in df['Store'].unique()}
    st.session_state.product_quantities = {}
    st.session_state.units_multiselect = []
    # If 'lowval_multiselect' is a key for a widget, uncomment this:
    st.session_state.lowval_multiselect = []
    st.session_state.categories_multiselect = []
    # Increment counter to force widget recreation
    st.session_state.widget_reset_counter += 1

# FIX: Add function to remove product - use counter approach
def remove_product_from_selection(store, product_uuid):
    """Remove product from selection and force widget recreation"""
    st.session_state.selected_products[store].discard(product_uuid)
    if product_uuid in st.session_state.product_quantities:
        del st.session_state.product_quantities[product_uuid]
    
    # Increment counter to force all widgets to recreate with new keys
    st.session_state.widget_reset_counter += 1

with st.sidebar:
    st.header("🔍 Search & Filters")

    st.caption(f"**For best results:** Use the search bar first, then apply filters to narrow down your results if you're not finding what you need.")

    search_query = st.text_input("Search for a product:", placeholder="Type product name...")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Create temporary filtered dataframe for dynamic filter options
    temp_df = df.copy()
    if search_query:
        temp_df = temp_df[temp_df['Title'].str.contains(search_query, case=False, na=False)]
    
    # Multi-select filters with dynamic options
    st.markdown('<div class="filter-title"></div>', unsafe_allow_html=True)
    
    # Get available units from current search results
    available_units = sorted(temp_df['Unit'].dropna().unique().tolist())
    selected_units = st.multiselect(
        "📦 Filter by Unit",
        options=available_units,
        key="units_multiselect",
        help="Select one or more units to filter products"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    
    st.markdown('<div class="filter-title"></div>', unsafe_allow_html=True)
    # Get available categories from current search results
    available_categories = sorted(temp_df['Cathegori'].dropna().unique().tolist())
    selected_categories = st.multiselect(
        "📂 Filter by Category",
        options=available_categories,
        key="categories_multiselect",
        help="Select one or more categories to filter products"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Price range slider
    price_range = st.slider("Price range (LEI):", min_value=min_price, max_value=max_price, value=(min_price, max_price), step=1)

    # Clear all selections button
    st.button(
            "🗑️ Clear All Selections",
            type="secondary",
            on_click=clear_all_selections # <--- IMPORTANT: Use on_click
        )

    # Show active filters summary
    active_filters_count = 0
    if selected_units:
        active_filters_count += len(selected_units)
    if selected_categories:
        active_filters_count += len(selected_categories)
    
    if active_filters_count > 0:
        st.markdown(f"**Active Filters: {active_filters_count}**")
        
        # Show filter summary
        if selected_units:
            st.markdown(f"**Units:** {', '.join(selected_units[:3])}{'...' if len(selected_units) > 3 else ''}")
        if selected_categories:
            st.markdown(f"**Categories:** {', '.join(selected_categories[:2])}{'...' if len(selected_categories) > 2 else ''}")
st.markdown("**<-- Filter in '>>'**")
st.caption(f"**Data Note:** This dashboard contains data inconsistencies including missing quantities, varied product descriptions, and consolidated categories from multiple sources. These inconsistencies will be reflected in search results and filters.")
st.markdown("**Sort by Value Per Quantity**")
# Apply all filters
filtered_df = df.copy()

# Apply search filter
if search_query:
    filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False, na=False)]

# Apply price range filter
filtered_df = filtered_df[
    (filtered_df['Current Price'] >= price_range[0]) & 
    (filtered_df['Current Price'] <= price_range[1])
]

# Apply unit filter
if selected_units:
    filtered_df = filtered_df[filtered_df['Unit'].isin(selected_units)]

# Apply category filter
if selected_categories:
    filtered_df = filtered_df[filtered_df['Cathegori'].isin(selected_categories)]

# Use the original store order
filtered_stores = set(filtered_df['Store'].unique())
stores = [store for store in ORIGINAL_STORE_ORDER if store in filtered_stores]

store_dfs = {store: filtered_df[filtered_df['Store'] == store].reset_index(drop=True) for store in stores}
rows_per_page = 5
rows = [st.columns(3), st.columns(3)]

for idx, store in enumerate(stores):
    
    col = rows[idx // 3][idx % 3]
    with col:
        st.markdown("<div style='padding-top: 20px;'></div>", unsafe_allow_html=True)
        logo_path = get_store_logo(store)
        if logo_path:
            try:
                st.markdown(
                    f"""
                    <div style="display: flex; justify-content: center; align-items: center;">
                        <img src="data:image/svg+xml;base64,{get_base64_of_bin_file(logo_path)}" style="width: 200px; height: 80px; border-radius: 8px;" />
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            except:
                st.image(logo_path, width=50)
        else:
            st.markdown(f"<h3 style='text-align: center;'>{store}</h3>", unsafe_allow_html=True)
        
        st.markdown("<div style='padding-bottom: 15px;'></div>", unsafe_allow_html=True)
        store_df = store_dfs[store].copy()
        total_pages = len(store_df) // rows_per_page + (len(store_df) % rows_per_page > 0)
        page_key = f'page_{store}'
        
        with st.container(height=300):
            # Reset page to 1 if current page exceeds total pages (happens when filters change)
            current_page = st.session_state.get(page_key, 1)
            if current_page > total_pages:
                current_page = 1
                st.session_state[page_key] = 1
            
            page = current_page
            start_idx = (page - 1) * rows_per_page
            end_idx = start_idx + rows_per_page
            paginated_df = store_df.iloc[start_idx:end_idx].copy()
            
            for _, row in paginated_df.iterrows():
                image_url = row['Image URL']
                product = row['Title']
                product_uuid = row['product_uuid']
                price = row['Current Price']
                quantity = row['Quantity']
                metprice = row["MetrPrice"]
                unit = row["Unit"]
                MetrPrice = row["MetrPrice"]
                prodlink = row["Product Link"]
                
                # FIX: More robust checkbox state management
                is_selected = product_uuid in st.session_state.selected_products[store]
                cols = st.columns([3, 2], gap="small")

                st.markdown("<div style='padding-top: 10px;'>", unsafe_allow_html=True)
                
                with cols[0]:
                    st.markdown(
                        f"""
                        <div class="image-wrapper">
                                <a href={prodlink}>
                                    <img src="{image_url}" style="width: 300px; height: 160px; object-fit: cover; border-radius: 8px;" />
                                </a>
                            <a href="{image_url}" target="_blank" class="fullscreen-icon">🔍</a>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                with cols[1]:
                                        # FIX: Include reset counter in checkbox key to force recreation when needed
                    checkbox_key = f"main_{store}_{product_uuid}_{st.session_state.widget_reset_counter}"
                    
                    # Use the current selection state to determine checkbox value
                    # This ensures the checkbox always reflects the actual selection state
                    selected = st.checkbox("Select", value=is_selected, key=checkbox_key)
                    
                    # Update selection state when checkbox changes
                    if selected != is_selected:
                        if selected:
                            st.session_state.selected_products[store].add(product_uuid)
                            # Initialize quantity when product is first selected
                            if product_uuid not in st.session_state.product_quantities:
                                st.session_state.product_quantities[product_uuid] = 1
                        else:
                            st.session_state.selected_products[store].discard(product_uuid)
                            # Remove quantity when product is deselected
                            if product_uuid in st.session_state.product_quantities:
                                del st.session_state.product_quantities[product_uuid]
        
                    # Simplified checkbox - let Streamlit handle the state naturall                    
                    # Product title with hover tooltip
                    short_title = product[:19] + "..." if len(product) > 2 else product
                    st.markdown(
                        f"""
                        <div class="product-title-container">
                            <span class="product-title-short">{short_title}</span>
                            <div class="tooltip">{product}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown(f"LEI {price} / {quantity} {unit}")


        # Pagination with proper bounds checking
        if total_pages > 1:
            # Ensure the current page doesn't exceed total pages
            current_page = st.session_state.get(page_key, 1)
            if current_page > total_pages:
                st.session_state[page_key] = total_pages
                current_page = total_pages
            
            st.number_input("", min_value=1, max_value=max(1, total_pages), value=current_page, key=page_key, step=1, help=f"Page navigation for {store} ({total_pages} pages total)")

st.subheader("🛒 Selected Products by Store")

if len(stores) == 0:
    st.info("No products found matching your search and filters. Try adjusting your filters or search term.")
else:
    # Add a container with fixed height and scrollbar
    with st.container(height=600):
        store_columns = st.columns(len(stores))
        grand_total = 0
        
        for idx, store in enumerate(stores):
            with store_columns[idx]:
                selected_product_uuids = st.session_state.selected_products[store]
                
                # Calculate total price with quantities
                store_total = 0
                for uuid in selected_product_uuids:
                    if uuid in product_lookup:
                        product_price = product_lookup[uuid]['price']
                        quantity = st.session_state.product_quantities.get(uuid, 1)
                        store_total += product_price * quantity
                
                grand_total += store_total
                
                # Display store logo
                logo_path = get_store_logo(store)
                if logo_path:
                    try:
                        st.markdown(
                            f"""
                            <div style="display: flex; justify-content: left; align-items: left;">
                                <img src="data:image/svg+xml;base64,{get_base64_of_bin_file(logo_path)}" style="width: 90px; height: 35px; border-radius: 8px; padding-bottom: 5px;" />
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    except:
                        st.markdown(f"<h4 style='text-align: center;'>{store}</h4>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<h4 style='text-align: center;'>{store}</h4>", unsafe_allow_html=True)

                
                # Display store total with styling
                st.markdown(f'<div class="total-price">{store_total:.2f} LEI</div>', unsafe_allow_html=True)
                
                if selected_product_uuids:
                    # Process selected products without conversion to list
                    for product_uuid in selected_product_uuids.copy():
                        if product_uuid in product_lookup:
                            product_info = product_lookup[product_uuid]
                            product = product_info['title']
                            price = product_info['price']
                            quantity = product_info['quantity']
                            unit = product_info['unit']  # FIX: Get unit from lookup
                            current_product_image = product_info['image_url']
                            prodlink = product_info["prod_link"]
                            metprice = product_info["metr_price"]

                        
                            # Get current quantity from session state
                            current_qty = st.session_state.product_quantities.get(product_uuid, 1)
                            
                            cols = st.columns([3, 1], gap="small")
                            with cols[0]:
                                st.markdown(
                                    f"""
                                    <div class="image-wrapper">
                                            <a href={prodlink}>
                                                <img src="{current_product_image}" style="width: 200px; height: 100px; object-fit: cover; border-radius: 8px; padding-top: 0px; padding-bottom: 5px;" />
                                            </a>
                                        <a href="{current_product_image}" target="_blank" class="fullscreen-icon">🔍</a>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                                
                                # Product title with hover tooltip in selected products
                                short_title = product[:20] + "..." if len(product) > 2 else product
                                st.markdown(
                                    f"""
                                    <div class="product-title-container">
                                        <span class="product-title-short">{short_title}</span>
                                        <div class="tooltip">{product}</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                                # Show total price for this product
                                total_product_price = price * current_qty
                                total_quant = quantity * current_qty
                                st.markdown(f"**Total:**\n\n **{total_quant} {unit}** \n\n **LEI {total_product_price:.2f}**")
                            
                                
                            with cols[1]:
                                if st.button("➖", key=f"dec_{store}_{product_uuid}"):
                                    if current_qty > 1:
                                        st.session_state.product_quantities[product_uuid] = current_qty - 1
                                        st.rerun()

                                st.markdown(f'<div class="qty-indic" style=" padding-left: 19px; " >{current_qty}</div>', unsafe_allow_html=True)

                                st.write(f"")
                                
                                if st.button("➕", key=f"inc_{store}_{product_uuid}"):
                                    st.session_state.product_quantities[product_uuid] = current_qty + 1
                                    st.rerun()
                                
                                # FIX: Use the new remove function with proper checkbox state management
                                if st.button("🗑️", key=f"remove_{store}_{product_uuid}"):
                                    remove_product_from_selection(store, product_uuid)
                                    st.rerun()
                            
                            st.markdown("---")
                else:
                    st.write("No products selected")
