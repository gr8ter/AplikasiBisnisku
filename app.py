import streamlit as st
import gspread
import pandas as pd
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np 
from datetime import timedelta

# --- KONFIGURASI APLIKASI ---
st.set_page_config(
    page_title="Dashboard Bisnis GR8TER", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Kunci yang digunakan untuk koneksi gspread
SERVICE_ACCOUNT_FILE = '.streamlit/secrets.json' 
SHEET_NAME = 'Database Bisnisku' 

# --- FUNGSI CSS INJECTION (Ungu-Hijau Muda, Rounded) ---
def inject_custom_css():
    st.markdown("""
        <style>
            /* 1. Base Font & Theme */
            html, body, [class*="st-"] {
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            }
            /* 2. Warna Dasar (Ungu & Hijau Muda) */
            .stSidebar {
                background-color: #E0F2F1; /* Hijau muda */
            }
            /* 3. Button Styling (Rounded & Soft) */
            .stButton>button {
                background-color: #7350F2; /* Ungu Utama */
                color: white;
                border-radius: 12px; 
                border: none;
                padding: 10px 20px;
                transition: 0.3s;
            }
            .stButton>button:hover {
                background-color: #5F3CD8; 
            }
            /* 4. Input Styling (Rounded) */
            .stTextInput>div>div>input, .stNumberInput>div>div>input {
                border-radius: 8px;
                border: 1px solid #7350F2; 
                padding: 8px;
            }
            /* 5. Header Styling */
            h1, h2, h3 {
                color: #5F3CD8; 
            }
            /* 6. Tabs Styling */
            .stTabs [data-baseweb="tab-list"] button {
                border-radius: 8px 8px 0px 0px;
                font-weight: bold;
            }
        </style>
        """, 
        unsafe_allow_html=True)

# Panggil fungsi CSS di awal
inject_custom_css()


# --- FUNGSI KONEKSI GSPREAD (SUDAH DIPERBAIKI) ---
@st.cache_resource
def get_gspread_client():
    """Menginisialisasi koneksi Gspread yang stabil menggunakan oauth2client."""
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
        st.error("Gagal menemukan kredensial. Pastikan secrets.toml sudah dikonfigurasi di Streamlit Cloud.")
        return None

# --- FUNGSI LOAD DATA ---
@st.cache_data(ttl=5) 
def load_data(sheet_name):
    sh = get_gspread_client()
    if sh:
        try:
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_values()
            df = pd.DataFrame(data[1:], columns=data[0])
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    pass
            return df
        except gspread.WorksheetNotFound:
            st.warning(f"Worksheet '{sheet_name}' tidak ditemukan. Mohon cek kembali nama sheet di Google Sheets Anda.")
            return None
    return None

# --- FUNGSI BEP CALCULATION ---
def calculate_bep(fixed_cost, unit_cost, selling_price):
    if selling_price <= unit_cost:
        return "Harga Jual harus lebih besar dari Biaya Variabel per Unit!", 0, 0
    contribution_margin_per_unit = selling_price - unit_cost
    bep_unit = fixed_cost / contribution_margin_per_unit
    bep_revenue = bep_unit * selling_price
    return "BEP Berhasil Dihitung", bep_unit, bep_revenue


# --- PENGELOMPOKAN DATA BERDASARKAN BISNIS (ASUMSI NAMA SHEET) ---
# PASTIKAN NAMA SHEET INI SESUAI DENGAN GOOGLE SHEETS ANDA
df_beras_master = load_data("beras_master") 
df_beras_trx = load_data("beras_transaksi")
df_obat = load_data("master_obat") 
df_warkop_trx = load_data("warkop_transaksi") 


# --- LOGIKA TAMPILAN UTAMA ---

st.title("Dashboard Bisnis GR8TER")

# Membuat Tab Utama untuk setiap bisnis
tab_beras, tab_dokter, tab_warkop = st.tabs([
    "🌾 Beras Tuju-Tuju Mart", 
    "🩺 Praktek Dokter", 
    "☕ Warkop Pak Sorden"
])


# ===============================================================
# 1. TAB BERAS TUJU-TUJU MART (Master + Kasir + Utang/Piutang)
# ===============================================================
with tab_beras:
    st.header("Dashboard Beras Tuju-Tuju Mart")
    
    # Membuat SUB-TAB KHUSUS di dalam Tab Beras
    sub_tab_master, sub_tab_kasir = st.tabs(["Master Stok & Harga Beli", "Transaksi Kasir & Utang/Piutang"])
    
    with sub_tab_master:
        st.subheader("Pencatatan Master Stok & Harga Beli")
        
        # --- FORM INPUT MASTER BERAS ---
        with st.expander("➕ Input Stok/Master Beras Baru"):
            st.subheader("Input Data Master")
            
            col_name, col_buy, col_sell, col_stock = st.columns(4)
            with col_name:
                nama_beras = st.text_input("Nama/Jenis Beras", key="nama_beras_master")
            with col_buy:
                # 1. Harga Beli untuk Master
                harga_beli = st.number_input("**Harga Beli (per kg/unit)**", min_value=0, step=1000, key="hb_beras")
            with col_sell:
                 # 2. Harga Jual untuk Master
                harga_jual = st.number_input("**Harga Jual (per kg/unit)**", min_value=0, step=1000, key="hj_beras_master")
            with col_stock:
                stok = st.number_input("Stok Awal (kg)", min_value=0, step=1, key="stok_beras_master")
            
            if st.button("Simpan Master Beras", key="btn_save_master_beras"):
                st.success(f"Master {nama_beras} tersimpan.")
                st.cache_data.clear() 

        st.subheader("Data Master Beras Terbaru")
        if df_beras_master is not None:
            st.dataframe(df_beras_master.head(10), use_container_width=True)
        else:
            st.warning("Data Master Beras Tuju-Tuju Mart tidak dapat dimuat.")

    with sub_tab_kasir:
        st.subheader("Pencatatan Transaksi Kasir & Utang/Piutang")
        
        # --- FORM KASIR BERAS (Utang/Piutang) ---
        with st.expander("💸 Input Transaksi Penjualan/Pembelian Beras"):
            
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                # Pilihan Utang/Piutang/Tunai
                jenis_transaksi = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", "**Pembelian Utang (Kita Berutang ke Supplier)**"],
                    key="tr_type_beras"
                )
            with col_amount:
                jumlah = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_beras")
            with col_party:
                pihak = st.text_input("**Pihak Terkait** (Nama Pelanggan/Supplier)", key="tr_party_beras")
            
            st.text_area("Catatan Transaksi", max_chars=200, key="catatan_beras")
            
            if st.button("Simpan Transaksi Kasir", key="btn_save_transaksi_beras"):
                st.success(f"Transaksi {jenis_transaksi} sebesar Rp {jumlah:,.0f} dengan {pihak} tersimpan.")
                st.cache_data.clear() 

        st.subheader("Data Transaksi Terbaru Beras Tuju-Tuju Mart")
        if df_beras_trx is not None:
            st.dataframe(df_beras_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Beras Tuju-Tuju Mart tidak dapat dimuat.")


# ===============================================================
# 2. TAB PRAKTEK DOKTER (Master Obat Lengkap)
# ===============================================================
with tab_dokter:
    st.header("Dashboard Praktek Dokter")
    
    # --- FORM INPUT MASTER OBAT BARU ---
    with st.expander("➕ Input Master Obat Baru (Lengkap)"):
        st.subheader("Pencatatan Master Obat")
        
        col_name, col_price, col_unit = st.columns(3)
        with col_name:
            nama_obat = st.text_input("Nama Obat", key="nama_obat")
        with col_price:
            harga_per_biji = st.number_input("**Harga Jual (per biji)**", min_value=0, step=100, key="hj_obat")
        with col_unit:
            st.selectbox("**Satuan**", ["Box", "Strip", "Biji", "Botol"], key="satuan_obat")
            
        expired_date = st.date_input("Tanggal Kedaluwarsa (Expired Date)", key="ed_obat")
        
        if st.button("Simpan Master Obat", key="btn_save_master_obat"):
            st.success(f"Master {nama_obat} tersimpan.")
            st.cache_data.clear() 

    # --- DATA & WARNING EXPIRED DATE ---
    if df_obat is not None:
        st.subheader("Data Stok Obat & Peringatan Kedaluwarsa")
        
        today = pd.to_datetime('today').normalize()
        three_months_ahead = today + timedelta(days=90) 
        
        if 'Tanggal_Kedaluwarsa' in df_obat.columns:
            df_obat['Tanggal_Kedaluwarsa'] = pd.to_datetime(df_obat['Tanggal_Kedaluwarsa'], errors='coerce')
            
            expired_soon = df_obat[
                (df_obat['Tanggal_Kedaluwarsa'].dt.normalize() >= today) & 
                (df_obat['Tanggal_Kedaluwarsa'].dt.normalize() <= three_months_ahead)
            ].sort_values('Tanggal_Kedaluwarsa')
            
            if not expired_soon.empty:
                st.error(f"🚨 **PERINGATAN!** Ada {len(expired_soon)} item akan Kedaluwarsa dalam 3 Bulan:")
                st.dataframe(expired_soon[['Nama_Obat', 'Tanggal_Kedaluwarsa', 'Satuan', 'Harga_Jual_Per_Biji']], use_container_width=True)
            else:
                st.success("Semua stok obat aman dari kedaluwarsa dalam 3 bulan.")
        
        st.write("Data Stok Master Obat:")
        st.dataframe(df_obat.head(10), use_container_width=True)
    else:
        st.warning("Data Praktek Dokter tidak dapat dimuat.")


# ===============================================================
# 3. TAB WARKOP PAK SORDEN (Utang/Piutang & BEP)
# ===============================================================
with tab_warkop:
    st.header("Dashboard Warkop Pak Sorden")
    
    # Membuat SUB-TAB KHUSUS di dalam Tab Warkop
    sub_tab_dash, sub_tab_bep = st.tabs(["Transaksi Kasir (Utang/Piutang)", "Kalkulator BEP"])
    
    with sub_tab_dash:
        st.subheader("Pencatatan Kasir & Transaksi")
        
        # --- FORM KASIR WARKOP (Utang/Piutang) ---
        with st.expander("💸 Input Transaksi Penjualan Warkop"):
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                jenis_transaksi = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", "**Pembelian Utang (Kita Berutang ke Supplier)**"],
                    key="tr_type_warkop"
                )
            with col_amount:
                jumlah = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_warkop")
            with col_party:
                pihak = st.text_input("Pihak Terkait (Nama Pelanggan/Supplier)", key="tr_party_warkop")
            
            st.text_area("Catatan Transaksi", max_chars=200, key="catatan_warkop")
            
            if st.button("Simpan Transaksi", key="btn_save_transaksi_warkop"):
                st.success(f"Transaksi {jenis_transaksi} sebesar Rp {jumlah:,.0f} tersimpan.")
                st.cache_data.clear() 

        st.markdown("---")
        st.subheader("Data Transaksi Terbaru Warkop")
        if df_warkop_trx is not None:
            st.dataframe(df_warkop_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Warkop Pak Sorden tidak dapat dimuat.")
    
    with sub_tab_bep:
        st.subheader("Kalkulator BEP (Break-Even Point) untuk Menu Warkop")
        
        col_input, col_result = st.columns(2)
        
        with col_input:
            st.subheader("Input Biaya")
            fixed_cost = st.number_input("1. Biaya Tetap Bulanan", min_value=0.0, value=5000000.0, format="%.0f", key="fc_warkop")
            unit_cost = st.number_input("2. Biaya Variabel per Unit", min_value=0.0, value=5000.0, format="%.0f", key="uc_warkop")
            selling_price = st.number_input("3. Harga Jual per Unit", min_value=0.0, value=15000.0, format="%.0f", key="sp_warkop")
            
            calculate_button = st.button("Hitung BEP", key="bep_calc_btn")

        with col_result:
            st.subheader("Hasil Perhitungan")
            if calculate_button:
                message, bep_unit, bep_revenue = calculate_bep(fixed_cost, unit_cost, selling_price)
                
                if "Harga Jual" in message:
                    st.error(message)
                else:
                    st.success(message)
                    st.metric("Titik Impas (Unit)", f"{bep_unit:,.0f} Unit")
                    st.metric("Titik Impas (Rupiah)", f"Rp {bep_revenue:,.0f}")
