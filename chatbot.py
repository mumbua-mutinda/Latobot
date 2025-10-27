import json

# Load product data
with open("lato_products.json", "r") as file:
    products = json.load(file)

# Flatten product names for easy search
product_names = [p["product_name"].lower() for p in products]

# Helper functions
def get_composition_info(product, query):
    """Return only relevant composition info if asked for specific nutrient."""
    comp = product.get("composition", {})
    for key in comp:
        if key.lower() in query:
            return f"{key}: {comp[key]}"
    return None

def check_baby_safety(product):
    """Return a warning if product is not for infants under 12 months."""
    if "not for infant" in product.get("intended_uses", "").lower():
        return "⚠️ Note: This product is not recommended for infants under 12 months."
    return None

# Greetings keywords
greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "kindly help", "help"]

print("👋 Hi! I’m Lato Chatbot. Ask me anything about our products.")
print("Type 'exit' to quit.\n")

while True:
    query = input("> ").strip().lower()
    
    if query == "exit":
        print("Goodbye! Have a great day! 🥛")
        break

    # Handle greetings
    if any(greet in query for greet in greetings):
        print("Hello! I can help you find information about Lato products. Try asking about milk, butter, or yoghurt.\n")
        continue

    found_any = False
    for product in products:
        # Check if product matches query
        if any(name_part in query for name_part in product["product_name"].lower().split()) or any(cat in query for cat in product.get("categories", [])):
            print(f"\nProduct: {product['product_name']}")
            print(f"Description: {product.get('description', 'No description available.')}")
            print(f"Intended Uses: {product.get('intended_uses', 'Not specified.')}")
            print(f"Packaging: {product.get('packaging', 'Not specified.')}")
            print(f"Shelf Life: {product.get('shelf_life', 'Not specified.')}")
            
            # Show relevant composition info if nutrient mentioned
            comp_info = get_composition_info(product, query)
            if comp_info:
                print(f"Composition Info: {comp_info}")
            else:
                print(f"Composition: {product.get('composition', 'Not specified.')}")
            
            # Show baby safety note
            safety_note = check_baby_safety(product)
            if safety_note:
                print(safety_note)
            
            found_any = True

    if not found_any:
        print("Sorry, I couldn’t find that product. Please try another name or category.\n")
