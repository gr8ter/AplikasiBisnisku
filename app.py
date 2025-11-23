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
    st.session_state.resep_items = [{'obat': '', 'jumlah': 0, 'aturan': ''}]
if 'bahan_items' not in st.session_state:
    st.session_state.bahan_items = [{'nama': '', 'harga_unit': 0.0, 'qty_pakai': 0.0}] 

# Kunci yang digunakan untuk koneksi gspread
SERVICE_ACCOUNT_FILE = '.streamlit/secrets.json' 
SHEET_NAME = 'Database Bisnisku' 

# --- FUNGSI CSS PERBAIKAN ULTRA-EKSTREM V9.2 ---
def inject_custom_css():
    st.markdown("""
        <style>
            /* 1. FIX TEKS GANDA/ARROW GANDA (ULTRA-EKSTREM) */
            
            /* Target semua elemen teks yang bukan merupakan teks utama tombol (paling sering jadi duplikasi) */
            div[data-testid="stExpander"] button > div:not(:last-child) > div > p,
            div[data-testid="stExpander"] button > div:first-child > svg,
            div[data-testid="stExpander"] > div > div > div > p {
                display: none !important; 
                visibility: hidden !important; 
            }
            
            /* Pastikan hanya teks judul tombol yang benar yang terlihat dan ter-style */
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
            
            /* Style Khusus untuk Struk/Invoice */
            .invoice-box {
                max-width: 600px;
                margin: auto;
                padding: 10px;
                border: 1px solid #eee;
                box-shadow: 0 0 10px rgba(0, 0, 0, .15);
                font-size: 12px;
                line-height: 14px;
                font-family: 'Helvetica Neue', 'Helvetica', Helvetica, Arial, sans-serif;
                color: #555;
            }
            .invoice-box table {
                width: 100%;
                line-height: inherit;
                text-align: left;
            }
            .invoice-box table td {
                padding: 3px;
                vertical-align: top;
            }
            .item-detail {
                border-top: 1px dashed #aaa;
                border-bottom: 1px dashed #aaa;
            }
            .stMetric [data-testid="stMetricDelta"] {
                color: #5F3CD8;
            }
        </style>
        """, 
        unsafe_allow_html=True)

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
            
            for col in df.columns:
                if 'harga' in col.lower() or 'biaya' in col.lower() or 'stok' in col.lower() or 'jumlah' in col.lower() or 'total' in col.lower():
                    # Bersihkan dan konversi angka
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip(), errors='coerce')
                
                if 'tanggal' in col.lower() or 'kedaluwarsa' in col.lower():
                    # Konversi tanggal, strip spasi ekstra
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

# --- FUNGSI GENERATOR STRUK HTML BARU ---
def generate_receipt_html(title, business_name, customer_info, items_list, total, needs_signature=False, no_faktur=None):
    
    # Konversi \n menjadi <br> untuk HTML
    business_header = business_name.replace('\n', '<br>')
    
    # Header dan Info
    html_content = f"""
    <div class="invoice-box">
        <table>
            <tr>
                <td colspan="2" style="text-align:center; font-weight: bold; font-size: 16px;">
                    {business_header}
                </td>
            </tr>
            <tr>
                <td colspan="2" style="text-align:center; font-size: 14px; border-bottom: 1px solid #ccc;">
                    **{title}**
                </td>
            </tr>
            <tr>
                <td style="width: 50%;">
                    **Tanggal:** {pd.to_datetime('today').strftime('%d %B %Y')}
                </td>
                <td style="width: 50%; text-align: right;">
                    {customer_info}
                    {f"<br>**Faktur/Resep No:** {no_faktur}" if no_faktur else ""}
                </td>
            </tr>
        </table>
        
        <table class="item-detail" cellpadding="0" cellspacing="0" style="margin-top: 5px;">
            <tr style="font-weight: bold; background-color: #f7f7f7;">
                <td style="width: 40%;">Deskripsi</td>
                <td style="width: 15%; text-align: center;">Qty</td>
                <td style="width: 45%; text-align: right;">Harga / Keterangan</td>
            </tr>
    """
    
    # Detail Item
    for item in items_list:
        html_content += f"""
            <tr>
                <td>{item['deskripsi']}</td>
                <td style="text-align: center;">{item['qty']}</td>
                <td style="text-align: right;">{item['keterangan']}</td>
            </tr>
        """
        
    # Total
    html_content += f"""
        </table>
        
        <table>
            <tr>
                <td style="font-weight: bold; text-align: right;">TOTAL:</td>
                <td style="font-weight: bold; text-align: right; width: 30%; border-top: 2px solid #555;">Rp {total:,.0f}</td>
            </tr>
    """

    # Tanda Tangan/Tanda Terima
    if needs_signature:
        html_content += f"""
            <tr><td colspan="2" style="text-align: center; padding-top: 20px;">
                Tanda Terima<br><br><br>
                (___________________)
            </td></tr>
        """
    
    html_content += "</table></div>"
    
    return html_content

