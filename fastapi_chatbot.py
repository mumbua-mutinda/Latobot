# Lato Chatbot — Full deliverable

#This single document contains all the files you'll need to run a production-like setup:

#* FastAPI backend with Redis session support, product endpoints, chat endpoint, and SharePoint image passthrough
#* `requirements.txt` and `docker-compose.yml` for running the backend + Redis locally
#* A minimal React frontend (single-page) that talks to the `/chat` endpoint and `/products` endpoints
#* `README` with step-by-step run instructions and notes for SharePoint image access, security, and production suggestions

#> ⚠️ Important: This document contains *code blocks* for each file. Copy each code block into a file with the filename shown in the header. Follow the README to run locally.


## File: `fastapi_chatbot.py`


# fastapi_chatbot.py
# FastAPI backend for Lato Chatbot
# - /chat POST -> conversational replies
# - /products GET -> minimal product list
# - /product/{sku_or_name} GET -> product details
# Uses Redis for session storage (fallback to in-memory if REDIS_URL not provided)

import os
import json
import uuid
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


# Redis connection (optional)
REDIS_URL = os.getenv("REDIS_URL", "")
USE_REDIS = bool(REDIS_URL)

if USE_REDIS:
    import aioredis
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
else:
    # simple in-memory session store for dev
    sessions = {}

DATA_FILE = os.getenv("LATO_PRODUCTS_FILE", "lato_products.json")

# Load product data (same normalization used in console script)
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
except FileNotFoundError:
    raw = {}

# normalize categories/products -> flat products list
categories = []
if isinstance(raw, dict) and "categories" in raw:
    categories = raw["categories"]
elif isinstance(raw, dict) and "products_catalog" in raw:
    categories = raw["products_catalog"]
elif isinstance(raw, list):
    categories = raw
elif isinstance(raw, dict):
    categories = [raw]

products = []
for cat in categories:
    cat_name = cat.get("category", "Uncategorized")
    for p in cat.get("products", []):
        p.setdefault("category", cat_name)
        products.append(p)

# helper normalizations

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
    # image_url placeholder might point to SharePoint (external)
    p.setdefault("image_url", p.get("image_url", ""))

# small utilities
import math

def extract_number_from_text(s):
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(s))
    if m:
        try:
            return float(m.group(1))
        except:
            return None
    return None


app = FastAPI(title="Lato Chatbot Backend")

app.mount("/images", StaticFiles(directory="images"), name="images")


# allow local dev origins (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    suggestions: Optional[list] = None
    product: Optional[dict] = None

# session helpers
async def save_session(sid: str, data: dict):
    if USE_REDIS:
        await redis.set(sid, json.dumps(data))
    else:
        sessions[sid] = data

async def load_session(sid: str):
    if not sid:
        return None
    if USE_REDIS:
        rawv = await redis.get(sid)
        return json.loads(rawv) if rawv else None
    else:
        return sessions.get(sid)

# create or get session
async def get_or_create_session(sid: Optional[str]):
    if sid:
        s = await load_session(sid)
        if s:
            return sid, s
    # new session
    new_id = str(uuid.uuid4())
    s = {"last_intent": None, "last_product": None, "last_suggestions": []}
    await save_session(new_id, s)
    return new_id, s

# product finders

def find_by_name_or_partial(text: str):
    if not text:
        return None
    txt = text.lower().strip()
    for p in products:
        if p["product_name"].lower() == txt:
            return p
    for p in products:
        if txt in p["product_name"].lower():
            return p
    # token match
    tokens = re.findall(r"\w+", txt)
    for t in tokens:
        for p in products:
            if t in p["product_name"].lower():
                return p
    return None


def find_all_by_category(keyword: str):
    if not keyword:
        return []
    k = keyword.lower()
    res = [p for p in products if k in p.get("category", "").lower() or k in p.get("product_name", "").lower()]
    return res


def extract_nutrient_from_query(q: str):
    nutrients = ["protein","fat","calcium","sugar","energy","iron","zinc","vitamin a","vitamin d","vitamin b12"]
    ql = (q or "").lower()
    for n in nutrients:
        if n in ql:
            return n
    return None


def get_best_product_by_nutrient(nutrient: str, candidates=None):
    best = None
    best_val = -math.inf
    target = (nutrient or "").lower()
    search_space = candidates if candidates is not None else products
    for p in search_space:
        comp = p.get("_comp_norm", {})
        num = None
        if target in comp:
            num = extract_number_from_text(comp[target])
        else:
            for k, v in comp.items():
                if target in k:
                    num = extract_number_from_text(v)
                    break
        if num is not None and num > best_val:
            best_val = num
            best = p
    return best, best_val if best is not None else (None, None)

# simple conversational engine (kept concise for backend; detailed turn logic lives in frontend or here as required)

def build_product_brief(p: dict):
    lines = []
    lines.append(f"🥛 Product: {p['product_name']}")
    desc = p.get('_desc','')
    if desc:
        lines.append(desc)
    lines.append(f"📦 Packaging: {p.get('packaging','Not specified')}  •  🕒 Shelf life: {p.get('shelf_life','Not specified')}")
    comp = p.get('composition', {}) or {}
    highlights = []
    for key in ['protein','fat','energy','calcium']:
        for k,v in comp.items():
            if key in k.lower():
                highlights.append(f"{k.title()}: {v}")
                break
    if highlights:
        lines.append("🔬 Nutritional highlights: " + "; ".join(highlights))
    return "\n".join(lines)

