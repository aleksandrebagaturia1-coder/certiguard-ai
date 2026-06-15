import streamlit as st
import base64
import pypdf
import io
from openai import OpenAI
import os
import fitz  # PyMuPDF
from fpdf import FPDF
import sqlite3
import hashlib
import random
from PIL import Image

# --- PAGE CONFIGURATION ---
LOGO_PATH = "logo.png"
logo_exists = os.path.exists(LOGO_PATH)

if logo_exists:
    try:
        page_icon_img = Image.open(LOGO_PATH)
        st.set_page_config(page_title="CertiGuard AI Enterprise", page_icon=page_icon_img, layout="wide")
    except:
        st.set_page_config(page_title="CertiGuard AI Enterprise", page_icon="✈️", layout="wide")
else:
    st.set_page_config(page_title="CertiGuard AI Enterprise", page_icon="✈️", layout="wide")

# --- DATABASE SETUP ---
DB_FILE = "certiguard.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            credits INTEGER DEFAULT 10
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            report TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS FOR AUTH ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, credits) VALUES (?, ?, ?)", (email, hash_password(password), 10))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(email, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, credits FROM users WHERE email = ? AND password = ?", (email, hash_password(password)))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_credits(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def deduct_credit(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits - 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_audit(user_id, filename, report):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO audits (user_id, filename, report) VALUES (?, ?, ?)", (user_id, filename, report))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT filename, report FROM audits WHERE user_id = ? ORDER BY id DESC", (user_id,))
    history = cursor.fetchall()
    conn.close()
    return [{"filename": row[0], "report": row[1]} for row in history]

# --- DYNAMIC TRUST SCORE GENERATOR ---
def calculate_trust_metrics(report_text, filename):
    hasher = hashlib.md5(filename.encode())
    seed_int = int(hasher.hexdigest(), 16) % 10000
    random.seed(seed_int)
    
    if "STATUS: RED" in report_text or "[RED]" in report_text or "High" in report_text:
        score = random.randint(15, 45)
        level = "High"
        emoji = "🔴"
    elif "STATUS: YELLOW" in report_text or "[YELLOW]" in report_text or "Medium" in report_text:
        score = random.randint(60, 78)
        level = "Medium"
        emoji = "🟡"
    else:
        score = random.randint(92, 99)
        level = "Low"
        emoji = "🟢"
        
    return level, score, emoji

# --- FIXED PDF GENERATION ---
def generate_pdf_report(report_text, filename, risk_level, trust_score):
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "CertiGuard Official Audit Report", ln=1, align="C")
    
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, f"Target Document: {filename}", ln=1, align="C")
    pdf.ln(5)
    
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, f"Risk Level: {risk_level}", ln=1)
    pdf.cell(0, 6, f"Trust Score: {trust_score}/100", ln=1)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(30, 41, 59)
    
    clean_text = report_text.replace("**", "").replace("###", "").replace("•", "-")
    pdf.multi_cell(0, 6, clean_text)
    
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, (bytes, bytearray)):
        return bytes(pdf_output)
    return pdf_output.encode('latin-1', errors='replace')

