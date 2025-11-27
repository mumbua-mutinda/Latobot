import json
import re

# ---------------------------
# Load product data
# ---------------------------
with open("lato_products.json", "r", encoding="utf-8") as f:
    products = json.load(f)

# Normalize product composition keys for easier search
for p in products:
    comp = p.get("composition", {})
    # create a normalized composition dict (lowercase keys)
    p["_comp_norm"] = {k.lower(): v for k, v in comp.items()}

# ---------------------------
# Helper functions
# ---------------------------
def extract_number_from_text(s):
    """Return first numeric value found in string as float (or None)."""
    if not s:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if m:
        try:
            return float(m.group(1))
        except:
            return None
    return None

def parse_age_to_months(txt):
    """Extract age in months from a query string. Supports 'X months', 'X years'."""
    if not txt:
        return None
    # find 'X months' or 'X month'
    m = re.search(r'(\d+)\s*month', txt)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*year', txt)
    if m:
        return int(m.group(1)) * 12
    # if only a number present, assume months
    m = re.search(r'\b(\d+)\b', txt)
    if m:
        return int(m.group(1))
    return None

def min_safe_age_months(product):
    """
    Determine minimum recommended age (in months) from product intended_uses / notes.
    - If text says 'not for infant' or 'not intended for infant', default to 12 months.
    - If text contains 'below X months' or 'below X years', parse X.
    """
    text = product.get("intended_uses", "") + " " + product.get("description", "")
    text = text.lower()
    # try patterns like 'below 12 months' or 'below 24 months'
    m = re.search(r'below\s+(\d+)\s*month', text)
    if m:
        return int(m.group(1))
    m = re.search(r'below\s+(\d+)\s*year', text)
    if m:
        return int(m.group(1)) * 12
    # patterns like 'not for infant formula for infants below 12 months'
    m = re.search(r'below\s+(\d+)\s*', text)
    if m and 'infant' in text and 'below' in text:
        try:
            return int(m.group(1))
        except:
            pass
    # generic phrase
    if "not intended for infant" in text or "not for infant" in text or "not for use in infant" in text:
        return 12
    # otherwise assume safe for all ages unless stated
    return 0

def is_safe_for_age(product, age_months):
    """Return True if product is safe for given age in months (age_months may be None)."""
    min_age = min_safe_age_months(product)
    return (age_months is None) or (age_months >= min_age)

def find_products_by_category_keyword(keyword):
    """Return list of products whose name or product_type contains keyword."""
    k = keyword.lower()
    results = []
    for p in products:
        if k in p["product_name"].lower():
            results.append(p)
    return results

def find_product_by_name_or_partial(text):
    """Try to match a product by exact name or partial name in text. Returns first match or None."""
    txt = text.lower().strip()
    # exact match
    for p in products:
        if p["product_name"].lower() == txt:
            return p
    # partial match: check if product name contained as substring
    for p in products:
        if p["product_name"].lower() in txt or any(word in p["product_name"].lower() for word in txt.split()):
            return p
    # try matching by presence of a product name in the text
    for p in products:
        if p["product_name"].lower() in txt:
            return p
    return None

def show_product_short(p):
    return f"- {p['product_name']}"

def show_product_full(p):
    info = []
    info.append(f"Product: {p['product_name']}")
    info.append(f"Description: {p.get('description','No description available.')}")
    info.append(f"Intended Uses: {p.get('intended_uses','Not specified.')}")
    info.append(f"Packaging: {p.get('packaging','Not specified.')}")
    info.append(f"Shelf Life: {p.get('shelf_life','Not specified.')}")
    # show composition nicely
    comp = p.get("composition", {})
    if comp:
        comp_lines = []
        for k, v in comp.items():
            comp_lines.append(f"  {k}: {v}")
        info.append("Composition:\n" + "\n".join(comp_lines))
    else:
        info.append("Composition: Not specified.")
    min_age = min_safe_age_months(p)
    if min_age and min_age > 0:
        info.append(f"⚠️ Not recommended for infants below {min_age} months.")
    return "\n".join(info)

