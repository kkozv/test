import streamlit as st
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="Magazyn | Streamlit + Supabase", layout="wide")

# ========= Supabase init (bez zmian w DB) =========
# Preferuj st.secrets (Streamlit Cloud / lokalnie przez secrets.toml),
# ale zostawiam fallback na ręczne wklejenie, gdybyście tak robili na zajęciach.
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# ========= Helpers =========
def sb_select(table: str, sel: str = "*", **kwargs):
    q = supabase.table(table).select(sel)
    # kwargs: eq={"col": val}, order=("col", True/False), limit=int
    if "eq" in kwargs and kwargs["eq"]:
        for c, v in kwargs["eq"].items():
            q = q.eq(c, v)
    if "order" in kwargs and kwargs["order"]:
        col, desc = kwargs["order"]
        q = q.order(col, desc=desc)
    if "limit" in kwargs and kwargs["limit"]:
        q = q.limit(kwargs["limit"])
    return q.execute().data or []

def sb_insert(table: str, data: dict):
    return supabase.table(table).insert(data).execute()

def sb_update(table: str, row_id, data: dict):
    return supabase.table(table).update(data).eq("id", row_id).execute()

def sb_delete(table: str, row_id):
    return supabase.table(table).delete().eq("id", row_id).execute()

def to_df(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def refresh():
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=10)
def load_data():
    kategorie = sb_select("kategorie", "*", order=("nazwa", False))
    produkty = sb_select("produkty", "*", order=("nazwa", False))
    return kategorie, produkty

def kat_maps(kategorie):
    name_to_id = {k["nazwa"]: k["id"] for k in kategorie}
    id_to_name = {k["id"]: k["nazwa"] for k in kategorie}
    return name_to_id, id_to_name


# ========= Layout =========
st.title("📦 Magazyn")
st.caption("Wersja ćwiczeniowa: dashboard + filtry + edycja + operacje IN/OUT (bez zmian w bazie)")

kategorie, produkty = load_data()
kat_name_to_id, kat_id_to_name = kat_maps(kategorie)

# Sidebar navigation
with st.sidebar:
    st.header("Menu")
    page = st.radio(
        "Wybierz widok",
        ["Dashboard", "Produkty", "Kategorie", "Operacje", "Eksport"],
        index=0,
    )
    st.divider()
    st.subheader("Szybkie statystyki")
    total_szt = sum(safe_int(p.get("liczba")) for p in produkty)
    total_val = sum(safe_int(p.get("liczba")) * safe_float(p.get("cena")) for p in produkty)
    st.metric("Stan łączny", f"{total_szt} szt.")
    st.metric("Wartość zapasu", f"{total_val:,.2f} zł".replace(",", " "))
    st.caption("Dane odświeżają się automatycznie co kilka sekund.")
    st.divider()
    if st.button("Odśwież teraz"):
        refresh()


# ========= Pages =========
# ------------------- DASHBOARD -------------------
if page == "Dashboard":
    st.subheader("📊 Dashboard")

    if not produkty:
        st.info("Brak produktów w bazie. Dodaj kategorie i produkty w innych zakładkach.")
        st.stop()

    # KPI
    total_items = sum(safe_int(p.get("liczba")) for p in produkty)
    total_value = sum(safe_int(p.get("liczba")) * safe_float(p.get("cena")) for p in produkty)
    unique_products = len(produkty)
    unique_categories = len(kategorie)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Liczba produktów", unique_products)
    c2.metric("Liczba kategorii", unique_categories)
    c3.metric("Stan łączny", f"{total_items} szt.")
    c4.metric("Wartość zapasu", f"{total_value:,.2f} zł".replace(",", " "))

    st.divider()

    # TOP produkty wg wartości
    rows = []
    for p in produkty:
        szt = safe_int(p.get("liczba"))
        cena = safe_float(p.get("cena"))
        wart = szt * cena
        rows.append({
            "Produkt": p.get("nazwa"),
            "Kategoria": kat_id_to_name.get(p.get("kategoria_id"), "—"),
            "Ilość": szt,
            "Cena": cena,
            "Wartość": wart
        })
    df = pd.DataFrame(rows).sort_values("Wartość", ascending=False)

    left, right = st.columns([2, 1])
    with left:
        st.markdown("**TOP 10 produktów wg wartości zapasu**")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)
    with right:
        st.markdown("**Struktura wartości wg kategorii**")
        by_cat = df.groupby("Kategoria", dropna=False)["Wartość"].sum().sort_values(ascending=False)
        st.bar_chart(by_cat)

    st.divider()
    st.markdown("**Produkty z niskim stanem (próg: ≤ 5 szt.)**")
    low = df[df["Ilość"] <= 5].sort_values("Ilość", ascending=True)
    if low.empty:
        st.success("Brak produktów o niskim stanie.")
    else:
        st.dataframe(low, use_container_width=True, hide_index=True)

