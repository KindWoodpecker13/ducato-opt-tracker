# app.py
# ITPL Configurator & OPT Checker (Streamlit)
# Requisiti: streamlit, pandas, openpyxl (solo se usi excel extraction)
# Avvio: streamlit run app.py

import streamlit as st
import pandas as pd
import os
import re

st.set_page_config(page_title="ITPL Configurator & OPT Checker", layout="wide")

# -------------------------
# Percorsi file (modifica se necessario)
# -------------------------
A_PATH = "decode_sincom_A.csv"      # sep=';'
B_PATH = "decode_sincom_B.csv"      # sep=';'
N_PATH = "decode_sincom_n.csv"      # sep=';'
LEVEL1_PATH = "level1_extracted.csv"
OPTS_PATH = "opts.csv"
CONSTRAINTS_PATH = "constraints.csv"

# -------------------------
# Helper: controllo DataFrame caricato
# -------------------------
def df_loaded_ok(df):
    return (df is not None) and hasattr(df, "empty") and (not df.empty)

# -------------------------
# Caricamento CSV robusto
# -------------------------
def try_read_csv(path, sep=",", encoding="utf-8", header="infer"):
    if not os.path.exists(path):
        return None
    try:
        if header == "infer":
            return pd.read_csv(path, sep=sep, dtype=str, encoding=encoding).fillna("")
        else:
            return pd.read_csv(path, sep=sep, dtype=str, encoding=encoding, header=header).fillna("")
    except Exception:
        # prova fallback con header=None
        try:
            return pd.read_csv(path, sep=sep, dtype=str, encoding=encoding, header=None).fillna("")
        except Exception:
            return None

# Carica con separatori probabili
df_A_raw = try_read_csv(A_PATH, sep=";", encoding="utf-8")
df_B_raw = try_read_csv(B_PATH, sep=";", encoding="utf-8")
df_N_raw = try_read_csv(N_PATH, sep=";", encoding="utf-8")
df_level1_raw = try_read_csv(LEVEL1_PATH, sep=",", encoding="utf-8")
df_opts_raw = try_read_csv(OPTS_PATH, sep=",", encoding="utf-8")
df_constraints_raw = try_read_csv(CONSTRAINTS_PATH, sep=",", encoding="utf-8")

# -------------------------
# Normalizzazione decode A/B/N (tollerante)
# -------------------------
def normalize_A(df, path=A_PATH):
    if df is None:
        return None
    cols = list(df.columns)
    expected = ["model_code","gvw","length_code","output_symbol"]
    # se ha già le colonne attese
    if all(c in [c.strip() for c in cols] for c in expected):
        df = df.rename(columns={c:c.strip() for c in cols})
        df = df.astype(str).apply(lambda col: col.str.strip())
        return df
    # se manca header (prima riga dati) o header non standard -> rinomina prime 4 colonne
    if len(cols) >= 4:
        df = df.rename(columns={cols[0]:"model_code", cols[1]:"gvw", cols[2]:"length_code", cols[3]:"output_symbol"})
        df["model_code"] = df["model_code"].astype(str).str.strip()
        df["gvw"] = df["gvw"].astype(str).str.strip()
        df["length_code"] = df["length_code"].astype(str).str.strip()
        df["output_symbol"] = df["output_symbol"].astype(str).str.strip()
        st.sidebar.info(f"{os.path.basename(path)}: prime 4 colonne rinominate come model_code, gvw, length_code, output_symbol")
        return df
    # fallback: non normalizzabile
    st.sidebar.error(f"{os.path.basename(path)}: non è stato possibile normalizzare (colonne: {cols})")
    return None

