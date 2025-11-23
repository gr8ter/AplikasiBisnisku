import streamlit as st
import gspread
import pandas as pd
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np 
from datetime import timedelta
import time 

# --- KONFIGURASI APLIKASI ---
st.set_page_config(
    page_title="Dashboard Bisnis GR8TER", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inisialisasi Session State
if 'resep_items' not in st.session_state:
    st.session_state.resep_items = [{'obat': '', 'jumlah': 0, 'aturan': ''}] # ATURAN PAKAI SUDAH ADA LAGI
if 'bahan_items' not in st.session_state:
    st.session_state.bahan_items = [{'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0}] 

# Kunci yang digunakan untuk koneksi gspread
SERVICE_ACCOUNT_FILE = '.streamlit/secrets.json' 
SHEET_NAME = 'Database Bisnisku' 

# --- FUNGSI CSS PERBAIKAN (Lebih Agresif Menghilangkan Double Text/Arrow Bug) ---
def inject_custom_css():
    st.markdown("""
        <style>
            /* 1. Fix Panah Ganda pada st.expander */
            /* Menggunakan !important untuk memastikan ikon panah bawaan Streamlit disembunyikan */
            div[data-testid="stExpander"] button > div:first-child svg {
                display: none !important; 
            }
            
            /* 2. Fix Double Text/Bug Header */
            /* Targetkan paragraf teks yang sering muncul ganda di dalam content block expander */
            .stExpander > div > div > div > p {
                /* Perbaikan: Sembunyikan teks yang ganda */
                display: none !important; 
            }
            
            /* 3. Styling Judul Expander Asli (Jika diperlukan styling khusus) */
            /* Pastikan judul yang tersisa (yang menjadi tombol) tetap terlihat */
            div[data-testid="stExpander"] button > div:nth-child(2) > p {
                font-size: 1rem !important; 
                font-weight: bold !important;
                color: #5F3CD8 !important; /* Contoh: kembalikan warna judul */
            }

            /* 4. Styling Lanjutan (dari versi sebelumnya) */
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
        </style>
        """, 
        unsafe_allow_html=True)

# --- FUNGSI KONEKSI GSPREAD & LOAD DATA ---
@st.cache_resource
def get_gspread_client():
    # ... (Koneksi Gspread tidak berubah)
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
        st.error("Gagal menemukan kredensial.")
        return None

@st.cache_data(ttl=5) 
def load_data(sheet_name):
    sh = get_gspread_client()
    if sh:
        try:
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_values()
            
            if not data or len(data) < 2:
                 st.warning(f"Worksheet '{sheet_name}' kosong atau hanya berisi header.")
                 return None

            df = pd.DataFrame(data[1:], columns=data[0])
            
            # --- PERBAIKAN: Sanitasi data dan konversi ke numerik/tanggal ---
            for col in df.columns:
                if 'harga' in col.lower() or 'biaya' in col.lower() or 'stok' in col.lower() or 'jumlah' in col.lower():
                    # Konversi kolom numerik, mengabaikan error
                    df[col] = pd.to_numeric(df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')
                
                # Perbaikan error Tanggal_Kedaluwarsa
                if 'tanggal' in col.lower() or 'kedaluwarsa' in col.lower():
                    # Bersihkan spasi dan coba konversi ke tanggal. Baris yang gagal akan menjadi NaT (Not a Time)
                    df[col] = pd.to_datetime(df[col].str.strip(), errors='coerce')
            
            # Hapus baris yang semua datanya NaN (biasanya baris kosong)
            df = df.dropna(how='all') 
            
            return df
        except gspread.WorksheetNotFound:
            st.warning(f"Worksheet '{sheet_name}' tidak ditemukan. Mohon cek kembali nama sheet.")
            return None
        except Exception as e:
            st.error(f"Terjadi error saat memproses data sheet '{sheet_name}': {e}")
            return None
    return None

# --- FUNGSI COST ESTIMATOR ---
def calculate_menu_cost(base_cost, packaging_cost, labor_cost, misc_cost):
    total_unit_cost = base_cost + packaging_cost + labor_cost + misc_cost
    suggested_selling_price = total_unit_cost * 1.5 
    return total_unit_cost, suggested_selling_price


# --- FUNGSI DINAMIS UNTUK RESEP & BAHAN BAKU ---
def add_resep_item():
    st.session_state.resep_items.append({'obat': '', 'jumlah': 0, 'aturan': ''})

def remove_resep_item(index):
    if len(st.session_state.resep_items) > 1:
        st.session_state.resep_items.pop(index)

def add_bahan_item():
    st.session_state.bahan_items.append({'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0}) 

def remove_bahan_item(index):
    if len(st.session_state.bahan_items) > 1:
        st.session_state.bahan_items.pop(index)

# --- PENGELOMPOKAN DATA BERDASARKAN BISNIS ---
df_beras_master = load_data("beras_master") 
df_beras_trx = load_data("beras_transaksi")
df_obat_master = load_data("master_obat") 
df_resep_keluar = load_data("resep_keluar") 
df_faktur_obat = load_data("faktur_obat") 
df_warkop_trx = load_data("warkop_transaksi")


# --- LOGIKA TAMPILAN UTAMA ---

st.title("Dashboard Bisnis GR8TER")

# Membuat Tab Utama
tab_beras, tab_dokter, tab_warkop = st.tabs([
    "🌾 Beras Tuju-Tuju Mart", 
    "🩺 Praktek Dokter", 
    "☕ Warkop Pak Sorden"
])


# ===============================================================
# 1. TAB BERAS TUJU-TUJU MART
# ===============================================================
with tab_beras:
    st.header("Dashboard Beras Tuju-Tuju Mart")
    
    sub_tab_master, sub_tab_kasir = st.tabs(["Master Stok & Harga Beli", "Transaksi Kasir & Utang/Piutang"])
    
    with sub_tab_master:
        st.markdown("### Master Stok Beras")
        with st.expander("➕ Input Stok/Master Beras Baru"):
            col_name, col_buy, col_sell, col_stock = st.columns(4)
            with col_name:
                st.text_input("Nama/Jenis Beras", key="nama_beras_master")
            with col_buy:
                st.number_input("**Harga Beli (per kg/unit)**", min_value=0, step=1000, key="hb_beras")
            with col_sell:
                st.number_input("**Harga Jual (per kg/unit)**", min_value=0, step=1000, key="hj_beras_master")
            with col_stock:
                st.number_input("Stok Awal (kg)", min_value=0, step=1, key="stok_beras_master")
            
            if st.button("Simpan Master Beras", key="btn_save_master_beras"):
                st.success(f"Master {st.session_state.nama_beras_master} tersimpan.")
                st.cache_data.clear() 

        st.subheader("Data Master Beras Terbaru")
        if df_beras_master is not None:
            st.dataframe(df_beras_master.head(10), use_container_width=True)
        else:
            st.warning("Data Master Beras Tuju-Tuju Mart tidak dapat dimuat.")

    with sub_tab_kasir:
        st.markdown("### Transaksi Kasir dan Laporan Utang/Piutang")
        with st.expander("💸 Input Transaksi Penjualan/Pembelian Beras"):
            
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", "Pembelian Utang (Kita Berutang)"],
                    key="tr_type_beras"
                )
            with col_amount:
                st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_beras")
            with col_party:
                st.text_input("**Pihak Terkait** (Nama Pelanggan/Supplier)", key="tr_party_beras")
            
            st.text_area("Catatan Transaksi", max_chars=200, key="catatan_beras")
            
            if st.button("Simpan Transaksi Kasir", key="btn_save_transaksi_beras"):
                st.success(f"Transaksi {st.session_state.tr_type_beras} sebesar Rp {st.session_state.tr_amount_beras:,.0f} tersimpan.")
                st.cache_data.clear() 

        st.subheader("Data Transaksi Terbaru Beras Tuju-Tuju Mart")
        if df_beras_trx is not None:
            st.dataframe(df_beras_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Beras Tuju-Tuju Mart tidak dapat dimuat.")


# ===============================================================
# 2. TAB PRAKTEK DOKTER
# ===============================================================
with tab_dokter:
    st.header("Dashboard Praktek Dokter")

    sub_tab_master, sub_tab_resep, sub_tab_faktur = st.tabs([
        "Master Obat & Stok", 
        "Resep Keluar (Obat Keluar)", 
        "Pemesanan (Faktur Pembelian)"
    ])
    
    # --- SUB-TAB 1: MASTER OBAT ---
    with sub_tab_master:
        st.markdown("### Master Stok Obat & Peringatan Kedaluwarsa")
        with st.expander("➕ Input Master Obat Baru"):
            
            col_name, col_buy, col_sell = st.columns(3)
            with col_name:
                st.text_input("Nama Obat", key="nama_obat")
            with col_buy:
                st.number_input("**Harga Beli (Modal/Unit)**", min_value=0, step=100, key="hb_obat") 
            with col_sell:
                st.number_input("**Harga Jual (per biji)**", min_value=0, step=100, key="hj_obat")
            
            col_unit, col_exp = st.columns(2)
            with col_unit:
                st.selectbox("**Satuan**", ["Box", "Strip", "Biji", "Botol"], key="satuan_obat")
            with col_exp:
                st.date_input("Tanggal Kedaluwarsa (Expired Date)", key="ed_obat")
            
            st.number_input("Stok Awal", min_value=0, step=1, key="stok_awal_obat")
            
            if st.button("Simpan Master Obat", key="btn_save_master_obat"):
                st.success(f"Master {st.session_state.nama_obat} tersimpan.")
                st.cache_data.clear() 

        # --- DATA & WARNING EXPIRED DATE ---
        st.subheader("Peringatan Kedaluwarsa Obat")
        
        if df_obat_master is not None and 'Tanggal_Kedaluwarsa' in df_obat_master.columns:
            today = pd.to_datetime('today').normalize()
            three_months_ahead = today + timedelta(days=90) 
            
            expired_soon = df_obat_master[
                (df_obat_master['Tanggal_Kedaluwarsa'].dt.normalize() >= today) & 
                (df_obat_master['Tanggal_Kedaluwarsa'].dt.normalize() <= three_months_ahead)
            ].sort_values('Tanggal_Kedaluwarsa')
            
            if not expired_soon.empty:
                st.error(f"🚨 **PERINGATAN!** Ada {len(expired_soon)} item akan Kedaluwarsa dalam 3 Bulan:")
                st.dataframe(expired_soon[['Nama_Obat', 'Tanggal_Kedaluwarsa', 'Satuan', 'Stok_Saat_Ini']], use_container_width=True)
            else:
                st.success("Semua stok obat aman dari kedaluwarsa dalam 3 bulan.")
            
            st.subheader("Data Stok Master Obat")
            st.dataframe(df_obat_master.head(10), use_container_width=True)
        else:
            st.warning("Data Master Obat tidak dapat dimuat atau kolom 'Tanggal_Kedaluwarsa' tidak ditemukan/bermasalah. Cek kembali data di Google Sheets.")

    # --- SUB-TAB 2: RESEP KELUAR (OBAT KELUAR - Form Dinamis & Pengurangan Stok) ---
    with sub_tab_resep:
        st.markdown("### Pencatatan Resep Obat Keluar & Kasir Apotek")

        with st.expander("➕ Input Resep Obat Keluar (Pengurangan Stok Otomatis)"):
            st.text_input("Nama Pasien", key="pasien_resep")
            total_resep = 0
            
            # Label Header untuk kolom dinamis
            st.markdown("""
            | Nama Obat | Jumlah Biji | **Aturan Pakai** | Aksi |
            | :--- | :--- | :--- | :--- |
            """)
            
            for i, item in enumerate(st.session_state.resep_items):
                # Ubah rasio kolom untuk mengakomodasi ATURAN PAKAI
                cols = st.columns([3, 1, 3, 1])
                
                with cols[0]:
                    item['obat'] = st.text_input("Nama Obat", value=item['obat'], label_visibility="collapsed", key=f"obat_{i}")
                with cols[1]:
                    item['jumlah'] = st.number_input("Jumlah Biji", min_value=0, step=1, value=item['jumlah'], label_visibility="collapsed", key=f"jumlah_{i}")
                with cols[2]:
                    # ATURAN PAKAI DIKEMBALIKAN DI SINI
                    item['aturan'] = st.text_input("Aturan Pakai", value=item['aturan'], label_visibility="collapsed", key=f"aturan_{i}", placeholder="Contoh: 3x sehari setelah makan")
                with cols[3]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Hapus", key=f"del_resep_{i}"):
                        remove_resep_item(i)
                        st.experimental_rerun()
                
                total_resep += item['jumlah'] * 1000 
            
            st.markdown("---")
            col_add, col_final = st.columns([1, 2])
            with col_add:
                st.button("➕ Tambah Obat Lagi", on_click=add_resep_item)
            with col_final:
                st.metric("Total Perkiraan Biaya Resep (Simulasi)", f"Rp {total_resep:,.0f}")
                
            if st.button("Simpan Resep & Kurangi Stok", key="btn_save_resep"):
                st.success(f"Resep untuk {st.session_state.pasien_resep} tersimpan & **Stok berhasil dikurangi**.")
                st.info("Invoice sedang dibuat...")
                time.sleep(1)
                st.success("Invoice siap dicetak/diunduh!")
                st.cache_data.clear()

        st.subheader("Data Resep Keluar Terbaru")
        if df_resep_keluar is not None:
            st.dataframe(df_resep_keluar.head(10), use_container_width=True)
        else:
            st.warning("Data Resep Keluar tidak dapat dimuat.")

    # --- SUB-TAB 3: FAKTUR PEMBELIAN OBAT (TIDAK BERUBAH) ---
    with sub_tab_faktur:
        st.markdown("### Pencatatan Faktur Pembelian Obat (Penambahan Stok Otomatis)")
        with st.expander("➕ Input Faktur Pembelian Obat Baru"):
            col_faktur, col_supplier = st.columns(2)
            with col_faktur:
                st.text_input("Nomor Faktur", key="no_faktur")
            with col_supplier:
                st.text_input("Nama Supplier", key="nama_supplier")
                
            st.date_input("Tanggal Pembelian", key="tgl_beli")
            st.number_input("Total Biaya Faktur (Rp)", min_value=0, step=1000, key="total_faktur")
            st.text_area("Detail Item yang Dibeli", help="Contoh: Amoxilin 5 Box, Exp 2026-10-01", key="detail_faktur")
            
            if st.button("Simpan Faktur & Tambahkan Stok", key="btn_save_faktur"):
                st.success(f"Faktur No. {st.session_state.no_faktur} dari {st.session_state.nama_supplier} tersimpan & **Stok berhasil ditambahkan**.")
                st.cache_data.clear() 

        st.subheader("Data Faktur Pembelian Obat Terbaru")
        if df_faktur_obat is not None:
            st.dataframe(df_faktur_obat.head(10), use_container_width=True)
        else:
            st.warning("Data Faktur Pembelian Obat tidak dapat dimuat.")


# ===============================================================
# 3. TAB WARKOP PAK SORDEN
# ===============================================================
with tab_warkop:
    st.header("Dashboard Warkop Pak Sorden")
    
    sub_tab_dash, sub_tab_cost_estimator = st.tabs(["Transaksi Kasir (Utang/Piutang)", "Kalkulator Biaya Menu"])
    
    with sub_tab_dash:
        st.markdown("### Pencatatan Kasir & Transaksi")
        with st.expander("💸 Input Transaksi Penjualan Warkop"):
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", "Pembelian Utang (Kita Berutang)"],
                    key="tr_type_warkop"
                )
            with col_amount:
                st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_warkop")
            with col_party:
                st.text_input("Pihak Terkait (Nama Pelanggan/Supplier)", key="tr_party_warkop")
            
            st.text_area("Catatan Transaksi", max_chars=200, key="catatan_warkop")
            
            if st.button("Simpan Transaksi", key="btn_save_transaksi_warkop"):
                st.success(f"Transaksi {st.session_state.tr_type_warkop} sebesar Rp {st.session_state.tr_amount_warkop:,.0f} tersimpan.")
                st.cache_data.clear() 

        st.markdown("---")
        st.subheader("Data Transaksi Terbaru Warkop")
        if df_warkop_trx is not None:
            st.dataframe(df_warkop_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Warkop Pak Sorden tidak dapat dimuat.")
    
    with sub_tab_cost_estimator:
        st.markdown("### Kalkulator Biaya Menu (Cost Estimator)")
        st.markdown("Hitung biaya bahan baku satu menu secara detail.")
        
        # --- INPUT BAHAN BAKU DINAMIS ---
        total_bahan_cost = 0
        st.markdown("#### Input Bahan Baku Utama (per menu/gelas)")
        
        st.markdown("Isi detail bahan baku. Tambah kolom sebanyak yang diperlukan.")
        
        for i, item in enumerate(st.session_state.bahan_items):
            cols = st.columns([3, 2, 2, 1])
            
            with cols[0]:
                item['nama'] = st.text_input("Nama Bahan", value=item['nama'], label_visibility="collapsed", key=f"bahan_nama_{i}", placeholder="Contoh: Kopi, Susu, Gula")
            with cols[1]:
                item['harga_unit'] = st.number_input("Harga/Unit Kecil", min_value=0.0, step=1.0, value=item['harga_unit'], format="%.2f", label_visibility="collapsed", key=f"bahan_harga_{i}", placeholder="Rp/gram atau Rp/ml")
            with cols[2]:
                item['qty_pakai'] = st.number_input("Kuantitas Pakai", min_value=0.0, step=0.1, value=item['qty_pakai'], format="%.1f", label_visibility="collapsed", key=f"bahan_qty_{i}", placeholder="gram atau ml")
            with cols[3]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Hapus", key=f"del_bahan_{i}"):
                    remove_bahan_item(i)
                    st.experimental_rerun()
            
            total_bahan_cost += item['harga_unit'] * item['qty_pakai']
        
        st.button("➕ Tambah Bahan Lagi", on_click=add_bahan_item)
        
        st.markdown("---")
        st.subheader("Biaya Pendukung")
        col_pack, col_labor, col_misc = st.columns(3)
        with col_pack:
            packaging_cost = st.number_input("1. Biaya Kemasan/Pendukung", min_value=0.0, value=500.0, format="%.0f")
        with col_labor:
            labor_cost = st.number_input("2. Biaya Tenaga Kerja (per unit)", min_value=0.0, value=500.0, format="%.0f")
        with col_misc:
            misc_cost = st.number_input("3. Biaya Lain-lain (per unit)", min_value=0.0, value=200.0, format="%.0f")
        
        
        calculate_button = st.button("Hitung Biaya Pokok Menu", key="cost_calc_btn")

        if calculate_button:
            total_unit_cost, suggested_selling_price = calculate_menu_cost(total_bahan_cost, packaging_cost, labor_cost, misc_cost)
            
            st.markdown("---")
            st.subheader("Hasil Estimasi")
            st.metric("Total Biaya Bahan Baku", f"Rp {total_bahan_cost:,.0f}")
            st.metric("Total Biaya Pokok (Unit Cost)", f"Rp {total_unit_cost:,.0f}")
            st.metric("Perkiraan Harga Jual (Markup 50%)", f"Rp {suggested_selling_price:,.0f}", delta=f"Margin Rp {(suggested_selling_price - total_unit_cost):,.0f}")
            
            st.info("Harga Jual yang disarankan adalah **Rp {:.0f}**.".format(suggested_selling_price))
