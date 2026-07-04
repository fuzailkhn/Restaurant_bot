import streamlit as st
from groq import Groq
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import random
import string
import hashlib
import re
from datetime import datetime

# ── Demo mode ─────────────────────────────────────────────────────────────────
DEMO_MODE = False  # Change to True for portfolio demo

DEMO_ORDERS = [
    {"Order ID":"ORD-DEMO1","Username":"demo","Type":"Delivery","Items":"Chicken Karahi x1, Drinks x2","Total":"1800","Contact Details":"House 12, Hayatabad, 0300-1234567","Status":"Delivered","Timestamp":"2026-07-01 14:30"},
    {"Order ID":"ORD-DEMO2","Username":"demo","Type":"Takeaway","Items":"Biryani x2","Total":"800","Contact Details":"Ahmed, 0311-9876543","Status":"Preparing","Timestamp":"2026-07-04 12:00"},
    {"Order ID":"ORD-DEMO3","Username":"demo","Type":"Delivery","Items":"Grilled Steak x1, Pasta x1","Total":"2700","Contact Details":"Flat 5, University Road, 0333-1112233","Status":"Out for Delivery","Timestamp":"2026-07-04 13:45"},
]

# ── Google Sheets ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_sheets():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc = gspread.authorize(creds)
    sp = gc.open("Savoria Reservation")
    sh1 = sp.sheet1
    try:
        ush = sp.worksheet("Users")
    except gspread.WorksheetNotFound:
        ush = sp.add_worksheet("Users", 500, 6)
        ush.append_row(["Username","Password Hash","Full Name","Phone","Registered At"])
    try:
        osh = sp.worksheet("Orders")
    except gspread.WorksheetNotFound:
        osh = sp.add_worksheet("Orders", 1000, 8)
        osh.append_row(["Order ID","Username","Type","Items","Total","Contact Details","Status","Timestamp"])
    return sh1, ush, osh

if not DEMO_MODE:
    sheet, users_sheet, orders_sheet = get_sheets()

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ── Helpers ───────────────────────────────────────────────────────────────────
def gen_id():
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_users():
    if DEMO_MODE:
        return [{"Username":"demo","Password Hash":hash_pw("demo123"),"Full Name":"Demo User","Phone":"0300-0000000"}]
    try: return users_sheet.get_all_records()
    except: return []

def find_user(uname):
    for u in get_users():
        if u.get("Username","").lower() == uname.lower(): return u
    return None

def login_user(uname, pw):
    if not uname or not pw: return False, "Enter both fields."
    u = find_user(uname)
    if not u: return False, "User not found. Register first."
    if u.get("Password Hash") != hash_pw(pw): return False, "Wrong password."
    return True, "OK"

def register_user(uname, pw, name, phone):
    if DEMO_MODE: return False, "Demo mode — registration disabled. Use demo/demo123."
    if not uname or not pw: return False, "Username and password required."
    if len(uname) < 3: return False, "Username too short (min 3)."
    if len(pw) < 6: return False, "Password too short (min 6)."
    if find_user(uname): return False, "Username already taken."
    users_sheet.append_row([uname, hash_pw(pw), name, phone, datetime.now().strftime("%Y-%m-%d %H:%M")])
    return True, "Registered!"

def get_all_orders():
    if DEMO_MODE: return DEMO_ORDERS
    try: return orders_sheet.get_all_records()
    except: return []

def get_user_orders(uname):
    return [o for o in get_all_orders() if o.get("Username","").lower() == uname.lower()]

def find_order_by_id(oid):
    for o in get_all_orders():
        if o.get("Order ID","").upper() == oid.upper(): return o
    return None

def save_order(oid, uname, otype, items, total, contact):
    if DEMO_MODE: return True
    orders_sheet.append_row([oid, uname, otype, items, total, contact, "Pending", datetime.now().strftime("%Y-%m-%d %H:%M")])
    return True

def update_order_status(oid, new_status):
    if DEMO_MODE: return True
    try:
        records = orders_sheet.get_all_records()
        for i, r in enumerate(records, start=2):
            if r.get("Order ID","").upper() == oid.upper():
                orders_sheet.update_cell(i, 7, new_status)
                return True
        return False
    except: return False