# ------------------- PRODUKTY -------------------
elif page == "Produkty":
    st.subheader("🛍️ Produkty")

    colA, colB = st.columns([2, 1])

    with colB:
        st.markdown("### Dodaj produkt")
        if not kategorie:
            st.warning("Najpierw dodaj kategorię w zakładce „Kategorie”.")
        else:
            with st.form("add_product", clear_on_submit=True):
                name = st.text_input("Nazwa produktu")
                qty = st.number_input("Ilość (szt.)", min_value=0, step=1)
                price = st.number_input("Cena (zł)", min_value=0.0, format="%.2f")
                cat = st.selectbox("Kategoria", options=list(kat_name_to_id.keys()))
                submitted = st.form_submit_button("Dodaj")
                if submitted:
                    if not name.strip():
                        st.error("Nazwa produktu nie może być pusta.")
                    else:
                        sb_insert("produkty", {
                            "nazwa": name.strip(),
                            "liczba": int(qty),
                            "cena": float(price),
                            "kategoria_id": kat_name_to_id[cat],
                        })
                        st.success("Dodano produkt.")
                        refresh()

    with colA:
        st.markdown("### Lista i filtrowanie")

        if not produkty:
            st.info("Brak produktów.")
            st.stop()

        # Filtry
        f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
        with f1:
            q = st.text_input("Szukaj po nazwie", placeholder="np. rękawiczki")
        with f2:
            cat_filter = st.selectbox("Kategoria", options=["Wszystkie"] + list(kat_name_to_id.keys()))
        with f3:
            sort_col = st.selectbox("Sortuj", options=["Nazwa", "Ilość", "Cena"])
        with f4:
            desc = st.checkbox("Malejąco", value=False)

        # Dataframe
        table = []
        for p in produkty:
            table.append({
                "ID": p.get("id"),
                "Nazwa": p.get("nazwa"),
                "Kategoria": kat_id_to_name.get(p.get("kategoria_id"), "—"),
                "Ilość": safe_int(p.get("liczba")),
                "Cena": safe_float(p.get("cena")),
                "Wartość": safe_int(p.get("liczba")) * safe_float(p.get("cena")),
            })
        df = pd.DataFrame(table)

        if q.strip():
            df = df[df["Nazwa"].str.contains(q.strip(), case=False, na=False)]

        if cat_filter != "Wszystkie":
            df = df[df["Kategoria"] == cat_filter]

        sort_map = {"Nazwa": "Nazwa", "Ilość": "Ilość", "Cena": "Cena"}
        df = df.sort_values(sort_map[sort_col], ascending=not desc)

        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

        st.divider()

        # Edycja / usuwanie (po ID)
        st.markdown("### Edycja / usuwanie")
        selected_name = st.selectbox("Wybierz produkt", options=df["Nazwa"].tolist())
        selected_row = df[df["Nazwa"] == selected_name].iloc[0]
        selected_id = selected_row["ID"]

        p_obj = next((x for x in produkty if x.get("id") == selected_id), None)
        if not p_obj:
            st.error("Nie znaleziono produktu.")
            st.stop()

        e1, e2 = st.columns([2, 1])
        with e1:
            with st.form("edit_product"):
                new_name = st.text_input("Nazwa", value=p_obj.get("nazwa", ""))
                new_qty = st.number_input("Ilość (szt.)", min_value=0, step=1, value=safe_int(p_obj.get("liczba")))
                new_price = st.number_input("Cena (zł)", min_value=0.0, format="%.2f", value=safe_float(p_obj.get("cena")))
                # kategoria
                current_cat_name = kat_id_to_name.get(p_obj.get("kategoria_id"), None)
                cat_options = list(kat_name_to_id.keys())
                cat_index = cat_options.index(current_cat_name) if current_cat_name in cat_options else 0
                new_cat = st.selectbox("Kategoria", options=cat_options, index=cat_index)

                save = st.form_submit_button("Zapisz zmiany")
                if save:
                    if not new_name.strip():
                        st.error("Nazwa nie może być pusta.")
                    else:
                        sb_update("produkty", selected_id, {
                            "nazwa": new_name.strip(),
                            "liczba": int(new_qty),
                            "cena": float(new_price),
                            "kategoria_id": kat_name_to_id[new_cat],
                        })
                        st.success("Zapisano zmiany.")
                        refresh()

        with e2:
            st.markdown("**Usuń produkt**")
            st.warning("To usuwa rekord z bazy.")
            confirm = st.checkbox("Potwierdzam usunięcie")
            if st.button("Usuń", disabled=not confirm):
                sb_delete("produkty", selected_id)
                st.success("Usunięto produkt.")
                refresh()

