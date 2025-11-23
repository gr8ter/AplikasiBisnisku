import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json
import io
import time
import os 
import sys 

SERVICE_ACCOUNT_FILE = '.streamlit/secrets.json' 
SHEET_NAME = 'Database Bisnisku'

@st.cache_resource
def get_gspread_client():
    """Menginisialisasi koneksi Gspread menggunakan st.secrets atau file lokal JSON."""
    credentials_data = None
    
    try:
        if 'gcp_service_account' in st.secrets:
            credentials_data = st.secrets["gcp_service_account"]
        elif os.path.exists(SERVICE_ACCOUNT_FILE):
            with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                credentials_data = json.load(f)
        
        if credentials_data:
            gc = gspread.service_account_from_dict(credentials_data)
            return gc.open(SHEET_NAME)
        else:
            st.error("Gagal menemukan kredensial. Pastikan secrets.json ada atau secrets.toml (di Cloud) sudah benar.")
            return None

    except KeyError:
        st.error("Kesalahan format kunci rahasia. Pastikan kunci 'gcp_service_account' ada.")
        return None
    except Exception as e:
        st.error(f"Gagal menghubungkan atau membuka Google Sheets. Pastikan akun layanan sudah diberi akses Edit di Sheets Anda. Detail: {e}")
        return None

@st.cache_data(ttl=5) 
def load_data(sheet_name):
    sh = get_gspread_client()
    if sh:
        try:
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except gspread.WorksheetNotFound:
            st.error(f"Sheet/Tab '{sheet_name}' tidak ditemukan di Google Sheets. Cek nama tab Sheets Anda.")
            return pd.DataFrame()
    return pd.DataFrame()

def append_row(sheet_name, row_data):
    sh = get_gspread_client()
    if sh:
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(row_data)

def update_row(sheet_name, row_index, new_values):
    sh = get_gspread_client()
    if sh:
        worksheet = sh.worksheet(sheet_name)
        sheet_row_number = row_index + 2 
        worksheet.update(f'F{sheet_row_number}:G{sheet_row_number}', [new_values])


def format_rupiah(angka):
    if not isinstance(angka, (int, float)):
        try:
            angka = float(str(angka).replace('.', '').replace(',', ''))
        except:
            return "Rp 0"
    return f"Rp {int(angka):,}".replace(",", ".")

def to_excel(df, sheet_name):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

st.set_page_config(page_title="Sistem Bisnis Cloud", layout="wide")
st.title("🚀 Dashboard Bisnis (Cloud Ready)")

menu = st.sidebar.selectbox("Pilih Unit Bisnis", 
    ["Beras Tuju Tuju Mart", "Praktek Dokter", "Warkop Pak Sorden"])


