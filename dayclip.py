import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import gridfs
import time

# -------- PAGE SETTINGS --------
st.set_page_config(page_title="Cloud Clipboard", layout="wide")

# Custom CSS for a clean, full-screen interface
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container { 
        padding-top: 0.5rem; 
        padding-bottom: 0rem; 
        padding-left: 1.5rem; 
        padding-right: 1.5rem; 
    }
    textarea { 
        font-family: 'Source Code Pro', monospace !important; 
        font-size: 16px !important; 
        line-height: 1.5 !important;
    }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ---------- MongoDB Connection ----------
@st.cache_resource
def get_db():
    # Ensure MONGO_URI is set in your st.secrets
    client = MongoClient(st.secrets["MONGO_URI"])
    db = client["online_clipboard"]
    return db, gridfs.GridFS(db)

db, fs = get_db()
notes_collection = db["notes"]

# ---------- SESSION STATE ----------
if "last_persisted" not in st.session_state:
    note = notes_collection.find_one({"name": "main_note"})
    st.session_state.last_persisted = note["text"] if note else ""
    st.session_state.last_saved_time = note["updated"] if note else None

# ---------- AUTO-SAVE LOGIC (Fragment) ----------
@st.fragment(run_every="2s")
def sync_logic(current_text):
    if current_text != st.session_state.last_persisted:
        now = datetime.utcnow()
        notes_collection.update_one(
            {"name": "main_note"},
            {"$set": {
                "text": current_text,
                "updated": now
            }},
            upsert=True
        )
        st.session_state.last_persisted = current_text
        st.session_state.last_saved_time = now
        st.toast("Saved to Cloud")

# ---------- HEADER SECTION ----------
col_head, col_meta = st.columns([7, 3])
with col_head:
    st.subheader("notes")

with col_meta:
    if st.session_state.last_saved_time:
        # Convert UTC to local style display
        st.caption(f"Last saved: {st.session_state.last_saved_time.strftime('%H:%M:%S')} (UTC)")

# ---------- TEXT EDITOR ----------
# Key "clipboard_area" ensures Streamlit tracks this widget's state
text_input = st.text_area(
    "label_hidden",
    value=st.session_state.last_persisted,
    height=600,
    label_visibility="collapsed",
    key="clipboard_area"
)

# Run the background sync fragment
sync_logic(text_input)

# ---------- FILE MANAGEMENT ----------
st.markdown("---")
with st.expander("📁 Files & Uploads", expanded=False):
    
    # Upload Section
    uploaded_files = st.file_uploader("Drag files here", accept_multiple_files=True)
    if uploaded_files:
        for file in uploaded_files:
            if not fs.exists({"filename": file.name}):
                # GridFS stores the file and returns a file ID
                fs.put(file.getvalue(), filename=file.name, uploadDate=datetime.utcnow())
        st.success("Upload complete!")
        time.sleep(1)
        st.rerun()

    st.markdown("### Recent Files")
    
    # FIX: Use count_documents on the underlying collection to avoid GridOutCursor error
    file_count = db["fs.files"].count_documents({})
    
    if file_count > 0:
        # Fetch metadata only for the list
        files = fs.find().sort("uploadDate", -1).limit(15)
        
        h1, h2, h3 = st.columns([6, 2, 2])
        h1.caption("Filename")
        h2.caption("Action")
        h3.caption("Danger Zone")

        for file in files:
            c1, c2, c3 = st.columns([6, 2, 2])
            
            with c1:
                st.write(f"📄 {file.filename}")
            
            with c2:
                # Download Button - file.read() is called only when clicked
                st.download_button(
                    "Download", 
                    file.read(), 
                    file_name=file.filename, 
                    key=f"dl_{file._id}"
                )
            
            with c3:
                # Delete Button
                if st.button("Delete", key=f"del_{file._id}", type="secondary"):
                    fs.delete(file._id)
                    st.toast(f"Deleted {file.filename}")
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.info("No files uploaded yet.")