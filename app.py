import streamlit as st
from groq import Groq
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import random
import string

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gs = gspread.authorize(creds)
sheet = client_gs.open("Savoria Reservation").sheet1

# Groq setup
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_order_id():
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

SYSTEM_PROMPT = """You are a friendly customer support assistant for Savoria Restaurant.

Business Info:
- Name: Savoria Restaurant
- Cuisine: Pakistani & Continental
- Hours: 12pm to 12am, 7 days a week
- Location: Main Boulevard, Peshawar
- Phone: 091-1234567

Menu Highlights:
- Karahi (Chicken/Mutton): Rs. 1500/2500
- Biryani: Rs. 400 per plate
- Grilled Steaks: Rs. 1800
- Pasta: Rs. 900
- Drinks: Sprite/Coke/Water: Rs. 150 each
- Desserts: Rs. 300 each

Policies:
- Home delivery available via call
- Reservations accepted
- No alcohol served

IMPORTANT RULES:
- When confirming a reservation, always end reply with EXACTLY:
RESERVATION_DATA:{"name":"customer name","guests":"number","datetime":"date and time","seating":"indoor/outdoor","order":"items ordered","total":"total in Rs","status":"Confirmed"}
- Never include order_id in RESERVATION_DATA, the system handles that
- When customer wants to cancel their FULL order, end reply with EXACTLY:
CANCEL_ORDER:True
- When customer wants to modify order (change items), treat it as a new reservation and output RESERVATION_DATA again with updated info
- Always be friendly and concise"""

st.set_page_config(page_title="Savoria Support", page_icon="🍽️")
st.title("🍽️ Savoria Restaurant")
st.caption("How can we help you today?")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_order_id" not in st.session_state:
    st.session_state.current_order_id = None
if "current_row" not in st.session_state:
    st.session_state.current_row = None

# Quick action buttons
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🍽️ Menu"):
        st.session_state.messages.append({"role": "user", "content": "Show me the menu"})
with col2:
    if st.button("📅 Reserve"):
        st.session_state.messages.append({"role": "user", "content": "I want to make a reservation"})
with col3:
    if st.button("🕐 Timings"):
        st.session_state.messages.append({"role": "user", "content": "What are your opening hours?"})
with col4:
    if st.button("📞 Contact"):
        st.session_state.messages.append({"role": "user", "content": "How can I contact you?"})

st.divider()

# Show current order ID if exists
if st.session_state.current_order_id:
    st.info(f"📋 Your current Order ID: **{st.session_state.current_order_id}**")

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "assistant":
        display_reply = msg["content"]
        display_reply = display_reply.split("RESERVATION_DATA:")[0].strip()
        display_reply = display_reply.split("CANCEL_ORDER:")[0].strip()
        st.chat_message("assistant").write(display_reply)
    else:
        st.chat_message(msg["role"]).write(msg["content"])

# Get AI response if last message is from user
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages
    )
    reply = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": reply})

    display_reply = reply.split("RESERVATION_DATA:")[0].strip()
    display_reply = display_reply.split("CANCEL_ORDER:")[0].strip()
    st.chat_message("assistant").write(display_reply)

    # Save or UPDATE reservation
    if "RESERVATION_DATA:" in reply:
        try:
            data_str = reply.split("RESERVATION_DATA:")[1].strip()
            data = json.loads(data_str)

            if st.session_state.current_row:
                # Update existing row
                row = st.session_state.current_row
                sheet.update_cell(row, 1, data.get("name", ""))
                sheet.update_cell(row, 2, data.get("guests", ""))
                sheet.update_cell(row, 3, data.get("datetime", ""))
                sheet.update_cell(row, 4, data.get("seating", ""))
                sheet.update_cell(row, 5, data.get("order", ""))
                sheet.update_cell(row, 6, data.get("total", ""))
                sheet.update_cell(row, 7, "Confirmed")
                st.success(f"✅ Order updated! ID: **{st.session_state.current_order_id}**")
            else:
                # New reservation
                new_order_id = generate_order_id()
                st.session_state.current_order_id = new_order_id
                sheet.append_row([
                    data.get("name", ""),
                    data.get("guests", ""),
                    data.get("datetime", ""),
                    data.get("seating", ""),
                    data.get("order", ""),
                    data.get("total", ""),
                    "Confirmed",
                    new_order_id
                ])
                all_rows = sheet.get_all_values()
                st.session_state.current_row = len(all_rows)
                st.success(f"✅ Reservation saved! Your Order ID: **{new_order_id}**")
        except Exception as e:
            st.error(f"Error saving: {e}")

    # Cancel reservation
    if "CANCEL_ORDER:True" in reply:
        try:
            if st.session_state.current_row:
                sheet.update_cell(st.session_state.current_row, 7, "Cancelled")
                st.warning(f"❌ Order **{st.session_state.current_order_id}** cancelled!")
                st.session_state.current_order_id = None
                st.session_state.current_row = None
            else:
                st.warning("No active order found to cancel.")
        except Exception as e:
            st.error(f"Error cancelling: {e}")

# Chat input
if prompt := st.chat_input("Ask something..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()