import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Inwentaryzator 3000", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- FUNKCJE POMOCNICZE (LOGIKA BIZNESOWA) ---
def get_categories():
    response = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(response.data)

def get_products():
    # Pobieramy produkty wraz z nazwą kategorii (Join)
    response = supabase.table("produkty").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
    return df

# --- SIDEBAR - NAWIGACJA ---
with st.sidebar:
    st.title("📦 Magazyn v2.0")
    menu = st.radio("Nawigacja", ["Dashboard", "Produkty", "Kategorie", "Operacje", "Eksport"])
    st.divider()
    st.info("Zalogowano jako: Administrator")

# --- MODUŁ 1: DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Statystyki Magazynowe")
    df_p = get_products()
    
    if not df_p.empty:
        col1, col2, col3 = st.columns(3)
        total_value = (df_p['liczba'] * df_p['cena']).sum()
        
        col1.metric("Liczba Produktów", len(df_p))
        col2.metric("Łączny Stan", int(df_p['liczba'].sum()))
        col3.metric("Wartość Magazynu", f"{total_value:,.2f} PLN")
        
        st.subheader("Rozkład kategorii")
        cat_counts = df_p['kategoria'].value_counts()
        st.bar_chart(cat_counts)
    else:
        st.warning("Brak danych do wyświetlenia.")

# --- MODUŁ 2: PRODUKTY (CRUD) ---
elif menu == "Produkty":
    st.header("🛒 Zarządzanie Produktami")
    
    tab1, tab2 = st.tabs(["Lista produktów", "Dodaj nowy"])
    
    df_p = get_products()
    df_c = get_categories()

    with tab1:
        # Filtrowanie i Wyszukiwanie
        search = st.text_input("🔍 Szukaj produktu po nazwie")
        if not df_p.empty:
            filtered_df = df_p[df_p['nazwa'].str.contains(search, case=False)]
            
            # Tabela z edycją
            edited_df = st.data_editor(
                filtered_df[['id', 'nazwa', 'liczba', 'cena', 'kategoria']], 
                num_rows="dynamic",
                key="prod_editor",
                disabled=["id", "kategoria"]
            )
            
            # Przycisk Usuwania (Multiselect)
            to_delete = st.multiselect("Wybierz produkty do usunięcia", df_p['nazwa'].tolist())
            if st.button("Usuń zaznaczone", type="primary"):
                for name in to_delete:
                    supabase.table("produkty").delete().eq("nazwa", name).execute()
                st.rerun()

    with tab2:
        with st.form("add_product_form"):
            new_name = st.text_input("Nazwa produktu")
            new_qty = st.number_input("Ilość", min_value=0, step=1)
            new_price = st.number_input("Cena (PLN)", min_value=0.0, step=0.01)
            cat_choice = st.selectbox("Kategoria", df_c['nazwa'].tolist() if not df_c.empty else [])
            
            if st.form_submit_button("Dodaj produkt"):
                cat_id = df_c[df_c['nazwa'] == cat_choice]['id'].values[0]
                supabase.table("produkty").insert({
                    "nazwa": new_name, "liczba": new_qty, "cena": new_price, "kategoria_id": int(cat_id)
                }).execute()
                st.success("Produkt dodany!")
                st.rerun()

# --- MODUŁ 3: KATEGORIE ---
elif menu == "Kategorie":
    st.header("📁 Kategorie Produktów")
    df_c = get_categories()
    
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.dataframe(df_c, use_container_width=True)
        
    with col_r:
        st.subheader("Zarządzaj")
        with st.expander("Dodaj kategorię"):
            c_name = st.text_input("Nazwa")
            c_desc = st.text_area("Opis")
            if st.button("Zapisz kategorię"):
                supabase.table("kategorie").insert({"nazwa": c_name, "opis": c_desc}).execute()
                st.rerun()

# --- MODUŁ 4: OPERACJE (PRZYJĘCIE/WYDANIE) ---
elif menu == "Operacje":
    st.header("🔄 Operacje Magazynowe")
    df_p = get_products()
    
    if not df_p.empty:
        with st.container(border=True):
            prod_to_change = st.selectbox("Wybierz produkt", df_p['nazwa'].tolist())
            op_type = st.radio("Typ operacji", ["Przyjęcie (+)", "Wydanie (-)"], horizontal=True)
            amount = st.number_input("Ilość", min_value=1, step=1)
            
            if st.button("Wykonaj operację"):
                current_qty = df_p[df_p['nazwa'] == prod_to_change]['liczba'].values[0]
                new_qty = current_qty + amount if "Przyjęcie" in op_type else current_qty - amount
                
                if new_qty < 0:
                    st.error("Błąd: Nie można wydać więcej niż jest w magazynie!")
                else:
                    supabase.table("produkty").update({"liczba": new_qty}).eq("nazwa", prod_to_change).execute()
                    st.success(f"Zaktualizowano stan dla {prod_to_change}. Nowy stan: {new_qty}")
    else:
        st.info("Dodaj produkty, aby móc wykonywać operacje.")

# --- MODUŁ 5: EKSPORT ---
elif menu == "Eksport":
    st.header("📥 Eksport Danych")
    df_p = get_products()
    
    if not df_p.empty:
        csv = df_p.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Pobierz raport CSV",
            data=csv,
            file_name="stan_magazynu.csv",
            mime="text/csv",
        )
        st.write("Podgląd danych do eksportu:")
        st.table(df_p[['nazwa', 'liczba', 'cena', 'kategoria']].head(10))