def extract_nutrient_from_query(q):
    nutrients = ["protein","fat","calcium","sugar","energy","iron","zinc"]
    for n in nutrients:
        if n in q:
            return n
    return None

def get_best_product_by_nutrient(nutrient, candidates=None):
    """Return product with highest numeric value for nutrient (searches all or candidates)."""
    best = None
    best_val = -float('inf')
    search_space = candidates if candidates is not None else products
    for p in search_space:
        comp = p.get("_comp_norm", {})
        # check keys for nutrient
        val = None
        # direct key
        if nutrient in comp:
            val = comp[nutrient]
        else:
            # try various capitalization variants (already normalized keys)
            for k in comp:
                if nutrient == k or nutrient in k:
                    val = comp[k]
                    break
        if val:
            num = extract_number_from_text(str(val))
            if num is None:
                continue
            if num > best_val:
                best_val = num
                best = p
    return best, best_val if best is not None else (None, None)

# ---------------------------
# Session state
# ---------------------------
session = {
    "last_category": None,        # e.g., "milk", "butter", "yoghurt"
    "last_suggestions": [],       # list of product dicts (from last category listing)
    "last_product": None,         # product dict the user selected / asked for details about
    "expecting_yes_no": False,    # when bot asks a yes/no question
    "last_bot_question": None,    # store last specific question type
}

# ---------------------------
# Conversation helpers
# ---------------------------
def list_category_and_ask(category, products_list):
    session["last_category"] = category
    session["last_suggestions"] = products_list
    session["last_product"] = None
    if not products_list:
        print(f"Sorry — I couldn't find any products for '{category}'.")
        return
    print(f"We have the following {category} products:")
    for p in products_list:
        print(show_product_short(p))
    print("Which one would you like?")

def respond_ordering_info():
    print("You can place an order via the website — check the 'Contact Us' or 'Where to Buy' section. If you want, I can give you the contact page link text or phone number (if available).")
    session["expecting_yes_no"] = True
    session["last_bot_question"] = "anything_else"
    print("Would you like help with anything else? (yes/no)")

def ask_anything_else():
    session["expecting_yes_no"] = True
    session["last_bot_question"] = "anything_else"
    print("Would you like help with anything else? (yes/no)")

# ---------------------------
# Main loop
# ---------------------------
print("👋 Hi! I’m Lato Chatbot. Ask me anything about our products.")
print("Type 'exit' to quit.\n")

