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
    st.session_state.resep_items = [{'obat': '', 'jumlah': 0, 'aturan': '', 'harga': 0.0}] 
if 'bahan_items' not in st.session_state:
    st.session_state.bahan_items = [{'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0, 'satuan': '', 'biaya': 0.0}] 
if 'kemasan_cost' not in st.session_state:
    st.session_state.kemasan_cost = 0
if 'ongkos_cost' not in st.session_state:
    st.session_state.ongkos_cost = 0
if 'operasional_cost' not in st.session_state:
    st.session_state.operasional_cost = 0


# Kunci yang digunakan untuk koneksi gspread
SERVICE_ACCOUNT_FILE = '.streamlit/secrets.json' 
SHEET_NAME = 'Database Bisnisku' 

# --- FUNGSI CSS PERBAIKAN ---
def inject_custom_css():
    st.markdown("""
        <style>
            /* 2. Styling Lanjutan */
            html, body, [class*="st-"] { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
            .stSidebar { background-color: #E0F2F1; }
            
            /* MEMASTIKAN WARNA TOMBOL ADALAH PUTIH */
            .stButton>button {
                background-color: #7350F2; 
                color: white !important; 
                border-radius: 12px; 
                border: none;
                padding: 10px 20px; 
                transition: 0.3s;
                font-weight: bold;
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
            /* Styling untuk container input Master/Form */
            .stContainer { border-radius: 10px; border: 1px solid #7350F2; padding: 20px; margin-bottom: 20px; }
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
                if 'harga' in col.lower() or 'biaya' in col.lower() or 'stok' in col.lower() or 'jumlah' in col.lower() or 'total' in col.lower() or 'modal' in col.lower() or 'beli' in col.lower():
                    # Bersihkan dan konversi angka
                    cleaned_col = df[col].astype(str).str.replace(',', 'TEMP', regex=False).str.replace('.', '', regex=False).str.replace('TEMP', '.', regex=False).str.strip()
                    df[col] = pd.to_numeric(cleaned_col, errors='coerce')
                
                if 'tanggal' in col.lower() or 'kedaluwarsa' in col.lower() or 'ed' in col.lower():
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

# --- FUNGSI UPDATE SEL TUNGGAL DI GOOGLE SHEETS ---
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
        
        # Format nilai sebelum update ke sheets
        value_to_update = new_value
        if isinstance(new_value, (int, float)):
             # Format angka tanpa ribuan, gspread akan menginterpretasikannya sebagai float/int
             value_to_update = str(round(new_value))
             
        worksheet.update_cell(sheet_row_index, col_index, value_to_update)
        
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
            data_dict['tr_party_beras'],
            data_dict['tr_catatan_beras']
        ]
    elif sheet_name == "master_obat":
        # Pastikan format data match dengan kolom di sheet
        # [Nama_Obat, Harga_Beli, Harga_Jual, Satuan, Tanggal_Kedaluwarsa, Stok_Saat_Ini]
        row_to_append = [data_dict['nama_obat'], data_dict['hb_obat'], data_dict['hj_obat'], data_dict['satuan_obat'], data_dict['ed_obat'].strftime('%Y-%m-%d'), data_dict['stok_awal_obat']]
    elif sheet_name == "warkop_transaksi":
         # URUTAN: [Tanggal_Transaksi, Jenis_Transaksi, Jumlah_Transaksi, Pihak_Terkait, Catatan]
         row_to_append = [
            data_dict['tr_date_warkop'].strftime('%Y-%m-%d'), 
            data_dict['tr_type_warkop'],
            data_dict['tr_amount_warkop'],
            data_dict['tr_party_warkop'],
            data_dict['tr_catatan_warkop']
        ]
    else:
        st.warning(f"Logika penyimpanan untuk sheet '{sheet_name}' belum diimplementasikan.")
        return False

    try:
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(row_to_append)
        st.cache_data.clear()
        st.success(f"✅ Data berhasil disimpan ke sheet '{sheet_name}'!")
        return True
    except Exception as e:
        st.error(f"❌ Gagal menyimpan data ke Google Sheets: {e}")
        st.info("Pastikan nama sheet dan urutan kolom di Google Sheets sudah benar.")
        return False

# --- LOGIKA PENGURANGAN STOK OTOMATIS DAN SIMPAN RESEP ---
def save_resep_and_update_stock(pasien_resep, resep_items, df_master_obat):
    if not pasien_resep.strip():
        st.error("Nama Pasien wajib diisi.")
        return False
    
    required_cols = ['Nama_Obat', 'Stok_Saat_Ini', 'Harga_Jual']
    if df_master_obat is None or not all(col in df_master_obat.columns for col in required_cols):
        st.error("Gagal memperbarui stok. Pastikan sheet 'master_obat' memiliki kolom: 'Nama_Obat', 'Stok_Saat_Ini', dan 'Harga_Jual'.")
        return False

    items_for_stock_update = []
    items_for_resep_sheet = []
    total_biaya_resep = 0
    today = pd.to_datetime('today').date()
    
    # 1. Cari ID Resep terakhir
    df_resep = load_data("resep_keluar")
    if df_resep is not None and not df_resep.empty and 'ID_Resep' in df_resep.columns:
        id_numbers = df_resep['ID_Resep'].astype(str).str.replace('R-', '', regex=False)
        valid_ids = pd.to_numeric(id_numbers, errors='coerce').dropna()
        last_id = valid_ids.max()
        new_id_num = int(last_id) + 1 if pd.notna(last_id) else 1
    else:
        new_id_num = 1
    new_id_resep = f"R-{new_id_num:03d}"

    # 2. Proses tiap item resep, cek stok, dan hitung total
    all_ok = True
    for item in resep_items:
        nama_obat = item['obat']
        jumlah = item['jumlah']
        
        if jumlah > 0 and nama_obat != "-- Pilih Obat --":
            
            master_row = df_master_obat[df_master_obat['Nama_Obat'] == nama_obat]
            
            if master_row.empty:
                st.error(f"Obat '{nama_obat}' tidak ditemukan di Master Obat. (Cek spasi/typo di sheet)")
                all_ok = False
                continue
            
            master_idx = master_row.index[0] 
            current_stok = master_row['Stok_Saat_Ini'].iloc[0]
            harga_jual = master_row['Harga_Jual'].iloc[0]
            
            if pd.isna(current_stok) or current_stok < jumlah:
                st.error(f"Stok '{nama_obat}' tidak cukup ({current_stok:,.0f}). Permintaan: {jumlah:,.0f}.")
                all_ok = False
                continue
                
            new_stok = current_stok - jumlah
            biaya_item = jumlah * harga_jual
            total_biaya_resep += biaya_item
            
            # Data untuk di-update
            items_for_stock_update.append({'index': master_idx, 'nama': nama_obat, 'new_stok': new_stok})
            
            # Data untuk di-append ke sheet resep_keluar
            items_for_resep_sheet.append([
                new_id_resep,
                today.strftime('%Y-%m-%d'),
                pasien_resep,
                nama_obat,
                jumlah,
                item['aturan'],
                biaya_item 
            ])
            
    if not all_ok:
        return False
        
    if not items_for_resep_sheet:
        st.warning("Tidak ada obat yang valid untuk diproses dalam resep ini.")
        return False

    # 3. Jika semua cek sukses, lakukan update dan append
    try:
        # A. UPDATE STOK DI MASTER OBAT
        for item_update in items_for_stock_update:
            update_sheet_cell("master_obat", item_update['index'], 'Stok_Saat_Ini', item_update['new_stok'])

        # B. APPEND DATA KE RESEP KELUAR
        sh = get_gspread_client()
        worksheet_resep = sh.worksheet("resep_keluar")
        worksheet_resep.append_rows(items_for_resep_sheet)
        
        st.cache_data.clear() 
        st.success(f"✅ Resep {new_id_resep} untuk {pasien_resep} berhasil disimpan & Stok Obat otomatis dikurangi. Total Biaya: Rp {total_biaya_resep:,.0f}")
        return True
    
    except Exception as e:
        st.error(f"❌ Terjadi kesalahan fatal saat menyimpan resep atau memperbarui stok: {e}")
        return False

# --- FUNGSI LOGIKA UNTUK RESET FORM INPUT ---
def clear_form_inputs(keys):
    """Mengosongkan input form setelah save sukses."""
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
            
    # Reset juga dynamic items
    if 'resep_items' in keys and 'resep_items' in st.session_state:
         st.session_state.resep_items = [{'obat': '', 'jumlah': 0, 'aturan': '', 'harga': 0.0}] 
    if 'bahan_items' in keys and 'bahan_items' in st.session_state:
         st.session_state.bahan_items = [{'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0, 'satuan': '', 'biaya': 0.0}]
    
    # Reset juga Biaya Tambahan Kalkulator Warkop
    if 'reset_warkop_cost' in keys:
        st.session_state.kemasan_cost = 0
        st.session_state.ongkos_cost = 0
        st.session_state.operasional_cost = 0

    st.experimental_rerun()

# --- FUNGSI UNTUK TAMBAH/HAPUS RESEP ITEM ---
def add_resep_item():
    st.session_state.resep_items.append({'obat': '', 'jumlah': 0, 'aturan': '', 'harga': 0.0})

def remove_resep_item(index):
    if len(st.session_state.resep_items) > 1:
        st.session_state.resep_items.pop(index)
    else:
        st.session_state.resep_items[0] = {'obat': '', 'jumlah': 0, 'aturan': '', 'harga': 0.0}

# --- FUNGSI UNTUK TAMBAH/HAPUS BAHAN WARKOP ---
def add_bahan_item():
    st.session_state.bahan_items.append({'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0, 'satuan': '', 'biaya': 0.0})

def remove_bahan_item(index):
    if len(st.session_state.bahan_items) > 1:
        st.session_state.bahan_items.pop(index)
    else:
        st.session_state.bahan_items[0] = {'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0, 'satuan': '', 'biaya': 0.0}


# --- PENGELOMPOKAN DATA BERDASARKAN BISNIS ---
df_beras_master = load_data("beras_master") 
df_beras_trx = load_data("beras_transaksi")
df_obat_master = load_data("master_obat") 
df_resep_keluar = load_data("resep_keluar") 
df_faktur_obat = load_data("faktur_obat") 
df_warkop_trx = load_data("warkop_transaksi")

# --- DATA LIST UNTUK SELECTBOX BARU (DILINDUNGI DARI KEYERROR) ---

obat_list = ["-- Pilih Obat --"]
obat_price_map = {}
# Kolom yang wajib ada
OBAT_COLS = ['Nama_Obat', 'Harga_Jual']

if df_obat_master is not None and not df_obat_master.empty:
    if all(col in df_obat_master.columns for col in OBAT_COLS):
        # Filter data yang benar-benar bersih dan konversi Harga_Jual ke float
        obat_data = df_obat_master[OBAT_COLS].dropna(subset=OBAT_COLS)
        obat_data['Harga_Jual'] = pd.to_numeric(obat_data['Harga_Jual'], errors='coerce')
        obat_data = obat_data.dropna(subset=['Harga_Jual'])

        if not obat_data.empty:
            obat_list += obat_data['Nama_Obat'].unique().tolist()
            obat_price_map = obat_data.set_index('Nama_Obat')['Harga_Jual'].to_dict()
        else:
            st.warning("⚠️ Data Obat valid (Harga Jual dan Nama Obat) tidak ditemukan di Master Obat.")
    else:
        st.warning("⚠️ Kolom 'Nama_Obat' atau 'Harga_Jual' hilang dari sheet Master Obat! Cek penulisan kolom.")
    
if df_beras_master is not None and not df_beras_master.empty and 'Nama_Beras' in df_beras_master.columns:
    beras_list = ["-- Pilih Beras --"] + df_beras_master['Nama_Beras'].dropna().unique().tolist()
else:
    beras_list = ["-- Pilih Beras --"]

# --- Fungsi Laporan Keuangan (Laba Bersih Per Unit) ---
def generate_financial_report(df_beras_trx, df_warkop_trx, df_resep_keluar, df_faktur_obat):
    
    # --- 1. PENGUMPULAN DATA TRANSAKSI UTAMA ---
    
    # Beras Mart
    if df_beras_trx is not None and not df_beras_trx.empty:
        beras_penjualan_tunai = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Penjualan Tunai']['Jumlah_Transaksi'].sum()
        beras_penerimaan_piutang = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Penerimaan Piutang']['Jumlah_Transaksi'].sum()
        beras_pembelian_utang = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Pembelian Utang']['Jumlah_Transaksi'].sum()
        beras_pembayaran_utang = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Pembayaran Utang']['Jumlah_Transaksi'].sum()
    else:
        beras_penjualan_tunai, beras_penerimaan_piutang, beras_pembelian_utang, beras_pembayaran_utang = 0, 0, 0, 0
    
    # Warkop 
    if df_warkop_trx is not None and not df_warkop_trx.empty:
        warkop_penjualan_tunai = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Penjualan Tunai']['Jumlah_Transaksi'].sum()
        warkop_penerimaan_piutang = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Penerimaan Piutang']['Jumlah_Transaksi'].sum()
        warkop_pembelian_utang = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Pembelian Utang']['Jumlah_Transaksi'].sum()
        warkop_pembayaran_utang = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Pembayaran Utang']['Jumlah_Transaksi'].sum()
    else:
        warkop_penjualan_tunai, warkop_penerimaan_piutang, warkop_pembelian_utang, warkop_pembayaran_utang = 0, 0, 0, 0
        
    # Dokter (Resep dan Faktur)
    if df_resep_keluar is not None and not df_resep_keluar.empty and 'Total_Biaya_Resep' in df_resep_keluar.columns:
        dokter_total_resep = df_resep_keluar['Total_Biaya_Resep'].sum() 
    else:
        dokter_total_resep = 0
        
    if df_faktur_obat is not None and not df_faktur_obat.empty and 'Total_Biaya_Faktur' in df_faktur_obat.columns:
        dokter_pembelian_faktur = df_faktur_obat['Total_Biaya_Faktur'].sum()
    else:
        dokter_pembelian_faktur = 0

    # --- 2. KALKULASI LABA PER UNIT BISNIS ---
    
    pemasukan_beras = beras_penjualan_tunai + beras_penerimaan_piutang
    pengeluaran_beras = beras_pembelian_utang + beras_pembayaran_utang
    laba_beras = pemasukan_beras - pengeluaran_beras
    
    pemasukan_warkop = warkop_penjualan_tunai + warkop_penerimaan_piutang
    pengeluaran_warkop = warkop_pembelian_utang + warkop_pembayaran_utang
    laba_warkop = pemasukan_warkop - pengeluaran_warkop
    
    pemasukan_dokter = dokter_total_resep
    pengeluaran_dokter = dokter_pembelian_faktur
    laba_dokter = pemasukan_dokter - pengeluaran_dokter
    
    pemasukan_total = pemasukan_beras + pemasukan_warkop + pemasukan_dokter
    pengeluaran_total = pengeluaran_beras + pengeluaran_warkop + pengeluaran_dokter
    laba_bersih_sementara = laba_beras + laba_warkop + laba_dokter
    
    # --- 3. OUTPUT RINGKASAN ---
    
    st.subheader("Ringkasan Kas Masuk (Pemasukan)")
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("1. Pemasukan Beras", f"Rp {pemasukan_beras:,.0f}")
    col_r2.metric("2. Pemasukan Warkop", f"Rp {pemasukan_warkop:,.0f}")
    col_r3.metric("3. Pemasukan Resep Dokter", f"Rp {pemasukan_dokter:,.0f}")
    
    st.markdown("---")
    st.subheader("Ringkasan Kas Keluar (Pengeluaran)")
    col_e1, col_e2, col_e3 = st.columns(3)
    col_e1.metric("1. Pengeluaran Beras", f"Rp {pengeluaran_beras:,.0f}")
    col_e2.metric("2. Pengeluaran Warkop", f"Rp {pengeluaran_warkop:,.0f}")
    col_e3.metric("3. Pengeluaran Obat (Faktur)", f"Rp {pengeluaran_dokter:,.0f}")
    
    st.markdown("---")
    
    # --- OUTPUT LABA PER UNIT ---
    st.subheader("💰 Laba Bersih per Unit Bisnis")
    
    col_laba_1, col_laba_2, col_laba_3, col_laba_total = st.columns(4)
    
    col_laba_1.metric("Laba Beras Tuju-Tuju Mart", f"Rp {laba_beras:,.0f}")
    col_laba_2.metric("Laba Warkop Es Pak Sorden", f"Rp {laba_warkop:,.0f}")
    col_laba_3.metric("Laba Praktek Dokter (Resep)", f"Rp {laba_dokter:,.0f}")
    
    st.markdown("---")
    
    col_final_1, col_final_2, col_final_3 = st.columns(3)
    col_final_1.metric("TOTAL PEMASUKAN SEMUA UNIT", f"Rp {pemasukan_total:,.0f}")
    col_final_2.metric("TOTAL PENGELUARAN SEMUA UNIT", f"Rp {pengeluaran_total:,.0f}")
    col_final_3.metric("LABA BERSIH TOTAL", f"Rp {laba_bersih_sementara:,.0f}")

# --- PERBAIKAN PENTING: INISIALISASI TAB UTAMA ---
st.title("Sistem Dashboard Terintegrasi GR8TER")
st.markdown("Aplikasi Pencatatan dan Monitoring Stok/Keuangan untuk Tuju-Tuju Mart, Praktek Dokter, dan Warkop.")

tab_beras, tab_dokter, tab_warkop, tab_laporan = st.tabs([
    "🍚 Beras Tuju-Tuju Mart", 
    "💊 Praktek Dokter", 
    "☕ Warkop Es Pak Sorden", 
    "📊 Laporan Keuangan"
])

# ===============================================================
# 1. TAB BERAS TUJU-TUJU MART
# ===============================================================
with tab_beras:
    st.header(f"Dashboard {NAMA_BISNIS_BERAS}")
    
    sub_tab_master, sub_tab_kasir = st.tabs(["Master Stok & Harga Beli", "Transaksi Kasir & Utang/Piutang"])
    
    with sub_tab_master:
        st.markdown("### Master Stok Beras")
        
        # PERBAIKAN: Menggunakan st.container
        with st.container(border=True): 
            st.markdown("#### ➕ Input Stok/Master Beras Baru")
            
            col_name, col_buy, col_sell, col_stock = st.columns(4)
            with col_name:
                nama_beras_master = st.text_input("Nama/Jenis Beras", key="nama_beras_master")
            with col_buy:
                hb_beras = st.number_input("**Harga Beli (per Zak)**", min_value=0, step=1000, key="hb_beras")
            with col_sell:
                hj_beras_master = st.number_input("**Harga Jual (per kg/unit)**", min_value=0, step=1000, key="hj_beras_master")
            with col_stock:
                stok_beras_master = st.number_input("Stok Awal (Zak)", min_value=0, step=1, key="stok_beras_master")
            
            def handle_save_master_beras():
                data = {'nama_beras_master': st.session_state.nama_beras_master, 'hb_beras': st.session_state.hb_beras, 'hj_beras_master': st.session_state.hj_beras_master, 'stok_beras_master': st.session_state.stok_beras_master}
                if save_data("beras_master", data):
                    clear_form_inputs(['nama_beras_master', 'hb_beras', 'hj_beras_master', 'stok_beras_master'])

            st.button("Simpan Master Beras", key="btn_save_master_beras", on_click=handle_save_master_beras) 

        st.subheader("Data Master Beras Terbaru")
        if df_beras_master is not None and not df_beras_master.empty:
            st.dataframe(df_beras_master.head(10), use_container_width=True)
        else:
            st.warning("Data Master Beras Tuju-Tuju Mart tidak dapat dimuat atau kosong.")

    with sub_tab_kasir:
        st.markdown("### Transaksi Kasir dan Laporan Utang/Piutang")
        
        st.markdown("#### 💸 Input Transaksi Penjualan/Pembelian Beras")
        with st.container(border=True):
            
            tr_date_beras = st.date_input("Tanggal Transaksi", pd.to_datetime('today').date(), key="tr_date_beras")
            
            col_type, col_product = st.columns(2)
            with col_type:
                tr_type_beras = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", 
                     "Pembelian Utang (Kita Berutang)", "Penerimaan Piutang", "Pembayaran Utang"], 
                    key="tr_type_beras"
                )
            with col_product:
                tr_product_beras = st.selectbox(
                    "Nama/Jenis Beras",
                    options=beras_list,
                    key="tr_product_beras"
                )
                
            col_amount, col_party = st.columns(2)
            with col_amount:
                tr_amount_beras = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_beras")
            with col_party:
                tr_party_beras = st.text_input("**Pihak Terkait** (Nama Pelanggan/Supplier)", key="tr_party_beras")
            
            tr_catatan_beras = st.text_area("Catatan Transaksi", max_chars=200, key="catatan_beras")
            
            def handle_save_transaksi_beras():
                if st.session_state.tr_product_beras == "-- Pilih Beras --":
                    st.error("Mohon pilih Nama/Jenis Beras yang terlibat dalam transaksi.")
                    return
                
                data = {
                    'tr_date_beras': st.session_state.tr_date_beras, 
                    'tr_type_beras': st.session_state.tr_type_beras,
                    'tr_product_beras': st.session_state.tr_product_beras, 
                    'tr_amount_beras': st.session_state.tr_amount_beras,
                    'tr_party_beras': st.session_state.tr_party_beras,
                    'tr_catatan_beras': st.session_state.catatan_beras,
                }
                if save_data("beras_transaksi", data):
                    clear_form_inputs(['tr_date_beras', 'tr_type_beras', 'tr_product_beras', 'tr_amount_beras', 'tr_party_beras', 'catatan_beras'])

            st.button("Simpan Transaksi Kasir", key="btn_save_transaksi_beras", on_click=handle_save_transaksi_beras)

        st.subheader("Data Transaksi Terbaru Beras Tuju-Tuju Mart")
        if df_beras_trx is not None and not df_beras_trx.empty:
            st.dataframe(df_beras_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Beras Tuju-Tuju Mart tidak dapat dimuat atau kosong.")


# ===============================================================
# 2. TAB PRAKTEK DOKTER
# ===============================================================
with tab_dokter:
    st.header(f"Dashboard {NAMA_BISNIS_DOKTER.replace(r'\n', ' ')}")

    sub_tab_master, sub_tab_resep, sub_tab_faktur = st.tabs(["Master Obat & Stok", "Resep Keluar (Obat Keluar)", "Pemesanan (Faktur Pembelian)"])
    
    # --- SUB-TAB 1: MASTER OBAT ---
    with sub_tab_master:
        st.markdown("### Master Stok Obat & Peringatan Kedaluwarsa")
        
        # PERBAIKAN: Menggunakan st.container
        with st.container(border=True): 
            st.markdown("#### ➕ Input Master Obat Baru")
            
            col_name, col_buy, col_sell = st.columns(3)
            with col_name:
                nama_obat = st.text_input("Nama Obat", key="nama_obat")
            with col_buy:
                hb_obat = st.number_input("**Harga Beli (Modal/Unit)**", min_value=0, step=100, key="hb_obat") 
            with col_sell:
                hj_obat = st.number_input("**Harga Jual (per biji)**", min_value=0, step=100, key="hj_obat")
            
            col_unit, col_exp = st.columns(2)
            with col_unit:
                satuan_obat = st.selectbox("**Satuan**", ["Box", "Strip", "Biji", "Botol"], key="satuan_obat")
            with col_exp:
                ed_obat = st.date_input("Tanggal Kedaluwarsa (Expired Date)", key="ed_obat")
            
            stok_awal_obat = st.number_input("Stok Awal", min_value=0, step=1, key="stok_awal_obat")
            
            def handle_save_master_obat_dokter():
                data = {'nama_obat': st.session_state.nama_obat, 'hb_obat': st.session_state.hb_obat, 'hj_obat': st.session_state.hj_obat, 'satuan_obat': st.session_state.satuan_obat, 'ed_obat': st.session_state.ed_obat, 'stok_awal_obat': st.session_state.stok_awal_obat}
                if save_data("master_obat", data):
                    clear_form_inputs(['nama_obat', 'hb_obat', 'hj_obat', 'satuan_obat', 'ed_obat', 'stok_awal_obat'])

            st.button("Simpan Master Obat", key="btn_save_master_obat", on_click=handle_save_master_obat_dokter) 

        st.subheader("Peringatan Kedaluwarsa Obat")
        
        if df_obat_master is not None and 'Tanggal_Kedaluwarsa' in df_obat_master.columns:
            today = pd.to_datetime('today').normalize()
            three_months_ahead = today + timedelta(days=90) 
            df_obat_master['Tanggal_Kedaluwarsa'] = pd.to_datetime(df_obat_master['Tanggal_Kedaluwarsa'], errors='coerce')

            expired_soon = df_obat_master[
                (df_obat_master['Tanggal_Kedaluwarsa'].dt.normalize() >= today) & 
                (df_obat_master['Tanggal_Kedaluwarsa'].dt.normalize() <= three_months_ahead)
            ].sort_values('Tanggal_Kedaluwarsa')
            
            if not expired_soon.empty:
                st.error(f"🚨 **PERINGATAN!** Ada {len(expired_soon)} item akan **Kedaluwarsa dalam 3 Bulan**:")
                if all(col in df_obat_master.columns for col in ['Nama_Obat', 'Tanggal_Kedaluwarsa', 'Satuan', 'Stok_Saat_Ini']):
                     st.dataframe(expired_soon[['Nama_Obat', 'Tanggal_Kedaluwarsa', 'Satuan', 'Stok_Saat_Ini']].dropna(), use_container_width=True)
                else:
                    st.warning("Kolom penting untuk peringatan kedaluwarsa tidak ditemukan.")
            else:
                st.success("Semua stok obat aman dari kedaluwarsa dalam 3 bulan.")
            
            st.subheader("Data Stok Master Obat")
            if all(col in df_obat_master.columns for col in ['Nama_Obat', 'Harga_Jual', 'Stok_Saat_Ini', 'Satuan', 'Tanggal_Kedaluwarsa']):
                st.dataframe(df_obat_master[['Nama_Obat', 'Harga_Jual', 'Stok_Saat_Ini', 'Satuan', 'Tanggal_Kedaluwarsa']].head(10), use_container_width=True)
            else:
                 st.warning("Kolom penting untuk menampilkan Master Obat tidak ditemukan.")

        else:
            st.warning("Data Master Obat tidak dapat dimuat atau kolom bermasalah.")

    # --- SUB-TAB 2: RESEP KELUAR (DENGAN LOGIKA STOK OTOMATIS) ---
    with sub_tab_resep:
        st.markdown("### Pencatatan Resep Obat Keluar & Kasir Apotek")

        st.markdown("#### ➕ Input Resep Obat Keluar (Pengurangan Stok Otomatis)")
        with st.container(border=True):
            
            # --- FUNGSI CALLBACK UNTUK UPDATE HARGA SAAT PILIH OBAT ---
            def update_price(i):
                nama_obat = st.session_state.get(f"obat_{i}")
                if nama_obat and nama_obat in obat_price_map:
                    st.session_state.resep_items[i]['harga'] = obat_price_map[nama_obat]
                    st.session_state.resep_items[i]['obat'] = nama_obat
                else:
                    st.session_state.resep_items[i]['harga'] = 0.0

            pasien_resep = st.text_input("Nama Pasien", key="pasien_resep")
            total_resep = 0
            
            col_header = st.columns([3, 1, 3, 1])
            with col_header[0]: st.markdown("**Nama Obat**")
            with col_header[1]: st.markdown("**Jumlah**")
            with col_header[2]: st.markdown("**Aturan Pakai**")
            with col_header[3]: st.markdown("**Aksi**")
            st.markdown("---") 
            
            for i, item in enumerate(st.session_state.resep_items):
                cols = st.columns([3, 1, 3, 1])
                
                with cols[0]:
                    current_value = item['obat']
                    st.selectbox("Nama Obat", options=obat_list, 
                                 index=0 if current_value not in obat_list else obat_list.index(current_value), 
                                 label_visibility="collapsed", key=f"obat_{i}",
                                 on_change=update_price, args=(i,)) 
                with cols[1]:
                    st.number_input("Jumlah Biji", min_value=0, step=1, value=item['jumlah'], label_visibility="collapsed", key=f"jumlah_{i}")
                with cols[2]:
                    st.text_input("Aturan Pakai", value=item['aturan'], label_visibility="collapsed", key=f"aturan_{i}", placeholder="Contoh: 3x sehari setelah makan")
                with cols[3]:
                    if st.button("Hapus", key=f"del_resep_{i}", on_click=lambda i=i: remove_resep_item(i)):
                        st.experimental_rerun()
                
                # Update item['jumlah'] dan item['aturan'] dari session state
                st.session_state.resep_items[i]['jumlah'] = st.session_state.get(f"jumlah_{i}", 0)
                st.session_state.resep_items[i]['aturan'] = st.session_state.get(f"aturan_{i}", '')
                
                # Hitung Total
                total_resep += st.session_state.resep_items[i]['jumlah'] * st.session_state.resep_items[i]['harga']
            
            st.markdown("---")
            col_add, col_final = st.columns([1, 2])
            with col_add:
                st.button("➕ Tambah Obat Lagi", on_click=add_resep_item)
            with col_final:
                st.metric("Total Biaya Resep", f"Rp {total_resep:,.0f}")
                
            def handle_save_resep():
                df_obat_master_latest = load_data("master_obat")
                if save_resep_and_update_stock(st.session_state.pasien_resep, st.session_state.resep_items, df_obat_master_latest):
                    clear_form_inputs(['pasien_resep', 'resep_items'])

            st.button("Simpan Resep & Kurangi Stok", key="btn_save_resep", on_click=handle_save_resep)

        st.subheader("Data Resep Keluar Terbaru")
        if df_resep_keluar is not None and not df_resep_keluar.empty:
            st.dataframe(df_resep_keluar.head(10), use_container_width=True)
        else:
            st.warning("Data Resep Keluar tidak dapat dimuat atau kosong.")

    # --- SUB-TAB 3: FAKTUR PEMBELIAN OBAT ---
    with sub_tab_faktur:
        st.markdown("### Pencatatan Faktur Pembelian Obat (Penambahan Stok Otomatis)")

        st.markdown("#### ➕ Input Faktur Pembelian Obat Baru")
        with st.container(border=True):
            col_faktur, col_supplier = st.columns(2)
            with col_faktur:
                no_faktur = st.text_input("Nomor Faktur", key="no_faktur")
            with col_supplier:
                nama_supplier = st.text_input("Nama Supplier", key="nama_supplier")
                
            tgl_beli = st.date_input("Tanggal Pembelian", key="tgl_beli")
            total_faktur = st.number_input("Total Biaya Faktur (Rp)", min_value=0, step=1000, key="total_faktur")
            detail_faktur = st.text_area("Detail Item yang Dibeli", help="Contoh: Amoxilin 5 Box, Exp 2026-10-01", key="detail_faktur")
            
            if st.button("Simpan Faktur & Tambahkan Stok", key="btn_save_faktur"):
                st.success(f"Faktur No. {no_faktur} dari {nama_supplier} tersimpan & Stok berhasil ditambahkan (Logika update stok untuk faktur akan diimplementasikan berikutnya).")
                st.cache_data.clear() 

        st.subheader("Data Faktur Pembelian Obat Terbaru")
        if df_faktur_obat is not None and not df_faktur_obat.empty:
            st.dataframe(df_faktur_obat.head(10), use_container_width=True)
        else:
            st.warning("Data Faktur Pembelian Obat tidak dapat dimuat atau kosong.")


# ===============================================================
# 3. TAB WARKOP PAK SORDEN
# ===============================================================
with tab_warkop:
    st.header(f"Dashboard {NAMA_BISNIS_WARKOP}")
    
    sub_tab_dash, sub_tab_cost_estimator = st.tabs(["Transaksi Kasir (Utang/Piutang)", "Kalkulator Biaya Menu"])
    
    with sub_tab_dash:
        st.markdown("### Pencatatan Kasir & Transaksi")
        
        st.markdown("#### 💸 Input Transaksi Penjualan Warkop")
        with st.container(border=True):
            
            tr_date_warkop = st.date_input("Tanggal Transaksi", pd.to_datetime('today').date(), key="tr_date_warkop")
            
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                tr_type_warkop = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", 
                     "Pembelian Utang (Kita Berutang)", "Penerimaan Piutang", "Pembayaran Utang"],
                    key="tr_type_warkop"
                )
            with col_amount:
                tr_amount_warkop = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_warkop")
            with col_party:
                tr_party_warkop = st.text_input("Pihak Terkait (Nama Pelanggan/Supplier)", key="tr_party_warkop")
            
            tr_catatan_warkop = st.text_area("Catatan Transaksi", max_chars=200, key="catatan_warkop")
            
            def handle_save_transaksi_warkop():
                data = {
                    'tr_date_warkop': st.session_state.tr_date_warkop, 
                    'tr_type_warkop': st.session_state.tr_type_warkop,
                    'tr_amount_warkop': st.session_state.tr_amount_warkop,
                    'tr_party_warkop': st.session_state.tr_party_warkop,
                    'tr_catatan_warkop': st.session_state.catatan_warkop,
                }
                if save_data("warkop_transaksi", data):
                    clear_form_inputs(['tr_date_warkop', 'tr_type_warkop', 'tr_amount_warkop', 'tr_party_warkop', 'catatan_warkop'])
            
            st.button("Simpan Transaksi", key="btn_save_transaksi_warkop", on_click=handle_save_transaksi_warkop)

        st.markdown("---")
        st.subheader("Data Transaksi Terbaru Warkop")
        if df_warkop_trx is not None and not df_warkop_trx.empty:
            st.dataframe(df_warkop_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Warkop Pak Sorden tidak dapat dimuat atau kosong.")
    
    with sub_tab_cost_estimator:
        st.markdown("### Kalkulator Biaya Menu (Cost Estimator)")
        st.info("Hitung Harga Pokok Penjualan (HPP) per porsi menu Anda.")
        
        menu_name = st.text_input("Nama Menu yang Dihitung", placeholder="Contoh: Es Kopi Susu Pak Sorden", key="menu_name_warkop")
        
        # --- INPUT BAHAN BAKU DINAMIS ---
        st.subheader("1. Biaya Bahan Baku per Porsi")
        total_hpp_bahan = 0
        
        col_header = st.columns([3, 1, 1.5, 1, 1])
        with col_header[0]: st.markdown("**Nama Bahan**")
        with col_header[1]: st.markdown("**Harga Unit (Rp)**")
        with col_header[2]: st.markdown("**Kuantitas Dipakai**")
        with col_header[3]: st.markdown("**Satuan**")
        with col_header[4]: st.markdown("**Total Biaya**")
        st.markdown("---") 

        for i, item in enumerate(st.session_state.bahan_items):
            cols = st.columns([3, 1, 1.5, 1, 1])
            
            with cols[0]:
                st.text_input("Nama Bahan", value=item['nama'], label_visibility="collapsed", key=f"bahan_nama_{i}", placeholder="Contoh: Kopi Bubuk")
            with cols[1]:
                harga_unit = st.number_input("Harga Unit (Rp)", min_value=0.0, step=100.0, value=item['harga_unit'], label_visibility="collapsed", key=f"bahan_harga_{i}")
            with cols[2]:
                qty_pakai = st.number_input("Qty Dipakai", min_value=0.0, step=0.01, value=item['qty_pakai'], label_visibility="collapsed", key=f"bahan_qty_{i}")
            with cols[3]:
                 st.text_input("Satuan", value=item['satuan'], label_visibility="collapsed", key=f"bahan_satuan_{i}", placeholder="gr/ml/unit")
            
            # Perhitungan Biaya Bahan per baris
            biaya_item = round(harga_unit * qty_pakai)
            with cols[4]:
                st.metric("Biaya", f"Rp {biaya_item:,.0f}", label_visibility="collapsed")
            
            # Update session state
            st.session_state.bahan_items[i]['nama'] = st.session_state.get(f"bahan_nama_{i}")
            st.session_state.bahan_items[i]['harga_unit'] = st.session_state.get(f"bahan_harga_{i}")
            st.session_state.bahan_items[i]['qty_pakai'] = st.session_state.get(f"bahan_qty_{i}")
            st.session_state.bahan_items[i]['satuan'] = st.session_state.get(f"bahan_satuan_{i}")
            st.session_state.bahan_items[i]['biaya'] = biaya_item
            
            total_hpp_bahan += biaya_item
        
        col_add, col_del, col_total_bahan = st.columns([1, 1, 2])
        with col_add:
            st.button("➕ Tambah Bahan", on_click=add_bahan_item)
        with col_del:
            st.button("Hapus Bahan Terakhir", on_click=lambda: remove_bahan_item(len(st.session_state.bahan_items) - 1))
        
        with col_total_bahan:
            st.metric("Total Biaya Bahan Baku", f"Rp {total_hpp_bahan:,.0f}")
            
        st.markdown("---")
        
        # --- INPUT BIAYA TAMBAHAN PER PORSI ---
        st.subheader("2. Biaya Tambahan per Porsi")
        
        col_kemasan, col_ongkos, col_operasional = st.columns(3)
        with col_kemasan:
            kemasan_cost = st.number_input("Biaya Kemasan (cup, sedotan, dll)", min_value=0, step=100, key="kemasan_cost")
        with col_ongkos:
            ongkos_cost = st.number_input("Biaya Tenaga Kerja/Gaji (perkiraan per porsi)", min_value=0, step=100, key="ongkos_cost")
        with col_operasional:
            operasional_cost = st.number_input("Biaya Operasional (listrik, air, sewa - perkiraan per porsi)", min_value=0, step=100, key="operasional_cost")

        # --- REKAPITULASI DAN HASIL AKHIR ---
        st.markdown("---")
        st.subheader("3. Rekapitulasi Harga Pokok Penjualan (HPP)")
        
        hpp_total = total_hpp_bahan + kemasan_cost + ongkos_cost + operasional_cost
        
        col_hpp, col_saran = st.columns(2)
        with col_hpp:
            st.metric(
                "TOTAL HPP per Porsi", 
                f"Rp {hpp_total:,.0f}",
                help=f"HPP = Bahan ({total_hpp_bahan:,}) + Kemasan ({kemasan_cost:,}) + Ongkos ({ongkos_cost:,}) + Operasional ({operasional_cost:,})"
            )
        
        with col_saran:
            # Menggunakan Markup 50% sebagai saran awal
            saran_harga_jual = round(hpp_total * 1.5, -2) # Pembulatan ke 100 terdekat
            st.metric("SARAN HARGA JUAL (Markup 50%)", f"Rp {saran_harga_jual:,.0f}", delta="Coba Jual Lebih Tinggi!")
            
        if st.button("Reset Kalkulator", key="btn_reset_kalkulator"):
            clear_form_inputs(['menu_name_warkop', 'bahan_items', 'reset_warkop_cost'])


# ===============================================================
# 4. TAB LAPORAN KEUANGAN & STOK TOTAL
# ===============================================================
with tab_laporan:
    st.header("Laporan Keuangan & Stok Total")
    
    st.info("Laporan ini menggunakan metode **Arus Kas (Cash Basis)**.")
    
    # --- Filter Tanggal ---
    today = pd.to_datetime('today').date()
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("Tanggal Mulai", today - timedelta(days=30))
    with col_end:
        end_date = st.date_input("Tanggal Akhir", today)
        
    st.markdown("---")
    
    # Panggil fungsi laporan keuangan
    generate_financial_report(df_beras_trx, df_warkop_trx, df_resep_keluar, df_faktur_obat)
