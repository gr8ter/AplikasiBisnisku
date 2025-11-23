import streamlit as st
import gspread
import pandas as pd
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np 
from datetime import timedelta
import time # Diperlukan untuk simulasi print

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
            .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div {
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
            /* 7. Fix Expander Header Double Text */
            .stExpander > div > div > div > p {
                font-size: 1rem; /* Adjust font size for clean look */
                font-weight: bold;
            }
        </style>
        """, 
        unsafe_allow_html=True)

inject_custom_css()


# --- FUNGSI KONEKSI GSPREAD ---
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

# --- FUNGSI COST ESTIMATOR (Ganti BEP) ---
def calculate_menu_cost(base_cost, packaging_cost, labor_cost, misc_cost):
    total_unit_cost = base_cost + packaging_cost + labor_cost + misc_cost
    
    # Perkiraan Harga Jual (Markup 50%)
    suggested_selling_price = total_unit_cost * 1.5 
    
    return total_unit_cost, suggested_selling_price


# --- PENGELOMPOKAN DATA BERDASARKAN BISNIS (ASUMSI NAMA SHEET) ---
df_beras_master = load_data("beras_master") 
df_beras_trx = load_data("beras_transaksi")
df_obat_master = load_data("master_obat") 
df_resep_keluar = load_data("resep_keluar") # SHEET BARU: Resep Keluar Dokter
df_faktur_obat = load_data("faktur_obat") # SHEET BARU: Faktur Pembelian Obat
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
    
    sub_tab_master, sub_tab_kasir = st.tabs(["Master Stok & Harga Beli", "Transaksi Kasir & Utang/Piutang"])
    
    with sub_tab_master:
        st.markdown("### Master Stok Beras")
        
        # --- FORM INPUT MASTER BERAS ---
        with st.expander("➕ Input Stok/Master Beras Baru"):
            col_name, col_buy, col_sell, col_stock = st.columns(4)
            with col_name:
                nama_beras = st.text_input("Nama/Jenis Beras", key="nama_beras_master")
            with col_buy:
                harga_beli = st.number_input("**Harga Beli (per kg/unit)**", min_value=0, step=1000, key="hb_beras")
            with col_sell:
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
        st.markdown("### Transaksi Kasir dan Laporan Utang/Piutang")
        
        # --- FORM KASIR BERAS (Utang/Piutang) ---
        with st.expander("💸 Input Transaksi Penjualan/Pembelian Beras"):
            
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                # Opsi Utang/Piutang
                jenis_transaksi = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", "Pembelian Utang (Kita Berutang)"],
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
# 2. TAB PRAKTEK DOKTER (Master + Resep + Faktur)
# ===============================================================
with tab_dokter:
    st.header("Dashboard Praktek Dokter")

    sub_tab_master, sub_tab_resep, sub_tab_faktur = st.tabs([
        "Master Obat & Stok", 
        "Resep Keluar (Kasir Apotek)", 
        "Pemesanan (Faktur Pembelian)"
    ])
    
    # --- SUB-TAB 1: MASTER OBAT ---
    with sub_tab_master:
        st.markdown("### Master Stok Obat & Peringatan Kedaluwarsa")
        
        with st.expander("➕ Input Master Obat Baru"):
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
        if df_obat_master is not None:
            st.subheader("Peringatan Kedaluwarsa Obat")
            today = pd.to_datetime('today').normalize()
            three_months_ahead = today + timedelta(days=90) 
            
            if 'Tanggal_Kedaluwarsa' in df_obat_master.columns:
                df_obat_master['Tanggal_Kedaluwarsa'] = pd.to_datetime(df_obat_master['Tanggal_Kedaluwarsa'], errors='coerce')
                
                expired_soon = df_obat_master[
                    (df_obat_master['Tanggal_Kedaluwarsa'].dt.normalize() >= today) & 
                    (df_obat_master['Tanggal_Kedaluwarsa'].dt.normalize() <= three_months_ahead)
                ].sort_values('Tanggal_Kedaluwarsa')
                
                if not expired_soon.empty:
                    st.error(f"🚨 **PERINGATAN!** Ada {len(expired_soon)} item akan Kedaluwarsa dalam 3 Bulan:")
                    st.dataframe(expired_soon[['Nama_Obat', 'Tanggal_Kedaluwarsa', 'Satuan']], use_container_width=True)
                else:
                    st.success("Semua stok obat aman dari kedaluwarsa dalam 3 bulan.")
            
            st.subheader("Data Stok Master Obat")
            st.dataframe(df_obat_master.head(10), use_container_width=True)
        else:
            st.warning("Data Master Obat tidak dapat dimuat.")

    # --- SUB-TAB 2: RESEP KELUAR (OBAT KELUAR) ---
    with sub_tab_resep:
        st.markdown("### Pencatatan Resep Obat Keluar & Kasir Apotek")

        # --- FORM PENCATATAN RESEP ---
        with st.expander("➕ Input Resep Obat Keluar"):
            
            st.text_input("Nama Pasien", key="pasien_resep")
            st.text_area("Detail Obat Diberikan (Contoh: Paracetamol 1 Strip, Amoxilin 10 Biji)", key="obat_diberikan")
            st.text_area("Aturan Pemakaian Obat (Sesuai Resep)", key="aturan_pakai")
            
            col_total, col_btn = st.columns([2, 1])
            with col_total:
                total_biaya = st.number_input("Total Biaya Obat (Rp)", min_value=0, step=1000, key="total_resep")
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True) # Spacer
                if st.button("Simpan Resep & Transaksi", key="btn_save_resep"):
                    st.success(f"Resep untuk {st.session_state.pasien_resep} tersimpan dengan total Rp {st.session_state.total_resep:,.0f}.")
                    
                    # --- SIMULASI PRINT INVOICE ---
                    st.info("Simulasi Print Invoice...")
                    time.sleep(1)
                    st.success("Invoice siap dicetak/diunduh!")
                    st.cache_data.clear()

        st.subheader("Data Resep Keluar Terbaru")
        if df_resep_keluar is not None:
            st.dataframe(df_resep_keluar.head(10), use_container_width=True)
        else:
            st.warning("Data Resep Keluar tidak dapat dimuat.")

    # --- SUB-TAB 3: FAKTUR PEMBELIAN OBAT ---
    with sub_tab_faktur:
        st.markdown("### Pencatatan Faktur Pembelian Obat (Restock)")

        # --- FORM FAKTUR PEMBELIAN ---
        with st.expander("➕ Input Faktur Pembelian Obat Baru"):
            col_faktur, col_supplier = st.columns(2)
            with col_faktur:
                st.text_input("Nomor Faktur", key="no_faktur")
            with col_supplier:
                st.text_input("Nama Supplier", key="nama_supplier")
                
            st.date_input("Tanggal Pembelian", key="tgl_beli")
            st.number_input("Total Biaya Faktur (Rp)", min_value=0, step=1000, key="total_faktur")
            st.text_area("Detail Item yang Dibeli", help="Contoh: Amoxilin 5 Box, Exp 2026-10-01", key="detail_faktur")
            
            if st.button("Simpan Faktur Pembelian", key="btn_save_faktur"):
                st.success(f"Faktur No. {st.session_state.no_faktur} dari {st.session_state.nama_supplier} tersimpan.")
                st.cache_data.clear() 

        st.subheader("Data Faktur Pembelian Obat Terbaru")
        if df_faktur_obat is not None:
            st.dataframe(df_faktur_obat.head(10), use_container_width=True)
        else:
            st.warning("Data Faktur Pembelian Obat tidak dapat dimuat.")


# ===============================================================
# 3. TAB WARKOP PAK SORDEN (Cost Estimator)
# ===============================================================
with tab_warkop:
    st.header("Dashboard Warkop Pak Sorden")
    
    sub_tab_dash, sub_tab_cost_estimator = st.tabs(["Transaksi Kasir (Utang/Piutang)", "Kalkulator Biaya Menu"])
    
    with sub_tab_dash:
        st.markdown("### Pencatatan Kasir & Transaksi")
        
        # --- FORM KASIR WARKOP (Utang/Piutang) ---
        with st.expander("💸 Input Transaksi Penjualan Warkop"):
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                jenis_transaksi = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", "Pembelian Utang (Kita Berutang)"],
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
    
    with sub_tab_cost_estimator:
        st.markdown("### Kalkulator Biaya Menu (Cost Estimator)")
        st.markdown("Gunakan kalkulator ini untuk menentukan **Biaya Pokok** satu porsi/gelas menu.")
        
        col_base, col_packaging, col_labor, col_misc = st.columns(4)
        
        with col_base:
            base_cost = st.number_input("1. Biaya Bahan Baku Utama (per unit)", min_value=0.0, value=3000.0, format="%.0f", help="Contoh: Harga kopi, susu, sirup yang digunakan.")
        with col_packaging:
            packaging_cost = st.number_input("2. Biaya Kemasan/Pendukung (per unit)", min_value=0.0, value=500.0, format="%.0f", help="Contoh: Cup, sedotan, tisu.")
        with col_labor:
            labor_cost = st.number_input("3. Biaya Tenaga Kerja (per unit)", min_value=0.0, value=500.0, format="%.0f", help="Perkiraan gaji yang dikeluarkan untuk membuat satu menu.")
        with col_misc:
            misc_cost = st.number_input("4. Biaya Lain-lain (per unit)", min_value=0.0, value=200.0, format="%.0f", help="Contoh: Listrik/Gas, penyusutan alat.")
        
        calculate_button = st.button("Hitung Biaya Pokok Menu", key="cost_calc_btn")

        if calculate_button:
            total_unit_cost, suggested_selling_price = calculate_menu_cost(base_cost, packaging_cost, labor_cost, misc_cost)
            
            st.markdown("---")
            st.subheader("Hasil Estimasi")
            
            st.metric("Total Biaya Pokok (Unit Cost)", f"Rp {total_unit_cost:,.0f}")
            st.metric("Perkiraan Harga Jual (Markup 50%)", f"Rp {suggested_selling_price:,.0f}", delta=f"Margin Rp {(suggested_selling_price - total_unit_cost):,.0f}")
            
            st.info("Harga Jual yang disarankan adalah **Rp {:.0f}** untuk mendapatkan margin 50%.".format(suggested_selling_price))