while True:
    user_input = input("> ").strip()
    if not user_input:
        continue
    q = user_input.lower().strip()

    # exit
    if q in ("exit","quit"):
        print("Goodbye, have a lovely day! 🥛")
        break

    # Yes/No handling when expected
    if session["expecting_yes_no"]:
        ans = q
        session["expecting_yes_no"] = False
        if ans in ("yes","y","sure","please","yeah","yep"):
            # continue conversation
            session["last_bot_question"] = None
            print("Sure — how may I help you today?")
            continue
        else:
            print("Thank you for visiting us! If you need anything else later, just ask. 🥛")
            break

    # Greeting
    if any(g in q for g in ["hi","hello","hey","good morning","good afternoon"]):
        print("Hello! I can help you find information about Lato products. Try asking about milk, butter, or yoghurt.")
        continue

    # Category queries
    if "milk" in q and not any(word in q for word in ["which","what","difference","differences","tell me","compare","compare to"]):
        milk_products = [p for p in products if "milk" in p["product_name"].lower()]
        list_category_and_ask("milk", milk_products)
        continue

    if "butter" in q and not any(word in q for word in ["which","what","difference","differences","tell me","compare","compare to"]):
        butter_products = [p for p in products if "butter" in p["product_name"].lower() or "butter" in p.get("product_name","").lower()]
        list_category_and_ask("butter", butter_products)
        continue

    if "yoghurt" in q or "yogurt" in q:
        yoghurt_products = [p for p in products if "yogh" in p["product_name"].lower() or "yogh" in p.get("description","").lower()]
        list_category_and_ask("yoghurt", yoghurt_products)
        continue

    # If user picks a product by name (exact or partial)
    picked = find_product_by_name_or_partial(q)
    if picked:
        # show full details and set as last_product
        print(show_product_full(picked))
        session["last_product"] = picked
        session["last_category"] = None
        session["last_suggestions"] = []
        # after showing details, ask if they want anything else
        ask_anything_else()
        continue

    # "tell me more about" or "details about {product}" and we have last suggestions
    if any(tok in q for tok in ["tell me more","tell me about","details about","difference","differences","compare","information on","info on"]):
        # if the user referenced a product name inside the query, try to find it
        p = find_product_by_name_or_partial(q)
        if p:
            print(show_product_full(p))
            session["last_product"] = p
            ask_anything_else()
            continue
        # else if there are last suggestions, print details of them
        if session["last_suggestions"]:
            for p in session["last_suggestions"]:
                print(show_product_full(p))
                print("-" * 30)
            ask_anything_else()
            continue
        print("Please tell me which product(s) you want details on (or ask for a category like 'milk').")
        continue

    # Age based recommendation: "what can i give my baby" or "what is best for my X-month/years old"
    if any(tok in q for tok in ["baby","infant","month","year","months","years"]):
        age_months = parse_age_to_months(q)
        if age_months is None:
            # maybe user only said 'baby' - ask for age
            print("Please specify the age of your child (e.g., '6 months' or '2 years').")
            continue

        # Very young: under 6 months
        if age_months < 6:
            print("For infants under 6 months, please consult a pediatrician before introducing Lato products. Breastmilk or formula is recommended for newborns.")
            ask_anything_else()
            continue

        # collect safe products
        safe_products = [p for p in products if is_safe_for_age(p, age_months)]
        # If user dislikes plain milk and is older than 12 months, prefer flavored/fortified
        if "don't like" in q or "doesn't like" in q or "doesnt like" in q or "does not like" in q or "doesn't like the taste" in q:
            # suggest flavored and fortified options that are safe
            flavored = [p for p in safe_products if any(k in p["product_name"].lower() for k in ["chocolate","vanilla","strawberry","flav","omega","custard"])]
            if flavored:
                names = ", ".join([p["product_name"] for p in flavored])
                print(f"I would recommend these flavored/fortified options for your child: {names}")
                ask_anything_else()
                continue

        # For 6-12 months: suggest porridge and certain yoghurts if appropriate
        if 6 <= age_months < 12:
            suggestions = []
            # prefer porridge
            for p in safe_products:
                if "porridge" in p["product_name"].lower() or "porridge" in p.get("description","").lower():
                    suggestions.append(p)
            # yoghurt might be okay depending on product notes; check safety
            for p in safe_products:
                if "yogh" in p["product_name"].lower():
                    suggestions.append(p)
            if suggestions:
                print("For 6–12 months, these are safer introductory options (but check with a pediatrician):")
                for s in suggestions:
                    print(show_product_short(s))
                ask_anything_else()
                continue
            else:
                print("I couldn't find clearly suitable Lato products for 6–12 months. Please consult a pediatrician.")
                ask_anything_else()
                continue

        # For 12 months and above: offer more choices; if toddler (1-3 years) prefer flavored
        if age_months >= 12:
            # recommend fortified/flavored or regular depending on taste
            flavored = [p for p in safe_products if any(k in p["product_name"].lower() for k in ["chocolate","vanilla","strawberry","flav","omega","custard","grow"])]
            if flavored:
                names = ", ".join([p["product_name"] for p in flavored])
                print(f"For a child of {age_months} months, these are good options: {names}")
                ask_anything_else()
                continue
            # otherwise return a few safe_products names
            names = ", ".join([p["product_name"] for p in safe_products[:6]])
            print(f"Suitable products include: {names}")
            ask_anything_else()
            continue

    # Nutrient-specific queries: "which has highest protein", "most calcium"
    nutrient = extract_nutrient_from_query(q)
    if nutrient:
        # if user referenced category in same prompt, restrict search; else global
        candidates = None
        if session["last_suggestions"]:
            candidates = session["last_suggestions"]
        best, val = get_best_product_by_nutrient(nutrient, candidates)
        if best:
            print(f"The product with highest {nutrient} is: {best['product_name']}")
            # show the exact composition line if available
            comp_val = None
            comp = best.get("_comp_norm", {})
            for k in comp:
                if nutrient in k:
                    comp_val = comp[k]
                    break
            if comp_val:
                print(f"{nutrient.capitalize()}: {comp_val}")
            print(show_product_full(best))
            ask_anything_else()
            continue
        else:
            print(f"Sorry, I couldn't find {nutrient} data for products.")
            continue

    # Shelf-life / "how long can i keep" queries
    if any(phrase in q for phrase in ["shelf life", "how long", "keep after purchase","how long can i keep"]):
        # if user referenced a product name, show its shelf life
        p = find_product_by_name_or_partial(q)
        if p:
            print(f"{p['product_name']} shelf life: {p.get('shelf_life','Not specified')}")
            ask_anything_else()
            continue
        # if there's a last_product in session
        if session["last_product"]:
            p = session["last_product"]
            print(f"{p['product_name']} shelf life: {p.get('shelf_life','Not specified')}")
            ask_anything_else()
            continue
        print("Which product's shelf life would you like to know?")
        continue

    # Simple comparison: "which is better ghee or butter"
    m = re.search(r'which is better (.+) or (.+)', q)
    if m:
        a = m.group(1).strip()
        b = m.group(2).strip()
        pa = find_product_by_name_or_partial(a)
        pb = find_product_by_name_or_partial(b)
        if pa and pb:
            # compare a few values: fat, protein, calcium if avail
            def numeric_from_comp(p, key):
                comp = p.get("_comp_norm", {})
                for k in comp:
                    if key in k:
                        return extract_number_from_text(str(comp[k])) or 0
                return 0
            fats = (numeric_from_comp(pa, "fat"), numeric_from_comp(pb, "fat"))
            prots = (numeric_from_comp(pa, "protein"), numeric_from_comp(pb, "protein"))
            # simple heuristic: if one has significantly more fat & better for frying/cooking -> recommend ghee/butter appropriately
            print(f"Comparison between {pa['product_name']} and {pb['product_name']}:")
            print(show_product_full(pa))
            print("-"*30)
            print(show_product_full(pb))
            # give a short recommendation
            if fats[0] > fats[1] + 10:
                print(f"\nRecommendation: {pa['product_name']} is higher in fat and more suitable for high-heat cooking; {pb['product_name']} is leaner.")
            elif fats[1] > fats[0] + 10:
                print(f"\nRecommendation: {pb['product_name']} is higher in fat and more suitable for high-heat cooking; {pa['product_name']} is leaner.")
            else:
                print("\nBoth products have similar nutritional profiles; choose based on intended use (baking vs cooking) and taste.")
            ask_anything_else()
            continue
        else:
            print("I couldn't find one or both product names you mentioned. Please use product names from our catalog.")
            continue

    # Ordering / how to get products
    if any(k in q for k in ["how can i get","where to buy","order","purchase"]):
        respond_ordering_info()
        continue

    # Fallback: try matching product by any word token in input (helpful if user typed 'tell me about Lato ESL Milk Pouch' but tokenization differs)
    tokens = q.split()
    matched = None
    for t in tokens:
        for p in products:
            if t in p["product_name"].lower():
                matched = p
                break
        if matched:
            break
    if matched:
        print(show_product_full(matched))
        session["last_product"] = matched
        ask_anything_else()
        continue

    # If nothing matched
    print("Sorry, I couldn’t understand that. You can ask about milk, butter, or yoghurt, ask for product recommendations, or say 'which has highest protein' or 'how can I get this product'.")
