import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, timedelta
from io import BytesIO

st.set_page_config(
    page_title="Saha Üretim Takip",
    page_icon=":construction_worker:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': (
            "DEVELOPED BY:\n"
            "- Batuhan Bozkurt"
        )
    }
)
st.sidebar.markdown("__DEVELOPED BY:__")
st.sidebar.markdown("_Batuhan Bozkurt_")
st.sidebar.markdown("_For:_")
st.sidebar.markdown("_Insteel Çelik ve Prefabrik Yapılar Aş._")

# Veritabanı bağlantısı
conn = sqlite3.connect('uretim_verileri.db')
c = conn.cursor()

# Tablo oluşturma
c.execute('''
    CREATE TABLE IF NOT EXISTS uretim (
        id INTEGER PRIMARY KEY,
        tarih TEXT,
        urun_adi TEXT,
        uretilen_miktar INTEGER,
        gereken_miktar INTEGER,
        tamamlanma_yuzdesi REAL,
        islem TEXT,
        proje TEXT
    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS projeler (
        id INTEGER PRIMARY KEY,
        proje_adi TEXT UNIQUE
    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS malzemeler (
        id INTEGER PRIMARY KEY,
        proje_adi TEXT,
        malzeme_adi TEXT,
        gereken_miktar INTEGER,
        UNIQUE(proje_adi, malzeme_adi)
    )
''')
conn.commit()

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Go to", ["Main", "Manage Projects and Materials"])