def normalize_B(df, path=B_PATH):
    if df is None:
        return None
    cols = list(df.columns)
    expected = ["height_code","body_label","output_symbol"]
    if all(c in [c.strip() for c in cols] for c in expected):
        df = df.rename(columns={c:c.strip() for c in cols})
        df = df.astype(str).apply(lambda col: col.str.strip())
        return df
    if len(cols) >= 3:
        df = df.rename(columns={cols[0]:"height_code", cols[1]:"body_label", cols[2]:"output_symbol"})
        df["height_code"] = df["height_code"].astype(str).str.strip()
        df["body_label"] = df["body_label"].astype(str).str.strip()
        df["output_symbol"] = df["output_symbol"].astype(str).str.strip()
        st.sidebar.info(f"{os.path.basename(path)}: prime 3 colonne rinominate come height_code, body_label, output_symbol")
        return df
    st.sidebar.error(f"{os.path.basename(path)}: non è stato possibile normalizzare (colonne: {cols})")
    return None

def normalize_N(df, path=N_PATH):
    if df is None:
        return None
    cols = list(df.columns)
    expected = ["engine_family","engine_full_label","short_label","engine_digit"]
    if all(c in [c.strip() for c in cols] for c in expected):
        df = df.rename(columns={c:c.strip() for c in cols})
        df = df.astype(str).apply(lambda col: col.str.strip())
        return df
    if len(cols) >= 4:
        df = df.rename(columns={cols[0]:"engine_family", cols[1]:"engine_full_label", cols[2]:"short_label", cols[3]:"engine_digit"})
        df["engine_family"] = df["engine_family"].astype(str).str.strip()
        df["engine_full_label"] = df["engine_full_label"].astype(str).str.strip()
        df["short_label"] = df["short_label"].astype(str).str.strip()
        df["engine_digit"] = df["engine_digit"].astype(str).str.strip()
        st.sidebar.info(f"{os.path.basename(path)}: prime 4 colonne rinominate come engine_family, engine_full_label, short_label, engine_digit")
        return df
    st.sidebar.error(f"{os.path.basename(path)}: non è stato possibile normalizzare (colonne: {cols})")
    return None

df_A = normalize_A(df_A_raw)
df_B = normalize_B(df_B_raw)
df_N = normalize_N(df_N_raw)

# -------------------------
# Normalizza level1, opts, constraints (se presenti)
# -------------------------
def normalize_level1(df):
    if df is None:
        return None
    cols = list(df.columns)
    if len(cols) >= 5 and cols[:5] != ["sigla_base","body_label","sevel","gliwice","notes"]:
        df = df.rename(columns={cols[0]:"sigla_base", cols[1]:"body_label", cols[2]:"sevel", cols[3]:"gliwice", cols[4]:"notes"})
    # normalizza flags
    if "sevel" in df.columns:
        df["sevel"] = df["sevel"].astype(str).str.strip().replace({"":"0","-":"0"})
        df["sevel"] = df["sevel"].apply(lambda x: "1" if x not in ("0","", "0.0") else "0")
    if "gliwice" in df.columns:
        df["gliwice"] = df["gliwice"].astype(str).str.strip().replace({"":"0","-":"0"})
        df["gliwice"] = df["gliwice"].apply(lambda x: "1" if x not in ("0","", "0.0") else "0")
    return df

df_level1 = normalize_level1(df_level1_raw)
df_opts = df_opts_raw.copy() if df_opts_raw is not None else None
df_constraints = df_constraints_raw.copy() if df_constraints_raw is not None else None

# -------------------------
# Funzioni decode: costruzione sigla
# -------------------------
def find_A_symbol(model_code, gvw, length_code):
    if df_A is None:
        return None
    q = df_A[
        (df_A["model_code"] == str(model_code)) &
        (df_A["gvw"] == str(gvw)) &
        (df_A["length_code"] == str(length_code))
    ]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    q = df_A[
        (df_A["model_code"] == str(model_code)) &
        (df_A["length_code"] == str(length_code))
    ]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    q = df_A[df_A["model_code"] == str(model_code)]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    return None

def find_B_symbol(height_code, body_label):
    if df_B is None:
        return None
    q = df_B[
        (df_B["height_code"] == str(height_code)) &
        (df_B["body_label"].str.upper().str.contains(str(body_label).upper(), na=False))
    ]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    q = df_B[df_B["height_code"] == str(height_code)]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    return None