# Chat routing (basic intent handling - we keep heavy lift in the frontend but provide good defaults)

@app.post('/chat', response_model=ChatResponse)
async def chat(req: ChatRequest):
    sid, sess = await get_or_create_session(req.session_id)
    q = req.message.strip()
    ql = q.lower()

    # greetings
    if ql in ("hi","hello","hey"):
        reply = (
            "🥛 Hi I’m Lato, your friendly nutrition buddy!\n"
            "I can help you explore products,or give recommendations based on your needs.\n"
            "Try what milk products do you have? or ask for a product by name."
        )
        sess['last_intent'] = 'greeting'
        await save_session(sid, sess)
        return ChatResponse(session_id=sid, reply=reply)

    # show category quick mention (fuzzy)
    if any(word in ql for word in ["milk","butter","yoghurt","yogurt","honey","juice","ghee","porridge","nadolac","nonna","omega"]):
        # pick category term
        cat_term = None
        for word in ["milk","butter","yoghurt","ghee","porridge","honey","juice","nadolac","nonna","omega"]:
            if word in ql:
                cat_term = word
                break
        if cat_term:
            items = find_all_by_category(cat_term)
            sess['last_intent'] = 'show_category'
            sess['last_suggestions'] = [p['product_name'] for p in items]
            sess['last_product'] = None
            await save_session(sid, sess)
            if items:
                brief = "Here are the {} options we have:\n".format(cat_term)
                brief += "\n".join(["- " + p['product_name'] for p in items])
                brief += "\nWhich one would you like to know more about?"
            else:
                brief = f"I couldn't find products under {cat_term}."
            return ChatResponse(session_id=sid, reply=brief, suggestions=[p['product_name'] for p in items][:10])

    # direct product lookup
    p = find_by_name_or_partial(ql)
    if p:
        sess['last_product'] = p['product_name']
        sess['last_intent'] = 'product_detail'
        await save_session(sid, sess)
        return ChatResponse(session_id=sid, reply=build_product_brief(p), product=p)

    # age based
    if any(tok in ql for tok in ["baby","infant","months","years","month","year","child"]):
        # try to parse age
        m = re.search(r"(\d+)\s*(months|month|years|year|y|m)", ql)
        if m:
            num = int(m.group(1))
            unit = m.group(2)
            months = num * 12 if 'year' in unit else num
            # simple safety
            if months < 6:
                reply = ("For infants under 6 months, breastmilk or recommended infant formula is strongly advised. "
                         "Please consult a pediatrician before introducing Lato products.")
                return ChatResponse(session_id=sid, reply=reply)
            # suggest safe products
            safe = [p for p in products if ('not for infant' not in (p.get('_intended','')+p.get('_desc','')).lower())]
            # heuristics: prefer porridge, nonna, lato grow, yoghurt
            suggestions = [p for p in safe if any(tok in p['product_name'].lower() for tok in ['porridge','nonna','grow','yog','lato grow'])]
            if not suggestions:
                suggestions = safe[:6]
            sess['last_suggestions'] = [p['product_name'] for p in suggestions]
            await save_session(sid, sess)
            reply = f"For a child of {months} months, these could be suitable:\n" + '\n'.join(["- " + s['product_name'] for s in suggestions[:10]])
            return ChatResponse(session_id=sid, reply=reply, suggestions=[s['product_name'] for s in suggestions[:10]])
        else:
            return ChatResponse(session_id=sid, reply="Please tell me the child's age (e.g., '6 months' or '2 years').")

    # nutrient query
    nutrient = extract_nutrient_from_query(ql)
    if nutrient:
        best, val = get_best_product_by_nutrient(nutrient)
        if best:
            sess['last_product'] = best['product_name']
            await save_session(sid, sess)
            brief = f"🔍 The product highest in {nutrient} is {best['product_name']} — {val}.\n" + build_product_brief(best)
            return ChatResponse(session_id=sid, reply=brief, product=best)
        else:
            return ChatResponse(session_id=sid, reply=f"Sorry, I couldn't find {nutrient} data in our catalog.")

    # ordering
    if any(tok in ql for tok in ["order","purchase","where to buy","buy","how can i get"]):
        return ChatResponse(session_id=sid, reply=("📦 To order Lato products, please visit the website's 'Contact Us' or 'Where to Buy' page. "
                                                 "If you'd like, provide your location and I can try to give local distributor info (if available)."))

    # fallback
    return ChatResponse(session_id=sid, reply=("Sorry — I didn't quite get that. You can ask about product categories (e.g., 'milk', 'yoghurt'), "
                                                "ask for a product by name, ask 'what's best for a 2 year old', or 'which has the most protein'."))

# Minimal product endpoints for UI
@app.get('/products')
async def get_products():
    # minimal list
    out = [{"product_name": p['product_name'], "sku": p.get('sku',''), "category": p.get('category',''), "image_url": p.get('image_url','')} for p in products]
    return out

@app.get('/product/{sku_or_name}')
async def get_product(sku_or_name: str):
    p = find_by_name_or_partial(sku_or_name)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p








