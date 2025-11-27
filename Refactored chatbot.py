import json
import re
import textwrap
import random

# ---------------------------
# Load product data
# ---------------------------
DATA_FILE = "lato_products.json"

try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
        if isinstance(raw, dict) and "categories" in raw:
            products = []
            for cat in raw["categories"]:
                cat_name = cat.get("category") or "Uncategorized"
                for p in cat.get("products", []):
                    p.setdefault("category", cat_name)
                    products.append(p)
        elif isinstance(raw, list):
            products = []
            for cat in raw:
                if isinstance(cat, dict) and "category" in cat and "products" in cat:
                    cat_name = cat.get("category") or "Uncategorized"
                    for p in cat.get("products", []):
                        p.setdefault("category", cat_name)
                        products.append(p)
                else:
                    products = raw
        else:
            products = []
except FileNotFoundError:
    print(f"ERROR: {DATA_FILE} not found. Place lato_products.json in the same folder.")
    products = []

# ---------------------------
# Normalize product data
# ---------------------------
def _get_key(p, *keys, default=None):
    for k in keys:
        if k in p:
            return p[k]
    return default

for p in products:
    p["product_name"] = _get_key(p, "product_name", "name", "sku", "title", default="Unnamed Product")
    p["category"] = p.get("category", p.get("category_name", "General"))
    comp = _get_key(p, "composition", "nutritional_info", default={})
    if isinstance(comp, str):
        comp_dict = {}
        for line in comp.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                comp_dict[k.strip()] = v.strip()
        comp = comp_dict
    p["composition"] = comp if isinstance(comp, dict) else {}
    p["_comp_norm"] = {k.lower(): v for k, v in p["composition"].items()}
    p["_desc"] = (_get_key(p, "description", "desc", default="") or "").strip()
    p["_intended"] = (_get_key(p, "intended_uses", "intended", default="") or "").strip()
    p.setdefault("shelf_life", p.get("Shelf life") or p.get("shelf life") or p.get("shelf_life", "Not specified"))
    p.setdefault("packaging", p.get("packaging", "Not specified"))
    p.setdefault("friendly_description", p.get("friendly_description", p.get("_desc", "No description available")))

# ---------------------------
# Helpers
# ---------------------------
def wrap(txt, indent=0, width=75):
    prefix = " " * indent
    return "\n".join(prefix + line for line in textwrap.fill(txt, width=width).splitlines())

def format_composition(comp):
    if not comp:
        return "  • Composition info not available."
    return "\n".join(f"  • {k.title()}: {v or 'Not specified'}" for k, v in comp.items())

def show_product(product):
    desc = product.get("friendly_description", "No description available")
    comp = format_composition(product.get("composition"))
    intended = product.get("recommended_for") or product.get("_intended") or "Not specified"
    shelf = product.get("shelf_life", "Not specified")
    packaging = product.get("packaging", "Not specified")

    text = f"""🥛 Product: {product['product_name']}

{wrap(desc, 2)}

🎯 Recommended for: {intended}
📦 Packaging: {packaging}
🕒 Shelf life: {shelf}

🔬 Composition:
{comp}

Would you like help finding similar products, ordering info, or something else?"""
    return text

def show_category(cat_name):
    matches = [p for p in products if cat_name.lower() in p["category"].lower()]
    if not matches:
        return f"Sorry, I couldn't find products in the category '{cat_name}'."
    names = "\n- ".join([p["product_name"] for p in matches])
    return f"Here are the {cat_name} options we have:\n- {names}\nWhich one would you like to know more about?"

def suggest_similar(product):
    # Find other products in the same category
    similar = [p for p in products if p["category"] == product["category"] and p["product_name"] != product["product_name"]]
    if not similar:
        return "No similar products found."
    selection = random.sample(similar, min(len(similar), 3))
    return "You might also like:\n- " + "\n- ".join([p["product_name"] for p in selection])

def best_for(keyword):
    keyword = keyword.lower()
    mapping = {
        "infant": ["LAT-UHT-FINO-200ml", "Lato Grow 400G"],
        "brain": ["Honey 1Kg", "Lato Grow 400G"]
    }
    choices = mapping.get(keyword)
    if not choices:
        return "Sorry, I don't have a recommendation for that yet."
    matches = [p for p in products if p["product_name"] in choices]
    return show_product(matches[0])

# ---------------------------
# Routing / Conversation
# ---------------------------
last_product = None  # for context-aware responses

def route(user):
    global last_product
    ql = user.lower().strip()

    # 1. Greetings
    if any(g in ql for g in ["hi", "hello", "hey"]):
        return "🥛 Hi — I’m Lato, your friendly nutrition buddy!\nI can help you explore products, check nutrition, or recommend options for children.\nTry 'show milk', 'what's best for a 2 year old', 'which has the most protein', or ask for a product by name."

    # 2. Show categories
    for cat in ["milk", "butter", "yoghurt", "honey", "juice", "porridge", "ghee"]:
        if cat in ql and any(w in ql for w in ["show", "list", "have", "kind", "type"]):
            return show_category(cat)

    # 3. Product by name
    for p in products:
        if p["product_name"].lower() in ql:
            last_product = p
            return show_product(p)

    # 4. “Best for” logic
    if any(w in ql for w in ["infant", "baby", "newborn"]):
        return best_for("infant")
    if any(w in ql for w in ["brain", "memory", "focus"]):
        return best_for("brain")

    # 5. Similar products / follow-ups
    if ql in ["yes", "similar", "more"]:
        if last_product:
            return suggest_similar(last_product)
        else:
            return "Which product would you like me to suggest alternatives for?"

    # 6. Nutritional queries (most protein/fat/energy)
    if "most protein" in ql:
        best = max(products, key=lambda x: float(x["_comp_norm"].get("protein", 0)))
        last_product = best
        return f"🔍 The product highest in *protein* is *{best['product_name']}* — {best['_comp_norm'].get('protein')} g.\n\n" + show_product(best)

    if "help" in ql:
        return "Try asking about product categories (e.g., 'milk', 'yoghurt'), a product by name, 'what's best for a 2 year old', or 'which has the most protein'."

    # fallback
    return "Sorry — I didn't quite get that. You can ask about product categories, a product by name, or 'which has the most protein'."

# ---------------------------
# Main Loop
# ---------------------------
def main():
    print("🥛 Hi — I’m Lato, your friendly nutrition buddy!")
    print("I can help you explore products, check nutrition, or recommend options for children.")
    print("Try 'show milk', 'what's best for a 2 year old', 'which has the most protein', or ask for a product by name.\n")

    while True:
        user = input("> ").strip()
        if user.lower() in ["exit", "quit"]:
            print("Bye! 🥛 Have a great day!")
            break
        out = route(user)
        print("\n" + out + "\n")

if __name__ == "__main__":
    main()