# -------------------------
# Transmission extraction and engine digit lookup (considers transmission)
# -------------------------
def extract_transmissions_from_dfN(df):
    if df is None:
        return []
    tx_set = set()
    for _, r in df.iterrows():
        for col in ["engine_full_label", "short_label", "engine_family"]:
            val = str(r.get(col,""))
            tokens = re.split(r"[ ,;/\-()]+", val)
            for t in tokens:
                t = t.strip()
                if not t:
                    continue
                if re.match(r"^[A-Za-z]{1,4}\d{0,3}$", t) and len(t) <= 8:
                    tx_set.add(t)
    tx_list = sorted(tx_set)
    tx_list = [t for t in tx_list if not re.match(r"^(KW|HP|EURO|E|VI|VI\.E)$", t.upper())]
    return tx_list

def find_engine_digit(engine_query, transmission_query=None):
    if df_N is None:
        return None
    q = df_N[
        (df_N["short_label"].str.contains(str(engine_query), na=False)) |
        (df_N["engine_family"].str.contains(str(engine_query), na=False))
    ]
    if transmission_query and not q.empty:
        q2 = q[
            q["engine_full_label"].str.contains(str(transmission_query), na=False) |
            q["short_label"].str.contains(str(transmission_query), na=False)
        ]
        if not q2.empty:
            return q2.iloc[0]["engine_digit"]
    if not q.empty:
        return q.iloc[0]["engine_digit"]
    if transmission_query:
        q3 = df_N[
            df_N["engine_full_label"].str.contains(str(transmission_query), na=False) |
            df_N["short_label"].str.contains(str(transmission_query), na=False)
        ]
        if not q3.empty:
            return q3.iloc[0]["engine_digit"]
    return None

# -------------------------
# Lookup producibilità (level1)
# -------------------------
def lookup_producibility(sigla, body_label=None):
    if df_level1 is None or not sigla:
        return None
    q = df_level1[df_level1["sigla_base"] == sigla]
    if body_label:
        q2 = q[q["body_label"].str.upper().str.contains(str(body_label).upper(), na=False)]
        if not q2.empty:
            q = q2
    if q.empty:
        q = df_level1[df_level1["sigla_base"] == sigla]
    if q.empty:
        return None
    row = q.iloc[0]
    return {
        "sigla": row["sigla_base"],
        "body_label": row["body_label"],
        "sevel": True if str(row.get("sevel","0")) == "1" else False,
        "gliwice": True if str(row.get("gliwice","0")) == "1" else False,
        "notes": row.get("notes","")
    }

# -------------------------
# Parser regole e OPT (sicuro)
# -------------------------
def parse_gvw_int(value):
    if not value:
        return None
    s = str(value).lower().replace("kg","").strip()
    try:
        return int(s)
    except:
        m = re.search(r"\d+", s)
        if m:
            return int(m.group())
    return None

def eval_rules(rule_str, context):
    if not rule_str or str(rule_str).strip().lower() in ("", "always", "true"):
        return True
    parts = [p.strip() for p in str(rule_str).split(";") if p.strip()]
    for p in parts:
        if "=" not in p:
            return False
        k, v = p.split("=",1)
        k = k.strip()
        v = v.strip()
        if k == "sigla_prefix":
            if not context.get("sigla","").startswith(v):
                return False
        elif k == "sigla_exact":
            if context.get("sigla","") != v:
                return False
        elif k == "engine_digit_in":
            allowed = [x.strip() for x in v.split(",") if x.strip()]
            if str(context.get("engine_digit","")) not in allowed:
                return False
        elif k == "body_contains":
            if v.upper() not in context.get("body_label","").upper():
                return False
        elif k == "gvw_le":
            g = context.get("gvw")
            if g is None or g > int(v):
                return False
        elif k == "gvw_gt":
            g = context.get("gvw")
            if g is None or g <= int(v):
                return False
        else:
            return False
    return True

