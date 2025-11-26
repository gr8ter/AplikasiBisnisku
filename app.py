import streamlit as st
import gspread
import pandas as pd
import numpy as np
from datetime import datetime
import json

# --- KONFIGURASI DAN INJEKSI CSS ---

# Setel konfigurasi halaman
st.set_page_config(layout="wide", page_title="Sistem Resep Farmasi")

# CSS INJECTION untuk memperbaiki tampilan dropdown (Solusi UI)
st.markdown("""
<style>
/* CSS untuk mengurangi margin/padding di atas selectbox, memperbaiki masalah nama obat terpotong */
div.stSelectbox > label {
    padding-top: 0rem; 
    margin-bottom: -10px; 
}

/* CSS untuk elemen label lainnya */
.css-1r650s0 {
    margin-bottom: -10px; 
}

/* Style untuk menghilangkan border pada input numerik */
.stNumberInput > div > div > input {
    border: none !important;
}

/* Style untuk memperjelas pesan error */
.stAlert {
    border-left: 5px solid red !important;
}
</style>
""", unsafe_allow_html=True)

# --- FUNGSI UTILITY GSPREAD ---

@st.cache_resource(ttl=3600)
def get_gc():
    """Menginisiasi koneksi Google Sheets."""
    try:
        # Menggunakan koneksi Streamlit Secrets
        secrets = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(secrets)
        return gc
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets: {e}")
        st.stop()

def get_worksheet(sheet_name):
    """Membuka worksheet berdasarkan nama."""
    try:
        gc = get_gc()
        # Ganti 'NAMA_SPREADSHEET_ANDA' dengan nama spreadsheet Google Anda yang sebenarnya
        spreadsheet_name = st.secrets["spreadsheet"]["name"]
        sh = gc.open(spreadsheet_name)
        worksheet = sh.worksheet(sheet_name)
        return worksheet
    except Exception as e:
        st.error(f"Gagal membuka sheet '{sheet_name}': Pastikan nama sheet benar dan akun memiliki akses. Error: {e}")
        st.stop()

@st.cache_data(ttl="1h")
def load_data(sheet_name):
    """Memuat data dari worksheet ke DataFrame."""
    try:
        worksheet = get_worksheet(sheet_name)
        df = pd.DataFrame(worksheet.get_all_records())
        
        if sheet_name == "master_obat":
            # PASTIKAN KOLOM HARGA DAN STOK ADALAH NUMERIK
            # Solusi Peringatan Harga Jual Rp 0.0
            df['Harga_Jual'] = pd.to_numeric(df['Harga_Jual'], errors='coerce').fillna(0)
            df['Stok_Saat_Ini'] = pd.to_numeric(df['Stok_Saat_Ini'], errors='coerce').fillna(0)
            # Isi nilai kosong di Nama_Obat dengan string kosong agar tidak crash
            df['Nama_Obat'] = df['Nama_Obat'].fillna('').astype(str)
            
        return df
    except Exception as e:
        st.error(f"Gagal memuat data dari '{sheet_name}'. Error: {e}")
        return pd.DataFrame()


def update_sheet_cell(sheet_name, row_index, col_name, new_value):
    """
    Memperbarui sel tertentu di worksheet. 
    (Row_index adalah index pandas, harus dikonversi ke index GSpread + 2)
    """
    try:
        worksheet = get_worksheet(sheet_name)
        
        # Cari index baris GSpread: index pandas + 2 (header + 0-indexing)
        sheet_row_index = row_index + 2
        
        # Cari index kolom
        headers = worksheet.row_values(1)
        col_index = headers.index(col_name) + 1 # +1 karena GSpread 1-indexing
        
        value_to_update = new_value
        
        # PERBAIKAN UTAMA: Penanganan Tipe Data Deprecated NumPy dan int64/float64
        # Menggunakan float dan int bawaan Python, dan tipe spesifik numpy yang masih valid.
        if isinstance(new_value, (int, float, np.integer, np.int64, np.float64)):
            # Gunakan int() untuk menghilangkan desimal dan mengubahnya ke Python int
            value_to_update = str(int(new_value)) 
        
        # Untuk kasus lain (misalnya string), pastikan itu string
        value_to_update = str(value_to_update)
            
        worksheet.update_cell(sheet_row_index, col_index, value_to_update)
        return True

    except Exception as e:
        # Tangkap dan tampilkan error
        st.error(f"Gagal memperbarui sel di sheet {sheet_name}: {e}")
        return False

# --- FUNGSI LOGIKA APLIKASI ---