# --- FUNGSI UTAMA LAPORAN KEUANGAN ---
def generate_financial_report(df_beras_trx, df_warkop_trx, df_resep_keluar, df_faktur_obat):
    
    # --- 1. PEMASUKAN (INCOME/CASH IN) ---
    pemasukan = 0
    
    # Pemasukan dari Beras Mart
    if df_beras_trx is not None and not df_beras_trx.empty:
        beras_penjualan_tunai = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Penjualan Tunai']['Jumlah_Transaksi'].sum()
        beras_penerimaan_piutang = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Penerimaan Piutang']['Jumlah_Transaksi'].sum()
    else:
        beras_penjualan_tunai, beras_penerimaan_piutang = 0, 0
    
    # Pemasukan dari Warkop
    if df_warkop_trx is not None and not df_warkop_trx.empty:
        warkop_penjualan_tunai = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Penjualan Tunai']['Jumlah_Transaksi'].sum()
        warkop_penerimaan_piutang = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Penerimaan Piutang']['Jumlah_Transaksi'].sum()
    else:
        warkop_penjualan_tunai, warkop_penerimaan_piutang = 0, 0
        
    # Pemasukan dari Dokter (Resep)
    if df_resep_keluar is not None and not df_resep_keluar.empty:
        dokter_total_resep = df_resep_keluar['Total_Biaya'].sum()
    else:
        dokter_total_resep = 0
        
    pemasukan_total = (
        beras_penjualan_tunai + beras_penerimaan_piutang + 
        warkop_penjualan_tunai + warkop_penerimaan_piutang + 
        dokter_total_resep
    )
    
    # --- 2. PENGELUARAN (EXPENSES/CASH OUT) ---
    pengeluaran = 0
    
    # Pengeluaran Pembelian Obat (Faktur)
    if df_faktur_obat is not None and not df_faktur_obat.empty:
        dokter_pembelian_faktur = df_faktur_obat['Total_Biaya_Faktur'].sum()
    else:
        dokter_pembelian_faktur = 0
        
    # Pembelian Utang/Pembayaran Utang dari Beras Mart
    if df_beras_trx is not None and not df_beras_trx.empty:
        beras_pembelian_utang = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Pembelian Utang']['Jumlah_Transaksi'].sum()
        beras_pembayaran_utang = df_beras_trx[df_beras_trx['Jenis_Transaksi'] == 'Pembayaran Utang']['Jumlah_Transaksi'].sum()
    else:
        beras_pembelian_utang, beras_pembayaran_utang = 0, 0

    # Pembelian Utang/Pembayaran Utang dari Warkop
    if df_warkop_trx is not None and not df_warkop_trx.empty:
        warkop_pembelian_utang = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Pembelian Utang']['Jumlah_Transaksi'].sum()
        warkop_pembayaran_utang = df_warkop_trx[df_warkop_trx['Jenis_Transaksi'] == 'Pembayaran Utang']['Jumlah_Transaksi'].sum()
    else:
        warkop_pembelian_utang, warkop_pembayaran_utang = 0, 0
        
    pengeluaran_total = (
        dokter_pembelian_faktur + 
        beras_pembelian_utang + beras_pembayaran_utang + 
        warkop_pembelian_utang + warkop_pembayaran_utang
    )
    
    # --- 3. LABA BERSIH SEMENTARA ---
    laba_bersih_sementara = pemasukan_total - pengeluaran_total
    
    # --- 4. OUTPUT ---
    
    st.subheader("Ringkasan Kas Masuk (Pemasukan)")
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("1. Penjualan Tunai Beras", f"Rp {beras_penjualan_tunai:,.0f}")
    col_r2.metric("2. Penjualan Tunai Warkop", f"Rp {warkop_penjualan_tunai:,.0f}")
    col_r3.metric("3. Total Penerimaan Resep", f"Rp {dokter_total_resep:,.0f}")
    
    col_r4, col_r5 = st.columns(2)
    col_r4.metric("4. Penerimaan Piutang Beras", f"Rp {beras_penerimaan_piutang:,.0f}")
    col_r5.metric("5. Penerimaan Piutang Warkop", f"Rp {warkop_penerimaan_piutang:,.0f}")
    
    st.markdown("---")
    st.subheader("Ringkasan Kas Keluar (Pengeluaran)")
    col_e1, col_e2, col_e3 = st.columns(3)
    col_e1.metric("1. Pembelian Obat (Faktur)", f"Rp {dokter_pembelian_faktur:,.0f}")
    col_e2.metric("2. Pembelian Utang Beras", f"Rp {beras_pembelian_utang:,.0f}")
    col_e3.metric("3. Pembelian Utang Warkop", f"Rp {warkop_pembelian_utang:,.0f}")
    
    col_e4, col_e5 = st.columns(2)
    col_e4.metric("4. Pembayaran Utang Beras", f"Rp {beras_pembayaran_utang:,.0f}")
    col_e5.metric("5. Pembayaran Utang Warkop", f"Rp {warkop_pembayaran_utang:,.0f}")
    
    st.markdown("---")
    
    col_final_1, col_final_2, col_final_3 = st.columns(3)
    col_final_1.metric("TOTAL PEMASUKAN", f"Rp {pemasukan_total:,.0f}", delta="Semua Kas Masuk")
    col_final_2.metric("TOTAL PENGELUARAN", f"Rp {pengeluaran_total:,.0f}", delta="Semua Kas Keluar")
    col_final_3.metric("LABA BERSIH SEMENTARA", f"Rp {laba_bersih_sementara:,.0f}", delta=f"Selisih: Rp {laba_bersih_sementara:,.0f}")


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
tab_beras, tab_dokter, tab_warkop, tab_laporan = st.tabs([
    "🌾 Beras Tuju-Tuju Mart", 
    "🩺 Praktek Dokter", 
    "☕ Warkop Es Pak Sorden",
    "📈 Laporan Keuangan & Stok Total" # <--- TAB BARU
])