def get_opts_for_config(sigla, engine_digit, body_label, gvw):
    ctx = {
        "sigla": sigla or "",
        "engine_digit": str(engine_digit) if engine_digit is not None else "",
        "body_label": body_label or "",
        "gvw": parse_gvw_int(gvw)
    }
    results = []
    if df_opts is None:
        return results
    for _, r in df_opts.iterrows():
        code = r.get("opt_code","")
        descr = r.get("opt_descr","")
        default = (r.get("default_state") or "OPZIONALE").upper()
        rules = r.get("availability_rules","").strip()
        available_by_rule = eval_rules(rules, ctx)
        if default == "SERIE":
            state = "SERIE"
        elif default == "NON_DISP":
            state = "NON_DISP"
        else:
            state = "OPZIONALE" if available_by_rule else "NON_DISP"
        results.append({"opt_code":code,"opt_descr":descr,"state":state,"rules":rules})
    return results

def check_constraints(selected_opts, sigla, engine_digit, body_label, gvw):
    ctx = {
        "sigla": sigla or "",
        "engine_digit": str(engine_digit) if engine_digit is not None else "",
        "body_label": body_label or "",
        "gvw": parse_gvw_int(gvw)
    }
    conflicts = []
    if df_constraints is None:
        return conflicts
    for _, r in df_constraints.iterrows():
        ctype = (r.get("constraint_type") or "").strip()
        subject = (r.get("subject") or "").strip()
        target = (r.get("target") or "").strip()
        cond = (r.get("condition") or "always").strip()
        if not eval_rules(cond, ctx):
            continue
        if ctype == "requires":
            if subject in selected_opts and target not in selected_opts:
                conflicts.append(f"{subject} requires {target}")
        elif ctype == "excludes":
            if subject in selected_opts and target in selected_opts:
                conflicts.append(f"{subject} excludes {target}")
        elif ctype == "mutually_exclusive":
            if subject in selected_opts and target in selected_opts:
                conflicts.append(f"{subject} mutually exclusive with {target}")
    return conflicts

# -------------------------
# Sidebar debug: stato file e prime colonne
# -------------------------
st.sidebar.markdown("### Dati caricati")
def show_df_info(name, df):
    if df is None:
        st.sidebar.write(f"{name}: MANCANTE")
    else:
        try:
            rows = len(df)
        except Exception:
            rows = "?"
        st.sidebar.write(f"{name}: OK — righe {rows}")
        st.sidebar.write(list(df.columns)[:6])

show_df_info("decode A", df_A)
show_df_info("decode B", df_B)
show_df_info("decode n", df_N)
show_df_info("level1", df_level1)
show_df_info("opts", df_opts)
show_df_info("constraints", df_constraints)

# -------------------------
# UI: modalità (switch)
# -------------------------
mode = st.sidebar.radio("Modalità", ["Configura ordine", "Verifica OPT"])

# Mantieni sigla generata in session state per riutilizzo nella Verifica OPT
if "last_generated_sigla" not in st.session_state:
    st.session_state["last_generated_sigla"] = ""

