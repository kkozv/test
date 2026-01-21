import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro", layout="wide", page_icon="📦")

# Inicjalizacja połączenia z Supabase (st.secrets)
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- FUNKCJE POMOCNICZE (CRUD) ---
def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(res.data)

def get_products():
    # Pobieramy produkty z dołączoną nazwą kategorii (Join)
    res = supabase.table("produkty").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
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
    st.info("System zarządzania stanami magazynowymi v1.0")

# --- WIDOK: DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Dashboard")
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
        
        st.subheader("Stan magazynowy wg kategorii")
        chart_data = df_p.groupby('kategoria_nazwa')['liczba'].sum()
        st.bar_chart(chart_data)
    else:
        st.warning("Brak danych do wyświetlenia statystyk.")

# --- WIDOK: PRODUKTY ---
elif menu == "Produkty":
    st.header("🛒 Zarządzanie Produktami")
    df_p = get_products()
    df_k = get_categories()

    tab1, tab2 = st.tabs(["Lista produktów", "Dodaj / Edytuj"])

    with tab1:
        # Filtrowanie i wyszukiwanie
        search = st.text_input("Szukaj produktu po nazwie...")
        if not df_p.empty:
            filtered_df = df_p[df_p['nazwa'].str.contains(search, case=False)]
            st.dataframe(filtered_df[['id', 'nazwa', 'liczba', 'cena', 'kategoria_nazwa']], use_container_width=True)
        else:
            st.info("Magazyn jest pusty.")

    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Nowy Produkt")
            with st.form("add_product_form", clear_on_submit=True):
                n_name = st.text_input("Nazwa produktu")
                n_qty = st.number_input("Ilość", min_value=0, step=1)
                n_price = st.number_input("Cena (PLN)", min_value=0.0, step=0.01)
                n_cat = st.selectbox("Kategoria", options=df_k['nazwa'].tolist() if not df_k.empty else ["Brak"])
                
                if st.form_submit_button("Dodaj produkt"):
                    cat_id = int(df_k[df_k['nazwa'] == n_cat]['id'].values[0])
                    supabase.table("produkty").insert({
                        "nazwa": n_name, "liczba": n_qty, "cena": n_price, "kategoria_id": cat_id
                    }).execute()
                    st.success("Dodano produkt!")
                    st.rerun()

        with col_b:
            st.subheader("Edytuj / Usuń")
            if not df_p.empty:
                to_edit = st.selectbox("Wybierz produkt", options=df_p['nazwa'].tolist())
                prod_data = df_p[df_p['nazwa'] == to_edit].iloc[0]
                
                with st.form("edit_product_form"):
                    e_name = st.text_input("Nowa nazwa", value=prod_data['nazwa'])
                    e_qty = st.number_input("Nowa ilość", value=int(prod_data['liczba']))
                    e_price = st.number_input("Nowa cena", value=float(prod_data['cena']))
                    
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Zapisz zmiany"):
                        supabase.table("produkty").update({
                            "nazwa": e_name, "liczba": e_qty, "cena": e_price
                        }).eq("id", int(prod_data['id'])).execute()
                        st.success("Zaktualizowano!")
                        st.rerun()
                    
                    if c2.form_submit_button("USUŃ PRODUKT"):
                        supabase.table("produkty").delete().eq("id", int(prod_data['id'])).execute()
                        st.error("Usunięto!")
                        st.rerun()

# --- WIDOK: KATEGORIE ---
elif menu == "Kategorie":
    st.header("📂 Kategorie")
    df_k = get_categories()

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Zarządzaj")
        mode = st.radio("Akcja", ["Dodaj nową", "Edytuj/Usuń istniejącą"])
        
        if mode == "Dodaj nową":
            with st.form("add_cat"):
                cat_n = st.text_input("Nazwa kategorii")
                cat_d = st.text_area("Opis")
                if st.form_submit_button("Dodaj"):
                    supabase.table("kategorie").insert({"nazwa": cat_n, "opis": cat_d}).execute()
                    st.rerun()
        else:
            if not df_k.empty:
                cat_to_mod = st.selectbox("Wybierz kategorię", df_k['nazwa'].tolist())
                cat_row = df_k[df_k['nazwa'] == cat_to_mod].iloc[0]
                new_cat_n = st.text_input("Nazwa", value=cat_row['nazwa'])
                if st.button("Aktualizuj nazwę"):
                    supabase.table("kategorie").update({"nazwa": new_cat_n}).eq("id", int(cat_row['id'])).execute()
                    st.rerun()
                if st.button("USUŃ KATEGORIĘ"):
                    supabase.table("kategorie").delete().eq("id", int(cat_row['id'])).execute()
                    st.rerun()

    with col2:
        st.subheader("Lista kategorii")
        st.table(df_k)

# --- WIDOK: OPERACJE (PRZYJĘCIE/WYDANIE) ---
elif menu == "Operacje":
    st.header("🔄 Operacje Magazynowe")
    df_p = get_products()
    
    if not df_p.empty:
        prod_sel = st.selectbox("Wybierz produkt do operacji", df_p['nazwa'].tolist())
        selected_prod = df_p[df_p['nazwa'] == prod_sel].iloc[0]
        
        st.info(f"Obecny stan: **{selected_prod['liczba']}**")
        
        col1, col2 = st.columns(2)
        with col1:
            op_type = st.radio("Typ operacji", ["Przyjęcie (+)", "Wydanie (-)"])
        with col2:
            amount = st.number_input("Ilość", min_value=1, step=1)

        if st.button("Wykonaj operację"):
            new_qty = selected_prod['liczba'] + amount if op_type == "Przyjęcie (+)" else selected_prod['liczba'] - amount
            
            if new_qty < 0:
                st.error("Błąd: Brak wystarczającej ilości towaru!")
            else:
                supabase.table("produkty").update({"liczba": new_qty}).eq("id", int(selected_prod['id'])).execute()
                st.success(f"Operacja zakończona. Nowy stan: {new_qty}")
                st.rerun()
    else:
        st.warning("Brak produktów w bazie.")

# --- WIDOK: EKSPORT ---
elif menu == "Eksport":
    st.header("📤 Eksport Danych")
    df_p = get_products()
    
    if not df_p.empty:
        st.write("Pobierz pełną listę produktów wraz z kategoriami w formacie CSV.")
        csv = df_p[['nazwa', 'liczba', 'cena', 'kategoria_nazwa']].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Pobierz plik CSV",
            data=csv,
            file_name="magazyn_export.csv",
            mime="text/csv"
        )
    else:
        st.info("Brak danych do eksportu.")
