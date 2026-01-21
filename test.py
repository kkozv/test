import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro", layout="wide", page_icon="📦")

# Stylizacja dla nowoczesnego wyglądu
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# Inicjalizacja połączenia z Supabase (klucze pobierane ze st.secrets)
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Błąd konfiguracji Supabase. Sprawdź plik secrets.toml lub ustawienia Streamlit Cloud.")
        st.stop()

supabase: Client = init_connection()

# --- FUNKCJE CRUD (KOMUNIKACJA Z BAZĄ) ---
def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(res.data)

def get_products():
    res = supabase.table("produkty").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # Wyciąganie nazwy kategorii z relacji (join)
        df['kategoria_nazwa'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
    return df

# --- SIDEBAR - NAWIGACJA ---
with st.sidebar:
    st.title("📦 Magazyn Pro")
    st.markdown("---")
    menu = st.radio(
        "Menu główne",
        ["Dashboard", "Produkty", "Kategorie", "Operacje", "Eksport"],
        index=0
    )
    st.markdown("---")
    st.caption("Status: Połączono z bazą danych")

# --- WIDOK: DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Statystyki Magazynu")
    df_p = get_products()
    
    if not df_p.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Liczba produktów", len(df_p))
        with col2:
            st.metric("Łączny stan", int(df_p['liczba'].sum()))
        with col3:
            total_val = (df_p['liczba'] * df_p['cena']).sum()
            st.metric("Wartość magazynu", f"{total_val:,.2f} PLN")
        
        st.markdown("---")
        st.subheader("Ilość towaru w podziale na kategorie")
        chart_data = df_p.groupby('kategoria_nazwa')['liczba'].sum()
        st.bar_chart(chart_data)
    else:
        st.info("Baza danych jest pusta. Dodaj produkty, aby zobaczyć statystyki.")

# --- WIDOK: PRODUKTY ---
elif menu == "Produkty":
    st.header("🛒 Zarządzanie Towarami")
    df_p = get_products()
    df_k = get_categories()

    tab1, tab2 = st.tabs(["📋 Lista i Szukanie", "➕ Dodaj / Edytuj"])

    with tab1:
        search = st.text_input("🔍 Wyszukaj produkt po nazwie...")
        if not df_p.empty:
            filtered_df = df_p[df_p['nazwa'].str.contains(search, case=False)]
            st.dataframe(
                filtered_df[['id', 'nazwa', 'liczba', 'cena', 'kategoria_nazwa']], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Brak produktów w bazie.")

    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Dodaj Nowy")
            with st.form("add_product_form", clear_on_submit=True):
                n_name = st.text_input("Nazwa produktu")
                n_qty = st.number_input("Ilość początkowa", min_value=0, step=1)
                n_price = st.number_input("Cena jednostkowa (PLN)", min_value=0.0, step=0.01)
                
                cat_options = {row['nazwa']: row['id'] for _, row in df_k.iterrows()}
                n_cat_name = st.selectbox("Kategoria", options=list(cat_options.keys()) if cat_options else ["Brak"])
                
                if st.form_submit_button("Zatwierdź i Dodaj"):
                    if n_name and cat_options:
                        supabase.table("produkty").insert({
                            "nazwa": n_name, 
                            "liczba": int(n_qty), 
                            "cena": float(n_price), 
                            "kategoria_id": int(cat_options[n_cat_name])
                        }).execute()
                        st.success(f"Dodano: {n_name}")
                        st.rerun()
                    else:
                        st.error("Wypełnij nazwę i upewnij się, że istnieją kategorie.")

        with col_b:
            st.subheader("Edytuj / Usuń")
            if not df_p.empty:
                to_edit_name = st.selectbox("Wybierz produkt do zmiany", options=df_p['nazwa'].tolist())
                prod_data = df_p[df_p['nazwa'] == to_edit_name].iloc[0]
                
                with st.form("edit_product_form"):
                    e_name = st.text_input("Nowa nazwa", value=prod_data['nazwa'])
                    e_price = st.number_input("Nowa cena", value=float(prod_data['cena']))
                    
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("💾 Zapisz"):
                        supabase.table("produkty").update({
                            "nazwa": e_name, "cena": float(e_price)
                        }).eq("id", int(prod_data['id'])).execute()
                        st.success("Zapisano zmiany!")
                        st.rerun()
                    
                    if c2.form_submit_button("🗑️ USUŃ"):
                        supabase.table("produkty").delete().eq("id", int(prod_data['id'])).execute()
                        st.error("Produkt usunięty.")
                        st.rerun()

# --- WIDOK: KATEGORIE ---
elif menu == "Kategorie":
    st.header("📂 Kategorie Produktów")
    df_k = get_categories()

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Nowa Kategoria")
        with st.form("add_cat"):
            cat_n = st.text_input("Nazwa")
            cat_d = st.text_area("Opis")
            if st.form_submit_button("Dodaj"):
                if cat_n:
                    supabase.table("kategorie").insert({"nazwa": cat_n, "opis": cat_d}).execute()
                    st.success("Dodano kategorię")
                    st.rerun()

    with col2:
        st.subheader("Istniejące")
        if not df_k.empty:
            st.table(df_k[['nazwa', 'opis']])
        else:
            st.info("Brak kategorii.")

# --- WIDOK: OPERACJE (PRZYJĘCIE/WYDANIE) ---
elif menu == "Operacje":
    st.header("🔄 Przyjęcia i Wydania Magazynowe")
    df_p = get_products()
    
    if not df_p.empty:
        # Wybór produktu
        prod_sel = st.selectbox("Produkt", options=df_p['nazwa'].tolist())
        selected_prod = df_p[df_p['nazwa'] == prod_sel].iloc[0]
        
        # Nowoczesny kafelek z obecnym stanem
        st.info(f"Obecnie w magazynie: **{selected_prod['liczba']}** szt.")
        
        col1, col2 = st.columns(2)
        with col1:
            op_type = st.radio("Typ operacji", ["Przyjęcie (+)", "Wydanie (-)"])
        with col2:
            amount = st.number_input("Liczba sztuk", min_value=1, step=1)

        if st.button("Wykonaj operację", use_container_width=True):
            # KLUCZOWE: Rzutowanie na typy natywne Pythona, aby uniknąć błędów HTTPX
            curr_qty = int(selected_prod['liczba'])
            change = int(amount)
            new_qty = curr_qty + change if op_type == "Przyjęcie (+)" else curr_qty - change
            
            if new_qty < 0:
                st.error("❌ BŁĄD: Stan magazynowy nie może być ujemny!")
            else:
                try:
                    product_id = int(selected_prod['id'])
                    supabase.table("produkty").update({
                        "liczba": new_qty
                    }).eq("id", product_id).execute()
                    
                    st.success(f"✅ Sukces! Nowy stan produktu {prod_sel}: {new_qty}")
                    # Krótkie oczekiwanie przed odświeżeniem, by użytkownik widział sukces
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd bazy danych: {e}")
    else:
        st.warning("Dodaj produkty, zanim zaczniesz operacje.")

# --- WIDOK: EKSPORT ---
elif menu == "Eksport":
    st.header("📤 Eksport danych")
    df_p = get_products()
    
    if not df_p.empty:
        st.write("Eksportuj aktualną listę produktów do pliku CSV.")
        # Czyszczenie danych do eksportu
        export_df = df_p[['nazwa', 'liczba', 'cena', 'kategoria_nazwa']].rename(columns={
            "nazwa": "Nazwa Produktu",
            "liczba": "Ilość",
            "cena": "Cena",
            "kategoria_nazwa": "Kategoria"
        })
        
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Pobierz plik CSV",
            data=csv,
            file_name="stan_magazynu.csv",
            mime="text/csv"
        )
    else:
        st.info("Brak danych do eksportu.")