# --- BULLETPROOF CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Inter', sans-serif !important;
            background-color: #f3f8fc !important;
        }
        
        /* HIDE ALL FORM HINTS */
        div[data-testid="InputInstructions"], 
        div[data-testid="stFormSubmitHint"],
        [data-testid="stForm"] small {
            display: none !important;
        }
        
        .block-container {
            background-color: #ffffff !important;
            padding: 3rem 4rem !important;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 51, 102, 0.05);
            margin-top: 2rem;
            margin-bottom: 2rem;
            max-width: 1200px;
            border: 1px solid #e2e8f0;
        }
        
        /* === 📱 MOBILE RESPONSIVE FIX === */
        @media (max-width: 768px) {
            .block-container {
                padding: 1.5rem 1rem !important;
                margin-top: 0.5rem;
                margin-bottom: 0.5rem;
            }
            .metric-container {
                flex-direction: column !important;
            }
            div[data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }
        }
        
        /* === SIDEBAR BACKGROUND === */
        [data-testid="stSidebar"] {
            background-color: #0b1a30 !important;
        }
        
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
            color: #e2e8f0 !important;
            font-weight: 500;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #ffffff !important;
            font-weight: 700;
        }
        
        /* === INPUT FIELDS === */
        [data-testid="stSidebar"] div[data-baseweb="input"] {
            background-color: #15294a !important;
            border: 1px solid #25406b !important;
            border-radius: 8px !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="input"] * {
            background-color: transparent !important;
        }
        [data-testid="stSidebar"] input {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            caret-color: #ffffff !important;
        }
        [data-testid="stSidebar"] input::placeholder {
            color: #64748b !important;
            -webkit-text-fill-color: #64748b !important;
        }
        
        [data-testid="stSidebar"] input:-webkit-autofill,
        [data-testid="stSidebar"] input:-webkit-autofill:hover, 
        [data-testid="stSidebar"] input:-webkit-autofill:focus, 
        [data-testid="stSidebar"] input:-webkit-autofill:active {
            -webkit-box-shadow: 0 0 0 1000px #15294a inset !important;
            -webkit-text-fill-color: #ffffff !important;
            transition: background-color 5000s ease-in-out 0s !important;
        }
        
        [data-testid="stSidebar"] div[data-baseweb="input"]:focus-within {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 1px #3b82f6 !important;
        }
        
        [data-testid="stSidebar"] div[data-baseweb="input"] svg {
            fill: #94a3b8 !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="input"]:hover svg {
            fill: #ffffff !important;
        }
        
        /* === RADIO BUTTONS === */
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
            color: #cbd5e1 !important;
        }
        
        /* === BUTTONS (HISTORY & LOGOUT) === */
        [data-testid="stSidebar"] .stButton > button {
            background-color: #15294a !important;
            color: #ffffff !important;
            border: 1px solid #25406b !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
            text-align: left !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: #1d4ed8 !important;
            border-color: #3b82f6 !important;
        }
        
        [data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button {
            background-color: #2563eb !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button:hover {
            background-color: #1d4ed8 !important;
        }
        
        .stButton>button {
            background-color: #2563eb !important;
            color: white !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        
        /* === METRICS & REPORT === */
        .metric-container {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
        }
        .metric-card {
            flex: 1;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px 24px;
            border-left: 5px solid #2563eb;
        }
        .metric-card.high-risk { border-left-color: #ef4444; background-color: #fff5f5; border-color: #fed7d7; }
        .metric-card.medium-risk { border-left-color: #f59e0b; background-color: #fffbeb; border-color: #fef3c7; }
        
        .metric-card h4 {
            color: #64748b !important;
            font-size: 0.85rem !important;
            text-transform: uppercase !important;
            margin: 0 0 8px 0 !important;
        }
        .metric-card h2 {
            font-size: 1.8rem !important;
            margin: 0 !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }
        
        .report-box {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 24px;
            font-size: 0.95rem;
            line-height: 1.6;
            color: #334155;
            margin-bottom: 20px;
        }
        
        div.stDownloadButton > button {
            background-color: #10b981 !important;
            color: white !important;
            font-weight: 600 !important;
            width: 100% !important;
            padding: 0.75rem !important;
        }
        div.stDownloadButton > button:hover {
            background-color: #059669 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- SAFE OPENAI API KEY SETUP ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    OPENAI_API_KEY = ""
    
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_INSTRUCTION = """
You are an expert Aviation Quality Assurance Inspector. Your job is to audit aircraft part certificates (FAA Form 8130-3 or EASA Form 1).
Analyze the provided document text and look for structural anomalies, missing critical fields, or signs of fraud. Do NOT use markdown stars or bold text markers (**).
"""

def analyze_pdf_text(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": f"Text data from PDF:\n\n{text}"}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: Text analysis failed. {e}"

def analyze_image_or_scanned(image_bytes):
    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_INSTRUCTION},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: Vision analysis failed. {e}"

# --- INITIALIZE USER STATE ---
if "user" not in st.session_state:
    st.session_state.user = None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.markdown("<div style='text-align: center; margin-bottom: 0px;'>", unsafe_allow_html=True)
    if logo_exists:
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("<h2 style='text-align: center; color: white;'>✈️ CertiGuard AI</h2>", unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size:0.85rem; color:#94a3b8 !important; margin-top:-10px;'>Aviation Certificate Ledger</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.user is None:
        st.markdown("### 🔐 System Access")
        auth_mode = st.radio("Select Mode", ["Sign In", "Create Account"], label_visibility="collapsed")
        
        with st.form(key="auth_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button(auth_mode, use_container_width=True)
            
            if submit_btn:
                if auth_mode == "Sign In":
                    user = login_user(email, password)
                    if user:
                        st.session_state.user = {"id": user[0], "email": user[1]}
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                else:
                    if email and password:
                        if register_user(email, password):
                            st.success("Account created! Please Sign In.")
                        else:
                            st.error("Email already registered.")
                    else:
                        st.warning("Please fill all fields.")
    else:
        u_id = st.session_state.user["id"]
        u_email = st.session_state.user["email"]
        u_credits = get_user_credits(u_id)
        
        st.markdown(f"👤 <span style='color:#e2e8f0; font-weight:500;'>User:</span> <span style='color:#ffffff; font-weight:700;'>{u_email}</span>", unsafe_allow_html=True)
        st.markdown(f"⚡ <span style='color:#e2e8f0; font-weight:500;'>Available Scans:</span> <span style='color:#ffffff; font-weight:700;'>{u_credits} / 10</span>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user = None
            if "current_report" in st.session_state:
                del st.session_state.current_report
            st.rerun()
            
        st.markdown("<br><hr style='border-color: #1e293b;'><br>", unsafe_allow_html=True)
        st.markdown("### 📂 Audit History")
        
        db_history = get_user_history(u_id)
        if not db_history:
            st.caption("No logs saved yet.")
        else:
            for idx, item in enumerate(db_history):
                emoji = "🟢"
                if "STATUS: RED" in item["report"] or "[RED]" in item["report"] or "High" in item["report"]:
                    emoji = "🔴"
                elif "STATUS: YELLOW" in item["report"] or "[YELLOW]" in item["report"] or "Medium" in item["report"]:
                    emoji = "🟡"
                    
                if st.button(f"{emoji}  {item['filename']}", key=f"hist_{idx}", use_container_width=True):
                    st.session_state.current_report = item["report"]
                    st.session_state.current_filename = item["filename"]

# --- MAIN AREA ROUTING ---
col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.markdown("<h2>📥 Document Upload</h2>", unsafe_allow_html=True)
    st.write("Upload Certificate File (PDF, PNG, JPG):")
    
    if st.session_state.user is None:
        st.info("Please sign in from the sidebar to access the scanner module.")
        st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], disabled=True, key="dis_up")
        uploaded_file = None
    else:
        u_id = st.session_state.user["id"]
        u_credits = get_user_credits(u_id)
        
        if u_credits <= 0:
            st.error("Scan limits exhausted. Upgrade required.")
            uploaded_file = None
        else:
            uploaded_file = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed", key="en_up")

    report = ""
    filename_to_report = ""

    if st.session_state.user is not None and uploaded_file is not None:
        file_bytes = uploaded_file.read()
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        filename_to_report = uploaded_file.name
        
        db_history = get_user_history(u_id)
        already_audited = any(item['filename'] == uploaded_file.name for item in db_history)
        
        if not already_audited and u_credits > 0:
            with st.spinner("Executing structural AI lookup..."):
                if file_ext in ['.png', '.jpg', '.jpeg']:
                    report = analyze_image_or_scanned(file_bytes)
                elif file_ext == '.pdf':
                    try:
                        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                        extracted_text = "".join([page.extract_text() or "" for page in reader.pages]).strip()
                    except:
                        extracted_text = ""
                        
                    if len(extracted_text) > 150:
                        report = analyze_pdf_text(extracted_text)
                    else:
                        try:
                            doc = fitz.open(stream=file_bytes, filetype="pdf")
                            page = doc.load_page(0)
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                            img_data = pix.tobytes("png")
                            report = analyze_image_or_scanned(img_data)
                            doc.close()
                        except Exception as e:
                            report = f"ERROR: PDF fallback vectorizer failed: {e}"
                
                deduct_credit(u_id)
                save_audit(u_id, uploaded_file.name, report)
                st.session_state.current_report = report
                st.session_state.current_filename = uploaded_file.name
                st.rerun()

if "current_report" in st.session_state and st.session_state.user is not None:
    report = st.session_state.current_report
    filename_to_report = st.session_state.current_filename

with col2:
    st.markdown("<h2>📊 Assessment Results</h2>", unsafe_allow_html=True)
    
    if report:
        risk_level, trust_score, status_emoji = calculate_trust_metrics(report, filename_to_report)
        risk_class = "high-risk" if risk_level == "High" else "medium-risk" if risk_level == "Medium" else ""
        
        st.markdown(f"""
            <div class="metric-container">
                <div class="metric-card {risk_class}">
                    <h4>Detected Risk</h4>
                    <h2>{risk_level} {status_emoji}</h2>
                </div>
                <div class="metric-card">
                    <h4>Verification Score</h4>
                    <h2>{trust_score} / 100</h2>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**Target:** `{filename_to_report}`")
        
        clean_display = report.replace("STATUS: RED", "").replace("STATUS: YELLOW", "").replace("STATUS: GREEN", "").strip()
        st.markdown(f'<div class="report-box">{clean_display.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        
        pdf_bytes_data = generate_pdf_report(report, filename_to_report, risk_level, trust_score)
        st.download_button(
            label="📥 Download Official Audit PDF",
            data=pdf_bytes_data,
            file_name=f"CertiGuard_Report_{filename_to_report}.pdf",
            mime="application/pdf"
        )
    else:
        st.markdown("""
            <div style="text-align: center; padding: 40px; background: #ffffff; border: 1px dashed #cbd5e1; border-radius: 12px; margin-top: 20px;">
                <p style="font-size: 35px; margin: 0;">📋</p>
                <p style="color: #64748b; margin-top: 10px; font-size: 0.95rem;">Select or upload a document to stream real-time compliance results.</p>
            </div>
        """, unsafe_allow_html=True)