if page == "Main":
    st.title("Günlük Üretim Takip")
    st.image("inst1.jpg", caption="INSTEEL ÜRETİM TAKİP PROGRAMI", use_column_width=True)

    # Ürün giriş formu
    c.execute('SELECT proje_adi FROM projeler')
    proje_listesi = [row[0] for row in c.fetchall()]

    if proje_listesi:
        selected_project = st.selectbox("Proje Seçiniz", proje_listesi)
        c.execute('SELECT malzeme_adi, gereken_miktar FROM malzemeler WHERE proje_adi = ?', (selected_project,))
        malzeme_listesi = [(row[0], row[1]) for row in c.fetchall()]
        malzeme_adi_listesi = [row[0] for row in malzeme_listesi]
    else:
        st.warning("Lütfen önce proje ve malzeme ekleyiniz.")
        conn.close()
        st.stop()

    with st.form("product_form"):
        selected_material = st.selectbox("Ürün Adı (Malzeme Listesi)", malzeme_adi_listesi)
        produced_quantity = st.number_input("Üretilen Miktar", min_value=0, value=0)
        selected_process = st.selectbox("İşlem Seçiniz", [
            "GİYOTİN", "ABKANT", "ROLLFORM", "RULO AÇICI-BOY KESİM",
            "DELİK-KULAK- HİDROLİK PRES", "KAYNAK-PROFİL KESİM",
            "PANEL-BETOPAN KESİM", "BOYA", "MONTAJ", "SEVKİYAT"
        ])
        submitted = st.form_submit_button("Girişi Kaydet")

        if submitted:
            required_quantity = next((row[1] for row in malzeme_listesi if row[0] == selected_material), 0)
            completion_percentage = (produced_quantity / required_quantity) * 100 if required_quantity > 0 else 0
            new_data = (date.today().isoformat(), selected_material, produced_quantity, required_quantity, completion_percentage, selected_process, selected_project)
            c.execute('''
                INSERT INTO uretim (tarih, urun_adi, uretilen_miktar, gereken_miktar, tamamlanma_yuzdesi, islem, proje)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', new_data)
            conn.commit()
            st.success(f"{selected_material} için veri başarıyla kaydedildi!")

    # Verileri göster
    st.subheader("Ürün Verileri")
    df = pd.read_sql('SELECT * FROM uretim', conn)
    st.dataframe(df)

    # Veri silme formu
    st.subheader("Veri Silme")
    with st.form("delete_form"):
        id_to_delete = st.number_input("Silmek istediğiniz verinin ID numarasını giriniz:", min_value=1)
        delete_submitted = st.form_submit_button("Veriyi Sil")

        if delete_submitted:
            c.execute('DELETE FROM uretim WHERE id = ?', (id_to_delete,))
            conn.commit()
            st.success(f"ID numarası {id_to_delete} olan veri başarıyla silindi!")

    # Haftalık rapor oluşturma
    st.subheader("Haftalık Rapor")
    today = date.today()
    last_week = today - timedelta(days=7)
    weekly_data = df[(df['tarih'] >= last_week.isoformat()) & (df['tarih'] <= today.isoformat())]

    # Proje ve işleme göre gruplama ve toplam üretilen miktar hesaplama
    grouped_data = weekly_data.groupby(['proje', 'islem', 'urun_adi', 'gereken_miktar']).agg({
        'uretilen_miktar': 'sum'
    }).reset_index()

    # Tamamlanma yüzdesini yeniden hesapla
    grouped_data['tamamlanma_yuzdesi'] = (grouped_data['uretilen_miktar'] / grouped_data['gereken_miktar']) * 100

    st.dataframe(grouped_data)

    # İşlem bazlı tamamlanma yüzdesi tablosu
    st.subheader("İşlem Bazlı Tamamlanma Yüzdesi")

    process_completion_data = grouped_data.groupby('islem').agg({
        'uretilen_miktar': 'sum',
        'gereken_miktar': 'sum'
    }).reset_index()

    process_completion_data['tamamlanma_yuzdesi'] = (process_completion_data['uretilen_miktar'] / process_completion_data['gereken_miktar']) * 100
    st.dataframe(process_completion_data)

    # Excel veya CSV dosyasına kaydetme seçeneği
    save_as_excel = st.button("Verileri Excel Olarak Kaydet")
    if save_as_excel:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            grouped_data.to_excel(writer, index=False, sheet_name='Haftalık Üretim Raporu')
            process_completion_data.to_excel(writer, index=False, sheet_name='İşlem Bazlı Tamamlanma Yüzdesi')
        output.seek(0)
        st.download_button(
            label="Excel dosyasını indir",
            data=output,
            file_name="haftalik_uretim_raporu.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Veritabanını sıfırlama butonu
    if st.button("Tabloları Sıfırla"):
        c.execute('DELETE FROM uretim')
        conn.commit()
        st.success("Tablolar başarıyla sıfırlandı!")

elif page == "Manage Projects and Materials":
    st.title("Proje ve Malzeme Yönetimi")

    # Proje ekleme formu
    st.subheader("Proje Ekleme")
    with st.form("add_project_form"):
        new_project = st.text_input("Yeni Proje Adı")
        project_submitted = st.form_submit_button("Proje Ekle")

        if project_submitted:
            if new_project:
                try:
                    c.execute('INSERT INTO projeler (proje_adi) VALUES (?)', (new_project,))
                    conn.commit()
                    st.success(f"{new_project} projesi başarıyla eklendi!")
                except sqlite3.IntegrityError:
                    st.error(f"{new_project} projesi zaten mevcut.")
            else:
                st.error("Proje adı boş olamaz.")

    # Proje silme formu
    st.subheader("Proje Silme")
    c.execute('SELECT proje_adi FROM projeler')
    projects = [row[0] for row in c.fetchall()]

    with st.form("delete_project_form"):
        project_to_delete = st.selectbox("Silmek istediğiniz projeyi seçin", projects)
        project_delete_submitted = st.form_submit_button("Projeyi Sil")

        if project_delete_submitted:
            c.execute('DELETE FROM projeler WHERE proje_adi = ?', (project_to_delete,))
            c.execute('DELETE FROM malzemeler WHERE proje_adi = ?', (project_to_delete,))
            conn.commit()
            st.success(f"{project_to_delete} projesi başarıyla silindi!")

    # Malzeme ekleme formu
    st.subheader("Malzeme Ekleme")
    if projects:
        with st.form("add_material_form"):
            selected_project_for_material = st.selectbox("Proje Seçiniz", projects)
            new_material = st.text_input("Yeni Malzeme Adı")
            required_quantity = st.number_input("Gereken Miktar", min_value=0, value=0)
            material_submitted = st.form_submit_button("Malzeme Ekle")

            if material_submitted:
                if new_material:
                    try:
                        c.execute('INSERT INTO malzemeler (proje_adi, malzeme_adi, gereken_miktar) VALUES (?, ?, ?)', (selected_project_for_material, new_material, required_quantity))
                        conn.commit()
                        st.success(f"{new_material} malzemesi başarıyla eklendi!")
                    except sqlite3.IntegrityError:
                        st.error(f"{selected_project_for_material} projesinde {new_material} malzemesi zaten mevcut.")
                else:
                    st.error("Malzeme adı boş olamaz.")
    else:
        st.warning("Lütfen önce proje ekleyiniz.")

    # Malzeme silme formu
    st.subheader("Malzeme Silme")
    c.execute('SELECT proje_adi, malzeme_adi FROM malzemeler')
    materials = [f"{row[0]} - {row[1]}" for row in c.fetchall()]

    with st.form("delete_material_form"):
        material_to_delete = st.selectbox("Silmek istediğiniz malzemeyi seçin", materials)
        material_delete_submitted = st.form_submit_button("Malzemeyi Sil")

        if material_delete_submitted:
            project_name, material_name = material_to_delete.split(" - ")
            c.execute('DELETE FROM malzemeler WHERE proje_adi = ? AND malzeme_adi = ?', (project_name, material_name))
            conn.commit()
            st.success(f"{material_name} malzemesi {project_name} projesinden başarıyla silindi!")

# Veritabanı bağlantısını kapatma
conn.close()