STATUS_EMOJI = {
    "Pending":"⏳ Pending","Confirmed":"✅ Confirmed","Preparing":"👨‍🍳 Preparing",
    "Out for Delivery":"🛵 Out for Delivery","Delivered":"✅ Delivered",
    "Cancelled":"❌ Cancelled","Ready for Pickup":"🏃 Ready for Pickup",
}
def fmt_status(s): return STATUS_EMOJI.get(s, s)

def detect_order_id(text):
    m = re.search(r'ORD-[A-Z0-9]{6}', text.upper())
    return m.group(0) if m else None

# ── Translations ──────────────────────────────────────────────────────────────
LANG = {
    "en": {
        "title":"🍽️ Savoria Restaurant","caption":"Your AI Restaurant Assistant",
        "login":"Login","register":"Register","username":"Username","password":"Password",
        "full_name":"Full Name","phone":"Phone","logout":"🚪 Logout",
        "my_orders":"📋 My Orders","track":"🔍 Track Order","clear":"🗑️ Clear Chat",
        "placeholder":"Type a message or paste your Order ID (ORD-XXXXXX) to track...",
        "please_login":"👈 Please login or register from the sidebar to start.",
        "welcome":"👋 Welcome to **Savoria Restaurant**!\n\nI can help you:\n- 🍽️ Browse the menu\n- 📅 Make a dine-in reservation\n- 🛵 Place delivery or takeaway order\n- 🔍 Track your order — just type your Order ID!\n\nWhat would you like today?",
        "ask_contact":"📍 **Almost done!** Please share:\n- **Delivery**: your full address + phone number\n- **Takeaway**: your name + phone number",
        "order_saved":"✅ **{type} order placed!**\n\n📋 Order ID: **{oid}**\n🍱 Items: {items}\n💰 Total: Rs. {total}\n📍 Details: {contact}\n\n_Save your Order ID to track anytime!_",
        "no_orders":"No orders yet.","recent_orders":"Recent Orders",
        "status_not_found":"❌ Order ID not found. Please check and try again.",
        "status_found":"📋 **Order Status**\n\n🆔 {oid}\n🛵 Type: {type}\n🍱 Items: {items}\n💰 Total: Rs. {total}\n📊 Status: **{status}**\n🕐 Placed: {time}",
        "demo_banner":"🎭 **DEMO MODE** — Portfolio demo. Login with `demo` / `demo123`",
    },
    "ur": {
        "title":"🍽️ سووریا ریسٹورنٹ","caption":"آپ کا AI ریسٹورنٹ اسسٹنٹ",
        "login":"لاگ ان","register":"رجسٹر","username":"یوزر نیم","password":"پاس ورڈ",
        "full_name":"پورا نام","phone":"فون نمبر","logout":"🚪 لاگ آوٹ",
        "my_orders":"📋 میرے آرڈرز","track":"🔍 آرڈر ٹریک","clear":"🗑️ چیٹ صاف کریں",
        "placeholder":"پیغام لکھیں یا آرڈر ID ڈالیں...",
        "please_login":"👈 سائیڈبار سے لاگ ان یا رجسٹر کریں۔",
        "welcome":"👋 **سووریا ریسٹورنٹ** میں خوش آمدید!\n\nمیں مدد کر سکتا ہوں:\n- 🍽️ مینیو دیکھنے میں\n- 📅 ریزرویشن کرنے میں\n- 🛵 آرڈر دینے میں\n- 🔍 آرڈر ٹریک کرنے میں\n\nکیسے مدد کروں؟",
        "ask_contact":"📍 **تقریباً ہو گیا!**\n- **ڈیلیوری**: پتہ + فون\n- **ٹیک اوے**: نام + فون",
        "order_saved":"✅ **{type} آرڈر ہو گیا!**\n\n📋 ID: **{oid}**\n🍱 {items}\n💰 روپے {total}\n📍 {contact}\n\n_ID محفوظ کریں — ٹریک کے لیے!_",
        "no_orders":"کوئی آرڈر نہیں۔","recent_orders":"حالیہ آرڈرز",
        "status_not_found":"❌ آرڈر ID نہیں ملی۔","status_found":"📋 **آرڈر کی حالت**\n\n🆔 {oid}\n🛵 {type}\n🍱 {items}\n💰 روپے {total}\n📊 **{status}**\n🕐 {time}",
        "demo_banner":"🎭 **ڈیمو موڈ** — `demo` / `demo123` سے لاگ ان کریں",
    }
}