# -------------------------
# Modalità: Configura ordine
# -------------------------
if mode == "Configura ordine":
    st.header("Configura ordine ITPL")
    st.markdown("Costruisci la configurazione passo passo. Il sistema genera la sigla e verifica la producibilità in Sevel/Gliwice.")

    # Popola opzioni da file (fallback a valori hardcoded)
    model_options = sorted(df_A["model_code"].unique()) if df_loaded_ok(df_A) else ["290/252","295/254"]
    length_options = sorted(df_A["length_code"].unique()) if df_loaded_ok(df_A) else ["L2","L3","L4","L2+","L0"]
    # GVW come selectbox (estrai unici da df_A)
    if df_loaded_ok(df_A):
        gvw_options = sorted([g for g in df_A["gvw"].unique() if str(g).strip() != ""])
    else:
        gvw_options = ["2800","3000","3300","3500","4000"]
    # Body version da df_B
    if df_loaded_ok(df_B):
        body_options = sorted([b for b in df_B["body_label"].unique() if str(b).strip() != ""])
    else:
        body_options = ["PANEL VAN","GLAZED VAN","SEMI GLAZED VAN","CHASSIS SINGLE CAB"]

    # Motore e cambio: motore da df_N short_label, cambio estratto
    engine_options = df_N["short_label"].unique().tolist() if df_loaded_ok(df_N) else ["140HP","180HP"]
    transmission_options = extract_transmissions_from_dfN(df_N)
    if not transmission_options:
        transmission_options = ["MT6","AT8"]

    col1, col2, col3 = st.columns(3)
    with col1:
        model_code = st.selectbox("Model / Gamma", options=model_options)
        gvw = st.selectbox("GVW / PTT", options=gvw_options)
        length_code = st.selectbox("Passo / Lunghezza", options=length_options)
    with col2:
        height_code = st.selectbox("Altezza", options=sorted(df_B["height_code"].unique()) if df_loaded_ok(df_B) else ["H1","H2","H3"])
        body_label = st.selectbox("Body / Version", options=body_options)
    with col3:
        engine_query = st.selectbox("Motore (seleziona)", options=engine_options)
        transmission_query = st.selectbox("Cambio (seleziona)", options=transmission_options)
        st.write("Seleziona motore e cambio per ottenere il digit della sigla.")

    if st.button("Genera sigla e verifica producibilità"):
        A = find_A_symbol(model_code, gvw, length_code)
        B = find_B_symbol(height_code, body_label)
        n = find_engine_digit(engine_query, transmission_query)

        if not A or not B or not n:
            st.error(f"Impossibile generare sigla completa. A={A}, B={B}, n={n}")
            if not A:
                st.info("Controlla mapping A (model/gvw/length).")
            if not B:
                st.info("Controlla mapping B (height/body).")
            if not n:
                st.info("Controlla mapping motore/cambio (file decode_sincom_n.csv).")
        else:
            sigla = f"{A}{B}{n}"
            st.session_state["last_generated_sigla"] = sigla
            st.success(f"Sigla generata: {sigla}")

            prod = lookup_producibility(sigla, body_label)
            if prod is None:
                st.warning("Sigla non trovata nel level1: configurazione non producibile in Sevel o Gliwice.")
                st.info("Prova a cambiare lunghezza/altezza/motore per trovare una sigla producibile.")
            else:
                cols = st.columns(3)
                with cols[0]:
                    st.write("**Produzione disponibile**")
                with cols[1]:
                    if prod["sevel"]:
                        st.success("Sevel: disponibile")
                    else:
                        st.error("Sevel: non disponibile")
                with cols[2]:
                    if prod["gliwice"]:
                        st.success("Gliwice: disponibile")
                    else:
                        st.error("Gliwice: non disponibile")

                if prod["sevel"] or prod["gliwice"]:
                    available_plants = []
                    if prod["sevel"]:
                        available_plants.append("Sevel")
                    if prod["gliwice"]:
                        available_plants.append("Gliwice")
                    chosen_plant = st.selectbox("Scegli plant di produzione", options=available_plants)
                    st.write(f"Produzione selezionata: **{chosen_plant}**")
                    if prod.get("notes"):
                        st.info(f"Note: {prod['notes']}")

                    st.markdown("---")
                    st.subheader("OPT (stato base)")
                    opts_list = get_opts_for_config(sigla, n, body_label, gvw)
                    if not opts_list:
                        st.info("Nessun OPT trovato (controlla opts.csv).")
                    else:
                        df_opts_view = pd.DataFrame(opts_list)[["opt_code","opt_descr","state"]]
                        st.dataframe(df_opts_view, use_container_width=True)

                        st.markdown("Seleziona OPT opzionali per simulare vincoli")
                        selectable = [o["opt_code"] for o in opts_list if o["state"] == "OPZIONALE"]
                        selected_opts = st.multiselect("OPT opzionali", options=selectable)
                        conflicts = check_constraints(selected_opts, sigla, n, body_label, gvw)
                        if conflicts:
                            st.error("Conflitti rilevati:")
                            for c in conflicts:
                                st.write(f"- {c}")
                        else:
                            st.success("Nessun conflitto rilevato per la selezione corrente.")

                    st.markdown("---")
                    st.subheader("Riepilogo ordine (testo)")
                    riepilogo = [
                        f"Sigla: {sigla}",
                        f"Model: {model_code}",
                        f"GVW: {gvw}",
                        f"Length: {length_code}",
                        f"Height: {height_code}",
                        f"Body: {body_label}",
                        f"Engine digit: {n}",
                        f"Transmission: {transmission_query}",
                        f"Plant scelto: {chosen_plant}"
                    ]
                    if 'selected_opts' in locals() and selected_opts:
                        riepilogo.append("OPT selezionati: " + ", ".join(selected_opts))
                    riepilogo_text = "\n".join(riepilogo)
                    st.code(riepilogo_text, language="text")
                else:
                    st.warning("Questa configurazione non è producibile in nessuno dei due plant.")
                    st.info("Modifica le scelte per trovare una combinazione producibile.")

