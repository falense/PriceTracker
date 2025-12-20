# Extraction Fields Guide

The pattern generator now extracts **6 fields** from e-commerce product pages:

## Fields Extracted

### 1. **Price** 💰
- Current selling price
- Extracts from: data attributes, CSS classes, JSON data
- Example: `1 990,-` or `1990.00`

### 2. **Title** 📝
- Product name/title
- Extracts from: Open Graph meta tags, H1 headings
- Example: `Bose QuietComfort SC trådløse hodetelefoner, Over-Ear (sort)`

### 3. **Image** 🖼️
- Primary product image URL
- Extracts from: Open Graph meta tags, img elements
- Example: `https://www.komplett.no/img/p/200/1310167.jpg`

### 4. **Availability** ✅
- Stock status/availability
- Extracts from: stock indicators, JSON data
- Example: `Tilgjengelighet: 20+ stk. på lager.` or `In Stock`

### 5. **Article Number** 🔢 (NEW)
- Web store item number (Varenummer/SKU)
- Extracts from: `itemprop="sku"`, "Varenummer" labels
- Example: `1310167`

### 6. **Model Number** 🏷️ (NEW)
- Manufacturer model/part number
- Extracts from: JSON data, product specification tables
- Example: `884367-0900`
