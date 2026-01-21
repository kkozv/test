import streamlit as st
from supabase import create_client, Client

# Połączenie z Supabase
url = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else "https://orqmqtuftyjwzgewjwdo.supabase.co"
key = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else "sb_publishable_wsgQI7Vay1ccTgmLbQsjwQ_yFAXNko4"

supabase: Client = create_client(url, key)

st.title("📦 Testowa aplikacja magazynowa")

# ======================
# KATEGORIE
# ======================
st.header("Kategorie")

with st.expander("Dodaj kategorię"):
    kat_nazwa = st.text_input("Nazwa kategorii")
    kat_opis = st.text_area("Opis kategorii")
    if st.button("Dodaj kategorię"):
        supabase.table("kategorie").insert({
            "nazwa": kat_nazwa,
            "opis": kat_opis
        }).execute()
        st.success("Dodano kategorię")
        st.rerun()

kategorie = supabase.table("kategorie").select("*").execute().data

if kategorie:
    for k in kategorie:
        st.write(f"• {k['nazwa']} – {k['opis']}")
else:
    st.info("Brak kategorii")

st.divider()

# ======================
# PRODUKTY
# ======================
st.header("Produkty")

kat_map = {k["nazwa"]: k["id"] for k in kategorie} if kategorie else {}

with st.expander("Dodaj produkt"):
    p_nazwa = st.text_input("Nazwa produktu")
    p_ilosc = st.number_input("Ilość", min_value=0, step=1)
    p_cena = st.number_input("Cena", min_value=0.0, format="%.2f")

    if kat_map:
        p_kat = st.selectbox("Kategoria", list(kat_map.keys()))
    else:
        p_kat = None
        st.warning("Najpierw dodaj kategorię")

    if st.button("Dodaj produkt"):
        if p_kat:
            supabase.table("produkty").insert({
                "nazwa": p_nazwa,
                "liczba": p_ilosc,
                "cena": p_cena,
                "kategoria_id": kat_map[p_kat]
            }).execute()
            st.success("Dodano produkt")
            st.rerun()

produkty = supabase.table("produkty").select("*").execute().data

if produkty:
    for p in produkty:
        st.write(f"• {p['nazwa']} | {p['liczba']} szt. | {p['cena']} zł")
else:
    st.info("Brak produktów")