def get_harga_dan_stok(df_master, nama_obat):
    """Mendapatkan Harga Jual dan Stok dari Nama Obat."""
    try:
        # Mencocokkan nama obat (pastikan stripping whitespace)
        data = df_master[df_master['Nama_Obat'].str.strip() == nama_obat.strip()].iloc[0]
        
        harga = data['Harga_Jual']
        stok = data['Stok_Saat_Ini']
        index = data.name # Index pandas (penting untuk update)
        
        return harga, stok, index
    except IndexError:
        st.warning(f"Obat '{nama_obat}' tidak ditemukan di Master Obat. (Cek spasi/typo di sheet)")
        return 0, 0, -1 # -1 menandakan tidak ditemukan
    except Exception as e:
        st.error(f"Error saat mencari data obat: {e}")
        return 0, 0, -1


def save_resep_and_update_stock(resep_data, df_master_obat):
    """Menyimpan resep dan memperbarui stok di Master Obat."""
    
    # ... Inisialisasi ...
    # Persiapan data resep untuk disimpan (tanpa ID Resep dulu)
    resep_to_save = {
        'Nama_Pasien': resep_data['Nama_Pasien'],
        'Tanggal_Resep': resep_data['Tanggal_Resep'],
        'Total_Biaya': resep_data['Total_Biaya'],
        'Detail_Obat': json.dumps(resep_data['Detail_Obat']), # Simpan detail obat sebagai JSON string
        'Status': 'Selesai' 
    }

    items_for_stock_update = []
    all_ok = True
    
    try:
        # 1. Cek stok dan kumpulkan data update
        for item in resep_data['Detail_Obat']:
            nama_obat = item['Nama_Obat_Pilihan']
            jumlah_resep = item['Jumlah_Resep']
            
            # Perbaikan Masalah 1: Penanganan Nama Obat Kosong
            if not nama_obat or str(nama_obat).strip() == "":
                st.error("Gagal memproses resep: Ada baris obat yang kosong.")
                all_ok = False
                break
            
            harga, current_stok, index = get_harga_dan_stok(df_master_obat, nama_obat)
            
            if index == -1: # Obat tidak ditemukan (sudah di-warning di get_harga_dan_stok)
                all_ok = False
                break
                
            if current_stok < jumlah_resep:
                st.error(f"Stok {nama_obat} tidak cukup. Stok saat ini: {current_stok}, Dibutuhkan: {jumlah_resep}")
                all_ok = False
                break
                
            new_stok = current_stok - jumlah_resep
            
            items_for_stock_update.append({
                'index': index,
                'nama_obat': nama_obat,
                'new_stok': new_stok
            })
        
        # 2. Jika semua cek sukses, lakukan update dan append
        if all_ok:
            
            # A. UPDATE STOK DI MASTER OBAT
            for item_update in items_for_stock_update:
                # PERBAIKAN FINAL int64: Konversi eksplisit ke INT Python murni
                stok_python_int = int(item_update['new_stok'])
                
                if not update_sheet_cell("master_obat", item_update['index'], 'Stok_Saat_Ini', stok_python_int):
                    all_ok = False # Jika update cell gagal, batalkan proses
                    break

            # B. SIMPAN DATA RESEP BARU
            if all_ok:
                worksheet_resep = get_worksheet("daftar_resep")
                # Ambil ID Resep terakhir dan tambahkan 1
                all_resep = worksheet_resep.get_all_records()
                last_id = 0
                if all_resep:
                    try:
                        last_id = int(all_resep[-1]['ID_Resep'].replace('R', ''))
                    except:
                        last_id = len(all_resep)
                        
                new_id = f"R{last_id + 1:04d}"
                resep_to_save['ID_Resep'] = new_id
                
                # Urutan kolom harus sesuai dengan GSheet
                header = worksheet_resep.row_values(1)
                row_values = [resep_to_save.get(col, '') for col in header]
                worksheet_resep.append_row(row_values, value_input_option='USER_ENTERED')
                
                # Kosongkan cache agar data terbaru dimuat
                st.cache_data.clear() 
                st.success(f"✅ Resep {new_id} berhasil disimpan dan stok diperbarui!")
                
                # Kosongkan daftar resep di session state setelah sukses
                if 'resep_items' in st.session_state:
                    st.session_state.resep_items = []
                st.rerun()
        
    except Exception as e:
        # Tangkap error JSON serializable (jika masih terjadi, berarti np.float fix gagal)
        st.error(f"❌ Terjadi kesalahan fatal saat menyimpan resep atau memperbarui stok: {e}")
        all_ok = False
        
    return all_ok


# --- TAMPILAN UTAMA APLIKASI ---

