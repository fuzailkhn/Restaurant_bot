import streamlit as st
from groq import Groq
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import random
import string
import hashlib
from datetime import datetime

# ── Google Sheets setup ───────────────────────────────────────────────────────
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gs = gspread.authorize(creds)
spreadsheet = client_gs.open("Savoria Reservation")

sheet = spreadsheet.sheet1  # existing reservations sheet

try:
    users_sheet = spreadsheet.worksheet("Users")
except gspread.WorksheetNotFound:
    users_sheet = spreadsheet.add_worksheet(title="Users", rows=500, cols=6)
    users_sheet.append_row(["Username", "Password Hash", "Full Name", "Phone", "Registered At"])

try:
    orders_sheet = spreadsheet.worksheet("Orders")
except gspread.WorksheetNotFound:
    orders_sheet = spreadsheet.add_worksheet(title="Orders", rows=1000, cols=8)
    orders_sheet.append_row(["Order ID", "Username", "Type", "Items", "Total", "Contact Details", "Status", "Timestamp"])

# ── Groq setup ────────────────────────────────────────────────────────────────
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ── Helpers ───────────────────────────────────────────────────────────────────
def generate_order_id():
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_all_users():
    try:
        return users_sheet.get_all_records()
    except Exception:
        return []

def find_user(username):
    for u in get_all_users():
        if u.get("Username", "").lower() == username.lower():
            return u
    return None

def login_user(username, password):
    if not username or not password:
        return False, "Enter both fields."
    u = find_user(username)
    if not u:
        return False, "User not found. Please register."
    if u.get("Password Hash") != hash_password(password):
        return False, "Wrong password."
    return True, "OK"

def register_user(username, password, name, phone):
    if not username or not password:
        return False, "Username and password required."
    if len(username) < 3:
        return False, "Username too short (min 3 chars)."
    if len(password) < 6:
        return False, "Password too short (min 6 chars)."
    if find_user(username):
        return False, "Username already taken."
    users_sheet.append_row([username, hash_password(password), name, phone,
                             datetime.now().strftime("%Y-%m-%d %H:%M")])
    return True, "Registered successfully!"

def save_delivery_order(order_id, username, order_type, items, total, contact):
    orders_sheet.append_row([order_id, username, order_type, items, total,
                              contact, "Pending", datetime.now().strftime("%Y-%m-%d %H:%M")])

def get_user_orders(username):
    try:
        return [r for r in orders_sheet.get_all_records()
                if r.get("Username", "").lower() == username.lower()]
    except Exception:
        return []

# ── Translations ──────────────────────────────────────────────────────────────
LANG = {
    "en": {
        "title": "🍽️ Savoria Restaurant",
        "caption": "How can we help you today?",
        "login": "Login", "register": "Register",
        "username": "Username", "password": "Password",
        "full_name": "Full Name", "phone": "Phone",
        "logout": "🚪 Logout", "my_orders": "📋 My Orders",
        "clear": "🗑️ Clear Chat",
        "placeholder": "Ask something...",
        "please_login": "👈 Please login or register from the sidebar to start chatting.",
        "welcome": "👋 Welcome to **Savoria Restaurant**! How can I help you today?",
        "ask_contact": "📍 **Almost done!** Please share:\n- **Delivery**: full address + phone\n- **Takeaway**: your name + phone",
        "order_confirmed": "✅ **{type} order saved!** Your Order ID: **{oid}**\nWe'll confirm shortly.",
        "no_orders": "No delivery/takeaway orders yet.",
        "recent_orders": "Recent Orders",
    },
    "ur": {
        "title": "🍽️ سووریا ریسٹورنٹ",
        "caption": "آج ہم آپ کی کیسے مدد کر سکتے ہیں؟",
        "login": "لاگ ان", "register": "رجسٹر",
        "username": "یوزر نیم", "password": "پاس ورڈ",
        "full_name": "پورا نام", "phone": "فون نمبر",
        "logout": "🚪 لاگ آوٹ", "my_orders": "📋 میرے آرڈرز",
        "clear": "🗑️ چیٹ صاف کریں",
        "placeholder": "کچھ پوچھیں...",
        "please_login": "👈 چیٹ شروع کرنے کے لیے سائیڈبار سے لاگ ان یا رجسٹر کریں۔",
        "welcome": "👋 **سووریا ریسٹورنٹ** میں خوش آمدید! آج میں آپ کی کیسے مدد کروں؟",
        "ask_contact": "📍 **تقریباً ہو گیا!** براہ کرم بتائیں:\n- **ڈیلیوری**: مکمل پتہ + فون نمبر\n- **ٹیک اوے**: نام + فون نمبر",
        "order_confirmed": "✅ **{type} آرڈر محفوظ!** آپ کی ID: **{oid}**\nہم جلد تصدیق کریں گے۔",
        "no_orders": "ابھی کوئی ڈیلیوری/ٹیک اوے آرڈر نہیں۔",
        "recent_orders": "حالیہ آرڈرز",
    }
}