# ================= BERAS TUJU TUJU MART =================
if menu == "Beras Tuju Tuju Mart":
    st.header("🌾 Beras Tuju Tuju Mart: Kasir & Piutang")
    
    tab1, tab2, tab3 = st.tabs(["1. Master Stok", "2. Kasir (Order Baru)", "3. Pelunasan & Riwayat"])
    
    with tab1:
        st.subheader("Master Stok & Harga Jual Default")
        col1, col2, col3 = st.columns(3)
        with col1: b_nama = st.text_input("Nama Beras")
        with col2: b_harga = st.number_input("Harga Jual (Rp)", min_value=0, step=500)
        with col3: b_stok = st.number_input("Stok Fisik", min_value=0)
            
        if st.button("Simpan Master Beras"):
            append_row("beras_stok", [b_nama, b_harga, b_stok])
            st.success("Master Beras Tersimpan!")
            st.cache_data.clear() 
            st.rerun()

        st.divider()
        df_master = load_data("beras_stok")
        st.dataframe(df_master, use_container_width=True)
        if not df_master.empty:
            st.download_button("📥 Download Master Stok", to_excel(df_master, "MasterStok"), 'master_beras.xlsx')

    with tab2:
        st.subheader("Catat Pesanan Pelanggan (Otomatis Piutang)")
        df_master = load_data("beras_stok")
        
        col_ord1, col_ord2 = st.columns(2)
        with col_ord1: 
            nama_pelanggan = st.text_input("Nama Pelanggan")
            tgl_order = st.date_input("Tanggal Order", datetime.now())
        
        pilih_item = None
        harga_jual = 0
        if not df_master.empty and 'Nama Beras' in df_master.columns and 'Harga Jual (Rp)' in df_master.columns:
            item_list = df_master['Nama Beras'].tolist()
            pilih_item = st.selectbox("Pilih Item Beras", item_list)
            df_master['Harga Jual (Rp)'] = pd.to_numeric(df_master['Harga Jual (Rp)'], errors='coerce').fillna(0)
            
            if pilih_item:
                harga_jual = df_master[df_master['Nama Beras'] == pilih_item]['Harga Jual (Rp)'].iloc[0]
            st.info(f"Harga Jual Default: {format_rupiah(harga_jual)}")
        else:
            st.warning("Mohon isi Master Stok dulu di Tab 1.")

        with col_ord2:
            jumlah = st.number_input("Jumlah Beli", min_value=1)
            total_bayar = st.number_input("Total Transaksi", value=int(harga_jual * jumlah), step=1000)
            keterangan = st.text_area("Keterangan", height=100)
            
        if st.button("Simpan Pesanan & Piutang"):
            if pilih_item and nama_pelanggan:
                append_row("beras_orders", [
                    int(time.time()), 
                    tgl_order.strftime("%Y-%m-%d"), 
                    nama_pelanggan, 
                    pilih_item, 
                    jumlah, 
                    "BELUM LUNAS", 
                    "-" 
                ])
                st.success(f"Pesanan {nama_pelanggan} berhasil dicatat sebagai piutang!")
                st.cache_data.clear()
                st.rerun()

    with tab3:
        st.subheader("Cek Piutang & Catat Pelunasan")
        df_orders = load_data("beras_orders")
        
        if not df_orders.empty and 'Status' in df_orders.columns:
            df_piutang = df_orders[df_orders['Status'] == 'BELUM LUNAS']
            
            st.markdown("#### Daftar Piutang Aktif")
            st.dataframe(df_piutang, use_container_width=True)
            
            if not df_piutang.empty and 'OrderID' in df_piutang.columns:
                piutang_list = df_piutang.apply(
                    lambda row: f"{row['OrderID']} | {row['Pelanggan']} ({row['Tanggal Order']})", axis=1
                ).tolist()
                
                st.write("---")
                st.markdown("#### Input Pelunasan")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    order_pilih = st.selectbox("Pilih Pesanan yang Dilunaskan", piutang_list)
                with col_p2:
                    tgl_lunas = st.date_input("Tanggal Pelunasan", datetime.now())
                
                if st.button("Catat Pelunasan"):
                    order_id = int(order_pilih.split(' | ')[0])
                    row_to_update = df_orders[df_orders['OrderID'] == order_id].index[0]
                    
                    update_row("beras_orders", row_to_update, ["LUNAS", tgl_lunas.strftime("%Y-%m-%d")])
                    
                    st.success(f"Piutang Order ID {order_id} LUNAS!")
                    st.cache_data.clear()
                    st.rerun()

        st.markdown("#### Seluruh Riwayat Pesanan")
        st.dataframe(df_orders, use_container_width=True)