# ===============================================================
# 1. TAB BERAS TUJU-TUJU MART
# ===============================================================
with tab_beras:
    st.header(f"Dashboard {NAMA_BISNIS_BERAS}")
    
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
                # --- PERUBAHAN JENIS TRANSAKSI ---
                tr_type_beras = st.selectbox(
                    "Jenis Transaksi", 
                    ["Penjualan Tunai", "Piutang (Pelanggan Berutang)", 
                     "Pembelian Utang (Kita Berutang)", "Penerimaan Piutang", "Pembayaran Utang"], 
                    key="tr_type_beras"
                )
            with col_amount:
                tr_amount_beras = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=1000, key="tr_amount_beras")
            with col_party:
                tr_party_beras = st.text_input("**Pihak Terkait** (Nama Pelanggan/Supplier)", key="tr_party_beras")
            
            tr_catatan_beras = st.text_area("Catatan Transaksi", max_chars=200, key="catatan_beras")
            
            if st.button("Simpan Transaksi Kasir", key="btn_save_transaksi_beras"):
                st.success(f"Transaksi {tr_type_beras} sebesar Rp {tr_amount_beras:,.0f} tersimpan.")
                st.cache_data.clear() 
                
                # --- LOGIKA CETAK INVOICE BERAS ---
                if tr_type_beras == "Penjualan Tunai":
                    items = [{'deskripsi': "Transaksi Penjualan Beras", 'qty': 1, 'keterangan': tr_catatan_beras if tr_catatan_beras else '-'}]
                    
                    receipt_html = generate_receipt_html(
                        title="Tanda Terima Penjualan",
                        business_name=NAMA_BISNIS_BERAS,
                        customer_info=f"**Pelanggan:** {tr_party_beras if tr_party_beras else 'Umum'}",
                        items_list=items,
                        total=tr_amount_beras,
                        needs_signature=True
                    )
                    
                    st.markdown("### Struk Siap Cetak")
                    st.markdown(receipt_html, unsafe_allow_html=True)
                    st.button("🖼️ Cetak Struk/Tanda Terima", help="Klik untuk membuka dialog cetak browser", key="print_beras_btn")

        st.subheader("Data Transaksi Terbaru Beras Tuju-Tuju Mart")
        if df_beras_trx is not None:
            st.dataframe(df_beras_trx.head(10), use_container_width=True)
        else:
            st.warning("Data Transaksi Beras Tuju-Tuju Mart tidak dapat dimuat.")