def t(key): return LANG[st.session_state.get("lang","en")].get(key, key)

SYSTEM_EN = """You are a friendly AI assistant for Savoria Restaurant, Peshawar.

Menu:
- Karahi Chicken: Rs.1500 | Karahi Mutton: Rs.2500
- Biryani: Rs.400/plate | Grilled Steak: Rs.1800 | Pasta: Rs.900
- Drinks: Rs.150 | Desserts: Rs.300

Hours: 12pm-12am | Location: Main Boulevard, Peshawar | Phone: 091-1234567
Services: Dine-in, Takeaway, Home Delivery

RULES:
- Dine-in reservation → end reply with: RESERVATION_DATA:{"name":"x","guests":"x","datetime":"x","seating":"indoor/outdoor","order":"x","total":"x","status":"Confirmed"}
- Delivery/Takeaway → end reply with: ORDER_DATA:{"type":"Delivery","items":"x","total":"x"}
- Cancellation → end reply with: CANCEL_ORDER:True
- Be friendly, concise
- Reply in English unless customer writes in Urdu"""

SYSTEM_UR = """آپ سووریا ریسٹورنٹ کے AI اسسٹنٹ ہیں۔
مینیو: کڑاہی چکن 1500، مٹن 2500، بریانی 400، اسٹیک 1800، پاستا 900، مشروبات 150
ڈائن ان: RESERVATION_DATA:{"name":"x","guests":"x","datetime":"x","seating":"indoor/outdoor","order":"x","total":"x","status":"Confirmed"}
ڈیلیوری/ٹیک اوے: ORDER_DATA:{"type":"Delivery","items":"x","total":"x"}
منسوخی: CANCEL_ORDER:True
اردو میں جواب دیں۔"""

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Savoria Restaurant", page_icon="🍽️", layout="centered")