def t(key):
    return LANG[st.session_state.get("lang", "en")].get(key, key)

# ── System prompts ────────────────────────────────────────────────────────────
SYSTEM_EN = """You are a friendly customer support assistant for Savoria Restaurant.

Business Info:
- Cuisine: Pakistani & Continental
- Hours: 12pm to 12am, 7 days a week
- Location: Main Boulevard, Peshawar
- Phone: 091-1234567

Menu:
- Karahi (Chicken/Mutton): Rs. 1500/2500
- Biryani: Rs. 400/plate
- Grilled Steaks: Rs. 1800
- Pasta: Rs. 900
- Drinks: Rs. 150
- Desserts: Rs. 300

IMPORTANT RULES:
- For DINE-IN RESERVATIONS, end your reply with EXACTLY (no extra text after):
RESERVATION_DATA:{"name":"name","guests":"N","datetime":"date time","seating":"indoor/outdoor","order":"items","total":"Rs X","status":"Confirmed"}

- For DELIVERY or TAKEAWAY orders, end reply with EXACTLY:
ORDER_DATA:{"type":"Delivery","items":"items","total":"Rs X"}

- For cancellations: CANCEL_ORDER:True
- Never include order_id in data blocks
- Be friendly and concise
- Respond in English unless customer writes in Urdu"""

SYSTEM_UR = """آپ سووریا ریسٹورنٹ کے AI اسسٹنٹ ہیں۔

ریسٹورنٹ: پاکستانی و کانٹی نینٹل کھانا | اوقات: دوپہر 12 تا رات 12 | پشاور

مینیو:
- کڑاہی (چکن/مٹن): 1500/2500 روپے
- بریانی: 400 روپے
- گرلڈ اسٹیک: 1800 روپے
- پاستا: 900 روپے
- مشروبات: 150 روپے

ہدایات:
- ڈائن ان کے لیے: RESERVATION_DATA:{"name":"نام","guests":"تعداد","datetime":"وقت","seating":"indoor/outdoor","order":"اشیاء","total":"رقم","status":"Confirmed"}
- ڈیلیوری/ٹیک اوے کے لیے: ORDER_DATA:{"type":"Delivery","items":"اشیاء","total":"رقم"}
- منسوخی: CANCEL_ORDER:True
- اردو میں جواب دیں"""

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Savoria Support", page_icon="🍽️")