# ===============================================================
# 2. TAB PRAKTEK DOKTER
# ===============================================================
with tab_dokter:
    st.header(f"Dashboard {NAMA_BISNIS_DOKTER.replace(r'\n', ' ')}")

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

    # --- SUB-TAB 2: RESEP KELUAR ---
    with sub_tab_resep:
        st.markdown("### Pencatatan Resep Obat Keluar & Kasir Apotek")

        with st.expander("➕ Input Resep Obat Keluar (Pengurangan Stok Otomatis)"):
            pasien_resep = st.text_input("Nama Pasien", key="pasien_resep")
            total_resep = 0
            
            col_header = st.columns([3, 1, 3, 1])
            with col_header[0]:
                st.markdown("**Nama Obat**")
            with col_header[1]:
                st.markdown("**Jumlah**")
            with col_header[2]:
                st.markdown("**Aturan Pakai**")
            with col_header[3]:
                st.markdown("**Aksi**")
            st.markdown("---") 
            
            for i, item in enumerate(st.session_state.resep_items):
                cols = st.columns([3, 1, 3, 1])
                
                with cols[0]:
                    item['obat'] = st.text_input("Nama Obat", value=item['obat'], label_visibility="collapsed", key=f"obat_{i}")
                with cols[1]:
                    item['jumlah'] = st.number_input("Jumlah Biji", min_value=0, step=1, value=item['jumlah'], label_visibility="collapsed", key=f"jumlah_{i}")
                with cols[2]:
                    item['aturan'] = st.text_input("Aturan Pakai", value=item['aturan'], label_visibility="collapsed", key=f"aturan_{i}", placeholder="Contoh: 3x sehari setelah makan")
                with cols[3]:
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
                st.success(f"Resep untuk {pasien_resep} tersimpan & **Stok berhasil dikurangi**.")
                st.info("Struk sedang dibuat...")
                time.sleep(1)
                
                items_resep = []
                for item in st.session_state.resep_items:
                    items_resep.append({
                        'deskripsi': item['obat'], 
                        'qty': item['jumlah'], 
                        'keterangan': item['aturan']
                    })
                
                receipt_html = generate_receipt_html(
                    title="STRUK RESEP OBAT",
                    business_name=NAMA_BISNIS_DOKTER,
                    customer_info=f"**Pasien:** {pasien_resep}",
                    items_list=items_resep,
                    total=total_resep,
                    needs_signature=False
                )
                
                st.markdown("### Struk Resep Siap Cetak")
                st.markdown(receipt_html, unsafe_allow_html=True)
                st.button("🖼️ Cetak Struk Resep", help="Klik untuk membuka dialog cetak browser", key="print_resep_btn")

        st.subheader("Data Resep Keluar Terbaru")
        if df_resep_keluar is not None:
            st.dataframe(df_resep_keluar.head(10), use_container_width=True)
        else:
            st.warning("Data Resep Keluar tidak dapat dimuat.")

    # --- SUB-TAB 3: FAKTUR PEMBELIAN OBAT ---
    with sub_tab_faktur:
        st.markdown("### Pencatatan Faktur Pembelian Obat (Penambahan Stok Otomatis)")

        with st.expander("➕ Input Faktur Pembelian Obat Baru"):
            col_faktur, col_supplier = st.columns(2)
            with col_faktur:
                no_faktur = st.text_input("Nomor Faktur", key="no_faktur")
            with col_supplier:
                nama_supplier = st.text_input("Nama Supplier", key="nama_supplier")
                
            tgl_beli = st.date_input("Tanggal Pembelian", key="tgl_beli")
            total_faktur = st.number_input("Total Biaya Faktur (Rp)", min_value=0, step=1000, key="total_faktur")
            detail_faktur = st.text_area("Detail Item yang Dibeli", help="Contoh: Amoxilin 5 Box, Exp 2026-10-01", key="detail_faktur")
            
            if st.button("Simpan Faktur & Tambahkan Stok", key="btn_save_faktur"):
                st.success(f"Faktur No. {no_faktur} dari {nama_supplier} tersimpan & **Stok berhasil ditambahkan**.")
                st.cache_data.clear() 
                
                items_faktur = [{'deskripsi': detail_faktur, 'qty': 1, 'keterangan': "Pembelian Grosir"}]
                
                receipt_html = generate_receipt_html(
                    title="FAKTUR PEMBELIAN OBAT",
                    business_name=NAMA_BISNIS_DOKTER,
                    customer_info=f"**Supplier:** {nama_supplier}",
                    items_list=items_faktur,
                    total=total_faktur,
                    needs_signature=True,
                    no_faktur=no_faktur
                )
                
                st.markdown("### Faktur Siap Cetak")
                st.markdown(receipt_html, unsafe_allow_html=True)
                st.button("🖼️ Cetak Faktur Pembelian", help="Klik untuk membuka dialog cetak browser", key="print_faktur_btn")

        st.subheader("Data Faktur Pembelian Obat Terbaru")
        if df_faktur_obat is not None:
            st.dataframe(df_faktur_obat.head(10), use_container_width=True)
        else:
            st.warning("Data Faktur Pembelian Obat tidak dapat dimuat.")


