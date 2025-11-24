import streamlit as st
import gspread
import pandas as pd
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np 
from datetime import timedelta
import time 

# --- KONFIGURASI APLIKASI & NAMA BISNIS ---
st.set_page_config(
    page_title="Dashboard Bisnis GR8TER", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Penyesuaian Nama Bisnis
NAMA_BISNIS_DOKTER = "PRAKTEK DOKTER UMUM\ndr. Putu Sannia Dewi, S.Ked"
NAMA_BISNIS_WARKOP = "WARKOP ES PAK SORDEN"
NAMA_BISNIS_BERAS = "TUJU-TUJU MART"


# Inisialisasi Session State
if 'resep_items' not in st.session_state:
    # Ditambah kolom 'harga' untuk tracking harga jual saat ini
    st.session_state.resep_items = [{'obat': '', 'jumlah': 0, 'aturan': '', 'harga': 0.0}] 
if 'bahan_items' not in st.session_state:
    st.session_state.bahan_items = [{'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0}] 

# Kunci yang digunakan untuk koneksi gspread
SERVICE_ACCOUNT_FILE = '.streamlit/secrets.json' 
SHEET_NAME = 'Database Bisnisku' 

# --- FUNGSI CSS PERBAIKAN ---
def inject_custom_css():
    st.markdown("""
        <style>
            /* 1. FIX TEKS GANDA/ARROW GANDA (ULTRA-EKSTREM) */
            div[data-testid="stExpander"] button > div:not(:last-child) > div > p,
            div[data-testid="stExpander"] button > div:first-child > svg,
            div[data-testid="stExpander"] > div > div > div > p {
                display: none !important; 
                visibility: hidden !important; 
            }
            div[data-testid="stExpander"] button > div:last-child > p {
                font-size: 1rem !important; 
                font-weight: bold !important;
                color: #5F3CD8 !important; 
            }
            
            /* 2. Styling Lanjutan */
            html, body, [class*="st-"] { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
            .stSidebar { background-color: #E0F2F1; }
            .stButton>button {
                background-color: #7350F2; color: white; border-radius: 12px; border: none;
                padding: 10px 20px; transition: 0.3s;
            }
            .stButton>button:hover { background-color: #5F3CD8; }
            .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div {
                border-radius: 8px; border: 1px solid #7350F2; padding: 8px;
            }
            h1, h2, h3 { color: #5F3CD8; }
            .stTabs [data-baseweb="tab-list"] button {
                border-radius: 8px 8px 0px 0px; font-weight: bold;
            }
            .stMetric [data-testid="stMetricDelta"] {
                color: #5F3CD8;
            }
        </style>
        """, 
        unsafe_allow_html=True)

inject_custom_css()


# --- FUNGSI KONEKSI GSPREAD & LOAD DATA ---
@st.cache_resource
def get_gspread_client():
    credentials_data = None
    if 'gcp_service_account' in st.secrets:
        original_data = st.secrets["gcp_service_account"]
        credentials_data = dict(original_data) 
    elif os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                credentials_data = json.load(f)
        except Exception:
            pass
    if credentials_data:
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_data, scope)
            gc = gspread.authorize(creds)
            return gc.open(SHEET_NAME)
        except Exception as e:
            st.error(f"Gagal saat menggunakan kredensial untuk koneksi gspread. Error: {e}")
            return None
    else:
        st.error("Gagal menemukan kredensial. Pastikan file secrets.json ada atau environment variable telah diset.")
        return None

@st.cache_data(ttl=5) 
def load_data(sheet_name):
    sh = get_gspread_client()
    if sh:
        try:
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_values()
            
            if not data or len(data) < 2:
                 df = pd.DataFrame(columns=data[0] if data else [])
                 return df

            df = pd.DataFrame(data[1:], columns=data[0])
            
            for col in df.columns:
                if 'harga' in col.lower() or 'biaya' in col.lower() or 'stok' in col.lower() or 'jumlah' in col.lower() or 'total' in col.lower():
                    # Bersihkan dan konversi angka
                    cleaned_col = df[col].astype(str).str.replace(',', 'TEMP', regex=False).str.replace('.', '', regex=False).str.replace('TEMP', '.', regex=False).str.strip()
                    df[col] = pd.to_numeric(cleaned_col, errors='coerce')
                
                if 'tanggal' in col.lower() or 'kedaluwarsa' in col.lower():
                    # Konversi tanggal
                    df[col] = pd.to_datetime(df[col].astype(str).str.strip(), errors='coerce')
            
            df = df.dropna(how='all') 
            
            return df
        except gspread.WorksheetNotFound:
            st.warning(f"Worksheet '{sheet_name}' tidak ditemukan. Mohon cek kembali nama sheet.")
            return None
        except Exception as e:
            st.error(f"Terjadi error saat memproses data sheet '{sheet_name}': {e}")
            return None
    return None

# --- FUNGSI BARU: UPDATE SEL TUNGGAL DI GOOGLE SHEETS ---
def update_sheet_cell(sheet_name, row_index, col_name, new_value):
    sh = get_gspread_client()
    if sh is None:
        return False
        
    try:
        worksheet = sh.worksheet(sheet_name)
        
        headers = worksheet.row_values(1)
        
        if col_name not in headers:
            st.error(f"Kolom '{col_name}' tidak ditemukan di sheet '{sheet_name}'.")
            return False
            
        col_index = headers.index(col_name) + 1
        
        # Penyesuaian index: row_index dari df (0-based) + 2 (karena header di baris 1)
        sheet_row_index = row_index + 2 
        
        worksheet.update_cell(sheet_row_index, col_index, new_value)
        
        return True
    except Exception as e:
        st.error(f"Gagal memperbarui sel di sheet {sheet_name}: {e}")
        return False


# --- FUNGSI SAVE DATA & MOCK (PENTING!) ---
def save_data(sheet_name, data_dict):
    """Fungsi Placeholder untuk menyimpan data ke Google Sheets."""
    sh = get_gspread_client()
    if sh is None:
        st.error("Gagal terhubung ke Google Sheets.")
        return False
        
    if sheet_name == "beras_master":
        row_to_append = [data_dict['nama_beras_master'], data_dict['hb_beras'], data_dict['hj_beras_master'], data_dict['stok_beras_master']]
    elif sheet_name == "beras_transaksi":
        # URUTAN: [Tanggal_Transaksi, Jenis_Transaksi, Produk, Jumlah_Transaksi, Pihak_Terkait, Catatan]
        row_to_append = [
            data_dict['tr_date_beras'].strftime('%Y-%m-%d'), 
            data_dict['tr_type_beras'],
            data_dict['tr_product_beras'], 
            data_dict['tr_amount_beras'],