for k, v in {
    "messages":[], "current_order_id":None, "current_row":None,
    "logged_in":False, "user":None, "lang":"en",
    "awaiting_contact":False, "pending_order_data":None,
    "show_orders":False, "show_track":False,
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    lp = st.radio("🌐 Language", ["English","اردو"], horizontal=True)
    st.session_state.lang = "ur" if lp == "اردو" else "en"
    st.divider()

    if not st.session_state.logged_in:
        mode = st.radio(t("login")+" / "+t("register"), [t("login"), t("register")])
        with st.form("auth"):
            uname = st.text_input(t("username"))
            pwd = st.text_input(t("password"), type="password")
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
                    else: st.error(msg)
                else:
                    ok, msg = register_user(uname, pwd, fname, phone)
                    (st.success if ok else st.error)(msg)
    else:
        st.markdown(f"👤 **{st.session_state.user}**")
        st.write("")

        if st.button(t("my_orders"), use_container_width=True):
            st.session_state.show_orders = not st.session_state.show_orders
            st.session_state.show_track = False
        if st.session_state.show_orders:
            ords = get_user_orders(st.session_state.user)
            if ords:
                for o in ords[-5:]:
                    st.markdown(f"**{o.get('Order ID','')}** — {fmt_status(o.get('Status',''))}\n🍱 {o.get('Items','')}\n💰 Rs.{o.get('Total','')} | 🕐 {o.get('Timestamp','')}\n---")
            else: st.info(t("no_orders"))

        if st.button(t("track"), use_container_width=True):
            st.session_state.show_track = not st.session_state.show_track
            st.session_state.show_orders = False
        if st.session_state.show_track:
            tid = st.text_input("Order ID", placeholder="ORD-XXXXXX")
            if st.button("🔍 Check", use_container_width=True) and tid:
                o = find_order_by_id(tid.strip())
                if o:
                    st.markdown(f"**{o.get('Order ID')}**\n{fmt_status(o.get('Status',''))}\n🍱 {o.get('Items','')}\n💰 Rs.{o.get('Total','')}\n📍 {o.get('Contact Details','')}\n🕐 {o.get('Timestamp','')}")
                else: st.error(t("status_not_found"))

        st.divider()
        with st.expander("🔐 Admin Panel"):
            apw = st.text_input("Admin Password", type="password", key="apw")
            if apw == st.secrets.get("ADMIN_PASSWORD","savoria2024"):
                st.success("✅ Admin Access")
                pending = [o for o in get_all_orders() if o.get("Status") == "Pending"]
                if pending:
                    for o in pending:
                        st.markdown(f"**{o.get('Order ID')}** | {o.get('Type')}\n🍱 {o.get('Items')}\n📍 {o.get('Contact Details')}")
                        ns = st.selectbox("Status", ["Pending","Confirmed","Preparing","Out for Delivery","Ready for Pickup","Delivered","Cancelled"], key=f"s_{o.get('Order ID')}")
                        if st.button(f"Update", key=f"u_{o.get('Order ID')}"):
                            if update_order_status(o.get("Order ID"), ns):
                                st.success("Updated!"); st.rerun()
                else: st.info("No pending orders.")

        if st.button(t("logout"), use_container_width=True):
            for k in ["logged_in","user","messages","current_order_id","current_row","awaiting_contact","pending_order_data","show_orders","show_track"]:
                st.session_state[k] = [] if k=="messages" else (False if k in ["logged_in","show_orders","show_track"] else None)
            st.rerun()

    st.divider()
    if st.button(t("clear"), use_container_width=True):
        for k in ["messages","current_order_id","current_row","awaiting_contact","pending_order_data"]:
            st.session_state[k] = [] if k=="messages" else None
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.title(t("title"))
st.caption(t("caption"))
if DEMO_MODE: st.info(t("demo_banner"))

if not st.session_state.logged_in:
    st.info(t("please_login")); st.stop()

c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    if st.button("🍽️ Menu"): st.session_state.messages.append({"role":"user","content":"Show me the full menu"})
with c2:
    if st.button("📅 Reserve"): st.session_state.messages.append({"role":"user","content":"I want to make a reservation"})
with c3:
    if st.button("🛵 Order"): st.session_state.messages.append({"role":"user","content":"I want to order for delivery"})
with c4:
    if st.button("🔍 Track"): st.session_state.messages.append({"role":"user","content":"How do I track my order?"})
with c5:
    if st.button("📞 Call"): st.session_state.messages.append({"role":"user","content":"What is your contact number?"})

st.divider()

if st.session_state.current_order_id:
    st.info(f"📋 Active Order: **{st.session_state.current_order_id}**")

if not st.session_state.messages:
    st.session_state.messages.append({"role":"assistant","content":t("welcome")})

for msg in st.session_state.messages:
    content = msg["content"]
    if msg["role"] == "assistant":
        content = content.split("RESERVATION_DATA:")[0].split("ORDER_DATA:")[0].split("CANCEL_ORDER:")[0].strip()
    st.chat_message(msg["role"]).write(content)

# ── Logic ─────────────────────────────────────────────────────────────────────
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last = st.session_state.messages[-1]["content"]

    if st.session_state.awaiting_contact and st.session_state.pending_order_data:
        od = st.session_state.pending_order_data

        # ── Validate: must contain a phone number (10-11 digits) and enough text for address ──
        phone_found = re.search(r'(\+92|0)?[0-9]{10,11}', re.sub(r'\s','', last))
        address_found = len(last.strip()) >= 15  # at least 15 chars = real address

        if not phone_found or not address_found:
            # Ask again with a clear example
            if st.session_state.lang == "ur":
                retry_msg = (
                    "⚠️ براہ کرم اپنا **مکمل پتہ اور فون نمبر** دونوں لکھیں۔\n\n"
                    "مثال:\n"
                    "🏠 گھر نمبر 12، حیات آباد فیز 3، پشاور\n"
                    "📞 0300-1234567"
                )
            else:
                retry_msg = (
                    "⚠️ Please provide both your **full address AND phone number** to complete the order.\n\n"
                    "Example:\n"
                    "🏠 House 12, Hayatabad Phase 3, Peshawar\n"
                    "📞 0300-1234567"
                )
            st.chat_message("assistant").write(retry_msg)
            st.session_state.messages.append({"role":"assistant","content":retry_msg})
        else:
            # Valid — save the order
            new_id = gen_id()
            save_order(new_id, st.session_state.user, od.get("type",""), od.get("items",""), od.get("total",""), last)
            confirm = t("order_saved").format(type=od.get("type",""), oid=new_id, items=od.get("items",""), total=od.get("total",""), contact=last)
            st.chat_message("assistant").write(confirm)
            st.session_state.messages.append({"role":"assistant","content":confirm})
            st.success(f"✅ Order saved! ID: **{new_id}**")
            st.session_state.awaiting_contact = False
            st.session_state.pending_order_data = None
            st.session_state.current_order_id = new_id

    elif detect_order_id(last):
        oid = detect_order_id(last)
        o = find_order_by_id(oid)
        if o:
            reply = t("status_found").format(oid=o.get("Order ID",""), type=o.get("Type",""), items=o.get("Items",""), total=o.get("Total",""), status=fmt_status(o.get("Status","")), time=o.get("Timestamp",""))
        else:
            reply = t("status_not_found")
        st.chat_message("assistant").write(reply)
        st.session_state.messages.append({"role":"assistant","content":reply})

    else:
        system = SYSTEM_UR if st.session_state.lang == "ur" else SYSTEM_EN
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":system}] + st.session_state.messages[-12:]
        )
        reply = response.choices[0].message.content
        display = reply.split("RESERVATION_DATA:")[0].split("ORDER_DATA:")[0].split("CANCEL_ORDER:")[0].strip()
        st.chat_message("assistant").write(display)
        st.session_state.messages.append({"role":"assistant","content":reply})

        if "RESERVATION_DATA:" in reply:
            try:
                data = json.loads(reply.split("RESERVATION_DATA:")[1].strip().split("\n")[0])
                if st.session_state.current_row:
                    row = st.session_state.current_row
                    for i, key in enumerate(["name","guests","datetime","seating","order","total"], start=1):
                        sheet.update_cell(row, i, data.get(key,""))
                    sheet.update_cell(row, 7, "Confirmed")
                    st.success(f"✅ Reservation updated! ID: **{st.session_state.current_order_id}**")
                else:
                    new_id = gen_id()
                    st.session_state.current_order_id = new_id
                    sheet.append_row([data.get("name",""), data.get("guests",""), data.get("datetime",""), data.get("seating",""), data.get("order",""), data.get("total",""), "Confirmed", new_id])
                    st.session_state.current_row = len(sheet.get_all_values())
                    st.success(f"✅ Reservation saved! ID: **{new_id}**")
            except Exception as e: st.error(f"Reservation error: {e}")

        if "ORDER_DATA:" in reply:
            try:
                st.session_state.pending_order_data = json.loads(reply.split("ORDER_DATA:")[1].strip().split("\n")[0])
                st.session_state.awaiting_contact = True
                ask = t("ask_contact")
                st.chat_message("assistant").write(ask)
                st.session_state.messages.append({"role":"assistant","content":ask})
            except Exception as e: st.error(f"Order error: {e}")

        if "CANCEL_ORDER:True" in reply:
            try:
                if st.session_state.current_row:
                    sheet.update_cell(st.session_state.current_row, 7, "Cancelled")
                    st.warning(f"❌ Order **{st.session_state.current_order_id}** cancelled!")
                    st.session_state.current_order_id = None
                    st.session_state.current_row = None
                else: st.warning("No active order to cancel.")
            except Exception as e: st.error(f"Cancel error: {e}")

if prompt := st.chat_input(t("placeholder")):
    st.session_state.messages.append({"role":"user","content":prompt})
    st.rerun()