def main_app():
    
    st.title("💊 Sistem Pencatatan Resep Obat")

    # 1. Muat Data Master Obat
    df_master_obat = load_data("master_obat")
    
    if df_master_obat.empty:
        st.error("Tidak dapat memuat Master Obat. Harap periksa koneksi.")
        return

    obat_list = sorted(df_master_obat['Nama_Obat'].unique().tolist())
    
    # Peringatan Harga Jual 0.0 (jika ada)
    if (df_master_obat['Harga_Jual'] == 0).any():
        st.warning("⚠️ Beberapa obat dimuat dengan Harga Jual Rp 0.0 (Harap periksa kolom **`Harga_Jual`** di Google Sheets **`Master Obat`**).")

    # 2. Inisialisasi State
    if 'resep_items' not in st.session_state:
        st.session_state.resep_items = []
    if 'nama_pasien' not in st.session_state:
        st.session_state.nama_pasien = ""

    # --- INPUT PASIEN ---
    col_pasien, col_tanggal = st.columns([3, 1])
    with col_pasien:
        st.session_state.nama_pasien = st.text_input("Nama Pasien", value=st.session_state.nama_pasien, key="pasien_input")
    with col_tanggal:
        tanggal_resep = st.date_input("Tanggal Resep", value=datetime.now().date())
    
    st.markdown("---")
    
    # --- INPUT OBAT (Loop/Daftar Resep) ---
    
    st.header("Detail Resep")

    # Tombol tambah baris baru
    if st.button("➕ Tambah Obat"):
        # Tambahkan item resep kosong baru
        st.session_state.resep_items.append({
            'key': len(st.session_state.resep_items), # Kunci unik
            'Nama_Obat_Pilihan': "",
            'Jumlah_Resep': 1,
            'Harga_Satuan': 0.0
        })
        st.rerun()

    total_biaya = 0
    items_to_keep = []

    # Tampilkan Header Tabel
    col_header = st.columns([4, 1, 2, 1])
    with col_header[0]:
        st.markdown("**Obat**")
    with col_header[1]:
        st.markdown("**Jumlah**")
    with col_header[2]:
        st.markdown("**Harga (Rp)**")
    with col_header[3]:
        st.markdown("**Hapus**")
        
    st.markdown("---")

    # Loop untuk menampilkan dan mengedit item resep
    for i, item in enumerate(st.session_state.resep_items):
        
        # Gunakan key unik untuk setiap widget dalam loop
        key_obat = f"obat_{item['key']}"
        key_jumlah = f"jumlah_{item['key']}"
        key_hapus = f"hapus_{item['key']}"

        col_obat, col_jumlah, col_harga, col_hapus = st.columns([4, 1, 2, 1])

        with col_obat:
            # st.selectbox dengan opsi obat dari Master Obat
            selected_obat = st.selectbox(
                "Pilih Obat", 
                options=[""] + obat_list, # Tambahkan opsi kosong
                index=([None] + obat_list).index(item['Nama_Obat_Pilihan']) if item['Nama_Obat_Pilihan'] in obat_list else 0,
                label_visibility="collapsed",
                key=key_obat
            )
            
            # Update nama obat di session state
            item['Nama_Obat_Pilihan'] = selected_obat

        with col_jumlah:
            # Input numerik untuk jumlah resep
            jumlah_resep = st.number_input(
                "Jumlah", 
                min_value=1, 
                value=item['Jumlah_Resep'], 
                step=1, 
                label_visibility="collapsed",
                key=key_jumlah
            )
            item['Jumlah_Resep'] = jumlah_resep

        # Logika perhitungan harga
        harga_satuan = 0.0
        if selected_obat:
            harga_satuan, stok_saat_ini, _ = get_harga_dan_stok(df_master_obat, selected_obat)
            item['Harga_Satuan'] = harga_satuan
            
        harga_subtotal = item['Harga_Satuan'] * item['Jumlah_Resep']
        total_biaya += harga_subtotal

        with col_harga:
            st.markdown(f"**Rp {harga_subtotal:,.2f}**") # Tampilkan subtotal

        with col_hapus:
            if st.button("❌", key=key_hapus):
                # Tombol hapus item dari daftar
                continue # Langsung lanjut ke iterasi berikutnya (tidak memasukkan item ini ke items_to_keep)

        # Jika tidak dihapus, masukkan item ini ke daftar yang akan dipertahankan
        items_to_keep.append(item)

    # Perbarui session state dengan item yang dipertahankan
    st.session_state.resep_items = items_to_keep
    
    st.markdown("---")

    # --- RINGKASAN DAN SIMPAN ---

    st.subheader(f"Total Biaya Resep: Rp {total_biaya:,.2f}")
    
    st.markdown("---")

    if st.button("💾 Simpan Resep & Update Stok", type="primary"):
        if not st.session_state.nama_pasien:
            st.error("Nama Pasien tidak boleh kosong.")
        elif not st.session_state.resep_items:
            st.error("Detail Resep tidak boleh kosong. Tambahkan minimal satu obat.")
        else:
            resep_data = {
                'Nama_Pasien': st.session_state.nama_pasien,
                'Tanggal_Resep': tanggal_resep.strftime("%Y-%m-%d"),
                'Total_Biaya': total_biaya,
                'Detail_Obat': st.session_state.resep_items
            }
            # Panggil fungsi penyimpanan dan update stok
            save_resep_and_update_stock(resep_data, df_master_obat)


if __name__ == "__main__":
    main_app()