# -------------------------
# Modalità: Verifica OPT (usa solo la sigla generata)
# -------------------------
else:
    st.header("Verifica OPT")
    st.markdown("Questa modalità usa la **sigla generata** dal configuratore. Se non hai ancora generato una sigla, vai su 'Configura ordine' e premi 'Genera sigla'.")

    sigla_generated = st.session_state.get("last_generated_sigla", "")
    if not sigla_generated:
        st.warning("Nessuna sigla generata in questa sessione. Vai su 'Configura ordine' per creare una sigla.")
        st.stop()

    st.subheader("Sigla usata per la verifica")
    st.info(f"Sigla generata: **{sigla_generated}**")

    # campi opzionali per contesto (non modificano la sigla)
    body_input = st.selectbox("Body (opzionale, contesto)", options=(sorted(df_B["body_label"].unique()) if df_loaded_ok(df_B) else ["PANEL VAN"]))
    gvw_input = st.selectbox("GVW (opzionale, contesto)", options=(sorted(df_A["gvw"].unique()) if df_loaded_ok(df_A) else ["3500"]))
    engine_digit_input = st.text_input("Engine digit (opzionale, es. 5)", value="")

    col2 = st.columns([1])[0]
    with col2:
        st.write("Carica opts.csv (opzionale)")
        uploaded_opts = st.file_uploader("Carica opts.csv (se vuoi testare file custom)", type=["csv"])
        if uploaded_opts is not None:
            try:
                df_opts = pd.read_csv(uploaded_opts, dtype=str).fillna("")
                st.success("opts.csv caricato per questa sessione")
            except Exception as e:
                st.error(f"Errore caricamento opts: {e}")

    if st.button("Verifica OPT per sigla generata"):
        sigla = sigla_generated
        engine_digit = engine_digit_input.strip() if engine_digit_input.strip() else None
        opts_list = get_opts_for_config(sigla, engine_digit, body_input, gvw_input)
        st.subheader("OPT trovati")
        if not opts_list:
            st.info("Nessun OPT disponibile (controlla opts.csv o la sigla).")
        else:
            for o in opts_list:
                state = o["state"]
                color = "green" if state=="SERIE" else ("orange" if state=="OPZIONALE" else "red")
                st.markdown(f"- **{o['opt_code']}** {o['opt_descr']} — <span style='color:{color}'>{state}</span>", unsafe_allow_html=True)

        st.subheader("Controllo vincoli (simulazione selezione)")
        selectable = [o for o in opts_list if o["state"] != "NON_DISP"]
        codes = [o["opt_code"] for o in selectable]
        selected = st.multiselect("Seleziona OPT per testare i vincoli", options=codes)
        conflicts = check_constraints(selected, sigla, engine_digit, body_input, gvw_input)
        if conflicts:
            st.error("Conflitti rilevati:")
            for c in conflicts:
                st.write(f"- {c}")
        else:
            st.success("Nessun conflitto rilevato per la selezione corrente.")

# -------------------------
# Footer: informazioni file caricati (riassunto)
# -------------------------
st.sidebar.markdown("---")
st.sidebar.write("Stato file (caricati e non vuoti):")
st.sidebar.write({
    "decode A": df_loaded_ok(df_A),
    "decode B": df_loaded_ok(df_B),
    "decode n": df_loaded_ok(df_N),
    "level1": df_loaded_ok(df_level1),
    "opts": df_loaded_ok(df_opts),
    "constraints": df_loaded_ok(df_constraints)
})