# ================= PRAKTEK DOKTER =================
elif menu == "Praktek Dokter":
    st.header("🩺 Sistem Manajemen Klinik")
    
    df_obat_stok = load_data("obat_stok")
    
    # --- Stock Warning ---
    if not df_obat_stok.empty and 'Stok' in df_obat_stok.columns and 'Batas Min' in df_obat_stok.columns:
        df_obat_stok['Stok'] = pd.to_numeric(df_obat_stok['Stok'], errors='coerce').fillna(0)
        df_obat_stok['Batas Min'] = pd.to_numeric(df_obat_stok['Batas Min'], errors='coerce').fillna(0)
        kritis = df_obat_stok[df_obat_stok['Stok'] <= df_obat_stok['Batas Min']]
        if not kritis.empty:
            st.error(f"⚠️ PERINGATAN: Ada {len(kritis)} obat stoknya menipis! **(Update Stok Manual di Google Sheets)**")
            st.dataframe(kritis)

    tab_d1, tab_d2 = st.tabs(["Tulis Resep & Cetak", "Kelola Master Obat"])

    # --- TAB 1: TULIS RESEP ---
    with tab_d1:
        st.subheader("Tulis Resep Pasien")
        
        col_pasien1, col_pasien2 = st.columns(2)
        with col_pasien1:
            nama_pasien = st.text_input("Nama Pasien")
        with col_pasien2:
            tgl_resep = st.date_input("Tanggal Periksa", datetime.now())

        st.write("---")
        c1, c2, c3 = st.columns([2, 1, 2])
        obat_list = df_obat_stok['Nama Obat'].tolist() if not df_obat_stok.empty and 'Nama Obat' in df_obat_stok.columns else []
        
        with c1:
            pilih_obat = st.selectbox("Pilih Obat", obat_list) if obat_list else None
        with c2:
            jml_obat = st.number_input("Jumlah", min_value=1, value=10)
        with c3:
            aturan = st.text_input("Aturan Pakai", placeholder="Cth: 3x1 Sesudah Makan")
        
        if st.button("✅ Proses & Catat Resep"):
            if pilih_obat and nama_pasien:
                append_row("obat_transaksi", [
                    int(time.time()),
                    tgl_resep.strftime("%Y-%m-%d"),
                    pilih_obat,
                    jml_obat,
                    aturan,
                    nama_pasien
                ])
                
                st.success("Resep berhasil dicatat di riwayat transaksi! **(Jangan lupa kurangi stok di Google Sheets)**")
                
                # Tampilan Kertas Resep
                st.write("---")
                st.write("### 👇 Tampilan Cetak (Tekan Ctrl + P)")
                
                with st.container(border=True):
                    st.markdown(f"""
                    <div style="text-align: center;">
                        <h2>KLINIK DOKTER</h2>
                        <p>Jl. Sehat Selalu No. 123</p>
                        <hr>
                    </div>
                    <p><strong>Tanggal:</strong> {tgl_resep.strftime("%d-%m-%Y")}</p>
                    <p><strong>Nama Pasien:</strong> {nama_pasien}</p>
                    <br>
                    <table style="width:100%; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #ddd;">
                            <th style="text-align:left;">Nama Obat</th>
                            <th style="text-align:center;">Jml</th>
                            <th style="text-align:right;">Aturan Pakai</th>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;">{pilih_obat}</td>
                            <td style="text-align:center;">{jml_obat}</td>
                            <td style="text-align:right;"><strong>{aturan}</strong></td>
                        </tr>
                    </table>
                    """, unsafe_allow_html=True)
            else:
                st.warning("Mohon isi Nama Pasien dan pastikan Master Obat sudah diinput.")

    # --- TAB 2: KELOLA MASTER ---
    with tab_d2:
        st.subheader("Input Master Obat Baru")
        co1, co2, co3 = st.columns(3)
        with co1: nama = st.text_input("Nama Obat Baru")
        with co2: stok = st.number_input("Stok Awal", 0)
        with co3: batas = st.number_input("Batas Peringatan", 10)
        
        if st.button("Simpan Obat ke Master Gudang"):
            append_row("obat_stok", [nama, stok, batas])
            st.success(f"{nama} masuk ke master data.")
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.subheader("Daftar Stok Obat & Riwayat Resep")
        st.write("Stok Saat Ini (Perlu Update Manual di Sheets):")
        st.dataframe(df_obat_stok, use_container_width=True)
        st.write("Riwayat Resep Keluar:")
        st.dataframe(load_data("obat_transaksi"), use_container_width=True)


# ================= WARKOP PAK SORDEN =================
elif menu == "Warkop Pak Sorden":
    st.header("☕ Warkop Pak Sorden: Analisis Margin")
    
    st.subheader("Input Transaksi & Biaya")
    col_tgl, col_tipe = st.columns(2)
    with col_tgl: tgl = st.date_input("Tgl Transaksi", datetime.now())
    with col_tipe: tipe = st.selectbox("Jenis", ["Pemasukan", "Pengeluaran"])
    
    col_nom, col_bahan = st.columns(2)
    with col_nom: nom = st.number_input("Harga Jual / Nominal", 0, step=1000)
    with col_bahan: 
        bahan = st.number_input("Harga Bahan Perkiraan (0 jika Pengeluaran)", 0, step=500)
    
    ket = st.text_input("Keterangan Barang")
    
    if st.button("Input Kasir"):
        append_row("kopi_keuangan", [tgl.strftime("%Y-%m-%d"), tipe, nom, ket, bahan])
        st.success("Input Kasir Tersimpan!")
        st.cache_data.clear()
        st.rerun()

    st.subheader("Laporan Laba/Rugi (dengan Margin)")
    df_kopi = load_data("kopi_keuangan")

    if not df_kopi.empty and 'Tipe' in df_kopi.columns and 'Nominal' in df_kopi.columns:
        
        for col in ['Nominal', 'Harga Bahan Perkiraan']:
            if col in df_kopi.columns:
                df_kopi[col] = pd.to_numeric(df_kopi[col], errors='coerce').fillna(0)
            else:
                df_kopi[col] = 0

        masuk = df_kopi[df_kopi['Tipe'] == "Pemasukan"]['Nominal'].sum()
        keluar = df_kopi[df_kopi['Tipe'] == "Pengeluaran"]['Nominal'].sum()
        total_bahan = df_kopi[df_kopi['Tipe'] == "Pemasukan"]['Harga Bahan Perkiraan'].sum()
        
        margin_kotor = masuk - total_bahan 
        bersih = margin_kotor - keluar 
        
        st.metric("Total Omset", format_rupiah(masuk))
        st.metric("Total Biaya Bahan", format_rupiah(total_bahan))
        st.metric("Keuntungan Bersih (Est.)", format_rupiah(bersih))
        
        st.dataframe(df_kopi, use_container_width=True)
        st.download_button("📥 Download Laporan Warkop", to_excel(df_kopi, "WarkopKeuangan"), 'warkop_laporan.xlsx')