# ── Session defaults ──────────────────────────────────────────────────────────
for k, v in {
    "messages": [], "current_order_id": None, "current_row": None,
    "logged_in": False, "user": None, "lang": "en",
    "awaiting_contact": False, "pending_order_data": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    lang_pick = st.radio("🌐 Language", ["English", "اردو"], horizontal=True)
    st.session_state.lang = "ur" if lang_pick == "اردو" else "en"
    st.divider()

    if not st.session_state.logged_in:
        mode = st.radio(t("login") + " / " + t("register"), [t("login"), t("register")])
        with st.form("auth"):
            uname = st.text_input(t("username"))
            pwd   = st.text_input(t("password"), type="password")
            fname = phone = ""
            if mode == t("register"):
                fname = st.text_input(t("full_name"))
                phone = st.text_input(t("phone"))
            if st.form_submit_button(mode, use_container_width=True):
                if mode == t("login"):
                    ok, msg = login_user(uname, pwd)
                    if ok:
                        st.session_state.logged_in = True
                        st.session_state.user = uname
                        st.session_state.messages = []
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    ok, msg = register_user(uname, pwd, fname, phone)
                    (st.success if ok else st.error)(msg)
    else:
        st.markdown(f"👤 **{st.session_state.user}**")
        if st.button(t("my_orders"), use_container_width=True):
            orders = get_user_orders(st.session_state.user)
            if orders:
                st.markdown(f"**{t('recent_orders')}:**")
                for o in orders[-3:]:
                    st.markdown(f"**{o.get('Order ID','')}** · {o.get('Type','')}\n🍱 {o.get('Items','')}\n💰 Rs.{o.get('Total','')} · {o.get('Status','')}\n---")
            else:
                st.info(t("no_orders"))
        if st.button(t("logout"), use_container_width=True):
            for k in ["logged_in","user","messages","current_order_id","current_row","awaiting_contact","pending_order_data"]:
                st.session_state[k] = [] if k == "messages" else (False if k == "logged_in" else None)
            st.rerun()

    st.divider()
    if st.button(t("clear"), use_container_width=True):
        for k in ["messages","current_order_id","current_row","awaiting_contact","pending_order_data"]:
            st.session_state[k] = [] if k == "messages" else None
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.title(t("title"))
st.caption(t("caption"))

if not st.session_state.logged_in:
    st.info(t("please_login"))
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🍽️ Menu"):
        st.session_state.messages.append({"role":"user","content":"Show me the menu"})
with col2:
    if st.button("📅 Reserve"):
        st.session_state.messages.append({"role":"user","content":"I want to make a reservation"})
with col3:
    if st.button("🛵 Order"):
        st.session_state.messages.append({"role":"user","content":"I want to order for delivery"})
with col4:
    if st.button("📞 Contact"):
        st.session_state.messages.append({"role":"user","content":"How can I contact you?"})

st.divider()

if st.session_state.current_order_id:
    st.info(f"📋 Active Order ID: **{st.session_state.current_order_id}**")

if not st.session_state.messages:
    st.session_state.messages.append({"role":"assistant","content": t("welcome")})

for msg in st.session_state.messages:
    content = msg["content"]
    if msg["role"] == "assistant":
        content = content.split("RESERVATION_DATA:")[0].split("ORDER_DATA:")[0].split("CANCEL_ORDER:")[0].strip()
    st.chat_message(msg["role"]).write(content)

# ── AI + order processing ─────────────────────────────────────────────────────
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":

    if st.session_state.awaiting_contact and st.session_state.pending_order_data:
        contact = st.session_state.messages[-1]["content"]
        od = st.session_state.pending_order_data
        new_id = generate_order_id()
        save_delivery_order(new_id, st.session_state.user,
                            od.get("type",""), od.get("items",""),
                            od.get("total",""), contact)
        confirm = t("order_confirmed").format(type=od.get("type",""), oid=new_id)
        st.chat_message("assistant").write(confirm)
        st.session_state.messages.append({"role":"assistant","content": confirm})
        st.success(confirm)
        st.session_state.awaiting_contact = False
        st.session_state.pending_order_data = None
        st.session_state.current_order_id = new_id

    else:
        system = SYSTEM_UR if st.session_state.lang == "ur" else SYSTEM_EN
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":system}] + st.session_state.messages
        )
        reply = response.choices[0].message.content
        display = reply.split("RESERVATION_DATA:")[0].split("ORDER_DATA:")[0].split("CANCEL_ORDER:")[0].strip()
        st.chat_message("assistant").write(display)
        st.session_state.messages.append({"role":"assistant","content": reply})

        # Dine-in reservation (your original logic)
        if "RESERVATION_DATA:" in reply:
            try:
                data_str = reply.split("RESERVATION_DATA:")[1].strip().split("\n")[0]
                data = json.loads(data_str)
                if st.session_state.current_row:
                    row = st.session_state.current_row
                    for i, key in enumerate(["name","guests","datetime","seating","order","total"], start=1):
                        sheet.update_cell(row, i, data.get(key,""))
                    sheet.update_cell(row, 7, "Confirmed")
                    st.success(f"✅ Reservation updated! ID: **{st.session_state.current_order_id}**")
                else:
                    new_id = generate_order_id()
                    st.session_state.current_order_id = new_id
                    sheet.append_row([data.get("name",""), data.get("guests",""),
                                      data.get("datetime",""), data.get("seating",""),
                                      data.get("order",""), data.get("total",""),
                                      "Confirmed", new_id])
                    st.session_state.current_row = len(sheet.get_all_values())
                    st.success(f"✅ Reservation saved! ID: **{new_id}**")
            except Exception as e:
                st.error(f"Reservation error: {e}")

        # Delivery/Takeaway — collect contact next
        if "ORDER_DATA:" in reply:
            try:
                data_str = reply.split("ORDER_DATA:")[1].strip().split("\n")[0]
                st.session_state.pending_order_data = json.loads(data_str)
                st.session_state.awaiting_contact = True
                ask = t("ask_contact")
                st.chat_message("assistant").write(ask)
                st.session_state.messages.append({"role":"assistant","content": ask})
            except Exception as e:
                st.error(f"Order parse error: {e}")

        # Cancel (your original logic)
        if "CANCEL_ORDER:True" in reply:
            try:
                if st.session_state.current_row:
                    sheet.update_cell(st.session_state.current_row, 7, "Cancelled")
                    st.warning(f"❌ Order **{st.session_state.current_order_id}** cancelled!")
                    st.session_state.current_order_id = None
                    st.session_state.current_row = None
                else:
                    st.warning("No active order to cancel.")
            except Exception as e:
                st.error(f"Cancel error: {e}")

if prompt := st.chat_input(t("placeholder")):
    st.session_state.messages.append({"role":"user","content": prompt})
    st.rerun()