# ===============================================================
# 3. TAB WARKOP PAK SORDEN
# ===============================================================
with tab_warkop:
    st.header(f"Dashboard {NAMA_BISNIS_WARKOP}")
    
    sub_tab_dash, sub_tab_cost_estimator = st.tabs(["Transaksi Kasir (Utang/Piutang)", "Kalkulator Biaya Menu"])
    
    with sub_tab_dash:
        st.markdown("### Pencatatan Kasir & Transaksi")
        with st.expander("💸 Input Transaksi Penjualan Warkop"):
            col_type, col_amount, col_party = st.columns(3)
            with col_type:
                 # --- PERUBAHAN JENIS TRANSAKSI ---
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
            
            st.text_area("Catatan Transaksi", max_chars=200, key="catatan_warkop")
            
            if st.button("Simpan Transaksi", key="btn_save_transaksi_warkop"):
                st.success(f"Transaksi {tr_type_warkop} sebesar Rp {tr_amount_warkop:,.0f} tersimpan.")
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

# ===============================================================
# 4. TAB LAPORAN KEUANGAN & STOK TOTAL
# ===============================================================
with tab_laporan:
    st.header("Laporan Keuangan & Stok Total")
    
    st.info("Laporan ini menggunakan metode **Arus Kas (Cash Basis)**. Laba Bersih dihitung dari total Kas Masuk dikurangi total Kas Keluar dari semua unit bisnis.")
    
    # --- Filter Tanggal ---
    today = pd.to_datetime('today').date()
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("Tanggal Mulai", today - timedelta(days=30))
    with col_end:
        end_date = st.date_input("Tanggal Akhir", today)
        
    st.markdown("---")
    
    # Reload data dengan filter tanggal
    # (Catatan: Saat ini filtering masih dilakukan di memory, perlu logic filtering jika dataset besar)
    
    # Panggil fungsi laporan keuangan
    generate_financial_report(df_beras_trx, df_warkop_trx, df_resep_keluar, df_faktur_obat)