# ------------------- KATEGORIE -------------------
elif page == "Kategorie":
    st.subheader("📂 Kategorie")

    left, right = st.columns([2, 1])

    with right:
        st.markdown("### Dodaj kategorię")
        with st.form("add_cat", clear_on_submit=True):
            name = st.text_input("Nazwa kategorii")
            desc = st.text_area("Opis")
            ok = st.form_submit_button("Dodaj")
            if ok:
                if not name.strip():
                    st.error("Nazwa kategorii nie może być pusta.")
                else:
                    sb_insert("kategorie", {"nazwa": name.strip(), "opis": desc.strip()})
                    st.success("Dodano kategorię.")
                    refresh()

    with left:
        if not kategorie:
            st.info("Brak kategorii.")
            st.stop()

        st.markdown("### Lista kategorii")
        dfk = to_df([{"ID": k["id"], "Nazwa": k["nazwa"], "Opis": k.get("opis", "")} for k in kategorie])
        st.dataframe(dfk.drop(columns=["ID"]), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Edycja / usuwanie")
        selected = st.selectbox("Wybierz kategorię", options=dfk["Nazwa"].tolist())
        row = dfk[dfk["Nazwa"] == selected].iloc[0]
        kid = row["ID"]
        kobj = next((x for x in kategorie if x.get("id") == kid), None)

        with st.form("edit_cat"):
            new_name = st.text_input("Nazwa", value=kobj.get("nazwa", ""))
            new_desc = st.text_area("Opis", value=kobj.get("opis", "") or "")
            save = st.form_submit_button("Zapisz")
            if save:
                if not new_name.strip():
                    st.error("Nazwa nie może być pusta.")
                else:
                    sb_update("kategorie", kid, {"nazwa": new_name.strip(), "opis": new_desc.strip()})
                    st.success("Zapisano.")
                    refresh()

        st.warning("Usunięcie kategorii może nie zadziałać, jeśli istnieją produkty powiązane (zależnie od FK).")
        confirm = st.checkbox("Potwierdzam usunięcie kategorii")
        if st.button("Usuń kategorię", disabled=not confirm):
            try:
                sb_delete("kategorie", kid)
                st.success("Usunięto kategorię.")
                refresh()
            except Exception as e:
                st.error(f"Nie udało się usunąć. Najpierw usuń/zmień produkty z tej kategorii. Szczegóły: {e}")

# ------------------- OPERACJE (IN/OUT bez tabeli ruchów) -------------------
elif page == "Operacje":
    st.subheader("🔁 Operacje magazynowe (bez zmian w bazie)")

    if not produkty:
        st.info("Brak produktów.")
        st.stop()

    st.markdown(
        "Tu robisz przyjęcie i wydanie towaru poprzez aktualizację pola **liczba**. "
        "Nie zapisujemy historii w bazie (bo nie wolno zmieniać DB), ale UI wygląda jak WMS."
    )

    names = [p["nazwa"] for p in produkty]
    prod_name = st.selectbox("Produkt", options=names)
    prod = next(p for p in produkty if p["nazwa"] == prod_name)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.info(
            f"Stan bieżący: **{safe_int(prod.get('liczba'))} szt.** | "
            f"Cena: **{safe_float(prod.get('cena')):.2f} zł** | "
            f"Kategoria: **{kat_id_to_name.get(prod.get('kategoria_id'), '—')}**"
        )
    with col2:
        qty = st.number_input("Ilość operacji", min_value=1, step=1)
    with col3:
        op = st.selectbox("Typ", options=["Przyjęcie (IN)", "Wydanie (OUT)"])

    if st.button("Wykonaj operację"):
        current = safe_int(prod.get("liczba"))
        qty_i = int(qty)

        if op.startswith("Przyjęcie"):
            new_val = current + qty_i
        else:
            new_val = current - qty_i
            if new_val < 0:
                st.error(f"Brak wystarczającego stanu. Stan={current}, próba wydania={qty_i}.")
                st.stop()

        sb_update("produkty", prod["id"], {"liczba": new_val})
        st.success(f"Zaktualizowano stan: {current} → {new_val}")
        refresh()

# ------------------- EKSPORT -------------------
elif page == "Eksport":
    st.subheader("⬇️ Eksport danych")

    st.markdown("Pobierz produkty i kategorie jako CSV (przydatne do zaliczenia jako „raport”).")

    dfk = to_df([{"id": k["id"], "nazwa": k["nazwa"], "opis": k.get("opis", "")} for k in kategorie])
    dfp = []
    for p in produkty:
        dfp.append({
            "id": p.get("id"),
            "nazwa": p.get("nazwa"),
            "kategoria": kat_id_to_name.get(p.get("kategoria_id"), "—"),
            "liczba": safe_int(p.get("liczba")),
            "cena": safe_float(p.get("cena")),
            "wartosc": safe_int(p.get("liczba")) * safe_float(p.get("cena")),
        })
    dfp = pd.DataFrame(dfp)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Kategorie**")
        st.dataframe(dfk, use_container_width=True, hide_index=True)
        st.download_button(
            "Pobierz kategorie.csv",
            data=dfk.to_csv(index=False).encode("utf-8"),
            file_name="kategorie.csv",
            mime="text/csv",
        )
    with c2:
        st.markdown("**Produkty**")
        st.dataframe(dfp, use_container_width=True, hide_index=True)
        st.download_button(
            "Pobierz produkty.csv",
            data=dfp.to_csv(index=False).encode("utf-8"),
            file_name="produkty.csv",
            mime="text/csv",
        )
