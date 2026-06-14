# app.py
# Configuratore ITPL + OPT Checker (Streamlit)
# Requisiti: streamlit, pandas
# Posiziona i CSV nella stessa cartella di app.py:
# - decode_sincom_A.csv (sep=';')
# - decode_sincom_B.csv (sep=';')
# - decode_sincom_n.csv (sep=';')
# - level1_extracted.csv (sigla_base,body_label,sevel,gliwice,notes)
# - opts.csv (opt_code,opt_descr,default_state,availability_rules,notes)
# - constraints.csv (constraint_type,subject,target,condition,notes)
#
# Avvio: streamlit run app.py

import streamlit as st
import pandas as pd
import os

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
# Utility: caricamento CSV
# -------------------------
def load_csv(path, sep=",", encoding="utf-8"):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, sep=sep, dtype=str, encoding=encoding).fillna("")
            return df
        except Exception as e:
            st.error(f"Errore caricamento {path}: {e}")
            return None
    else:
        return None

# Carica decode
df_A = load_csv(A_PATH, sep=";")
df_B = load_csv(B_PATH, sep=";")
df_N = load_csv(N_PATH, sep=";")

# Carica level1, opts, constraints
df_level1 = load_csv(LEVEL1_PATH, sep=",")
df_opts = load_csv(OPTS_PATH, sep=",")
df_constraints = load_csv(CONSTRAINTS_PATH, sep=",")

# -------------------------
# Normalizzazione decode (se necessario)
# -------------------------
def normalize_A(df):
    if df is None:
        return None
    cols = list(df.columns)
    if len(cols) >= 4:
        df = df.iloc[:, :4]
        df.columns = ["model_code","gvw","length_code","output_symbol"]
    else:
        # fallback: try to keep as-is
        df.columns = [c.strip() for c in df.columns]
    df["model_code"] = df["model_code"].astype(str).str.strip()
    df["gvw"] = df["gvw"].astype(str).str.strip()
    df["length_code"] = df["length_code"].astype(str).str.strip()
    df["output_symbol"] = df["output_symbol"].astype(str).str.strip()
    return df

def normalize_B(df):
    if df is None:
        return None
    cols = list(df.columns)
    if len(cols) >= 3:
        df = df.iloc[:, :3]
        df.columns = ["height_code","body_label","output_symbol"]
    df["height_code"] = df["height_code"].astype(str).str.strip()
    df["body_label"] = df["body_label"].astype(str).str.strip()
    df["output_symbol"] = df["output_symbol"].astype(str).str.strip()
    return df

def normalize_N(df):
    if df is None:
        return None
    cols = list(df.columns)
    if len(cols) >= 4:
        df = df.iloc[:, :4]
        df.columns = ["engine_family","engine_full_label","short_label","engine_digit"]
    df["engine_family"] = df["engine_family"].astype(str).str.strip()
    df["engine_full_label"] = df["engine_full_label"].astype(str).str.strip()
    df["short_label"] = df["short_label"].astype(str).str.strip()
    df["engine_digit"] = df["engine_digit"].astype(str).str.strip()
    return df

df_A = normalize_A(df_A)
df_B = normalize_B(df_B)
df_N = normalize_N(df_N)

# -------------------------
# Funzioni di decode: costruzione sigla
# -------------------------
def find_A_symbol(model_code, gvw, length_code):
    if df_A is None:
        return None
    # match esatto su model_code + gvw + length_code
    q = df_A[
        (df_A["model_code"] == str(model_code)) &
        (df_A["gvw"] == str(gvw)) &
        (df_A["length_code"] == str(length_code))
    ]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    # fallback: model_code + length_code
    q = df_A[
        (df_A["model_code"] == str(model_code)) &
        (df_A["length_code"] == str(length_code))
    ]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    # fallback: model_code only
    q = df_A[df_A["model_code"] == str(model_code)]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    return None

def find_B_symbol(height_code, body_label):
    if df_B is None:
        return None
    # match su height_code e body_label (contains)
    q = df_B[
        (df_B["height_code"] == str(height_code)) &
        (df_B["body_label"].str.upper().str.contains(str(body_label).upper(), na=False))
    ]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    # fallback su height_code solo
    q = df_B[df_B["height_code"] == str(height_code)]
    if not q.empty:
        return q.iloc[0]["output_symbol"]
    return None

def find_engine_digit(engine_query):
    if df_N is None:
        return None
    # cerca per short_label esatto o contenuto, poi per engine_family
    q = df_N[
        (df_N["short_label"].str.contains(str(engine_query), na=False)) |
        (df_N["engine_family"].str.contains(str(engine_query), na=False))
    ]
    if not q.empty:
        return q.iloc[0]["engine_digit"]
    return None

# -------------------------
# Caricamento e lookup producibilità (level1)
# -------------------------
def load_level1_df(df):
    if df is None:
        return None
    # assicurati colonne corrette
    cols = list(df.columns)
    if len(cols) >= 5 and cols[:5] != ["sigla_base","body_label","sevel","gliwice","notes"]:
        # prova a rinominare le prime 5 colonne
        df = df.rename(columns={cols[0]:"sigla_base", cols[1]:"body_label", cols[2]:"sevel", cols[3]:"gliwice", cols[4]:"notes"})
    # normalizza flags
    if "sevel" in df.columns:
        df["sevel"] = df["sevel"].astype(str).str.strip().replace({"":"0","-":"0"})
        df["sevel"] = df["sevel"].apply(lambda x: "1" if x not in ("0","", "0.0") else "0")
    if "gliwice" in df.columns:
        df["gliwice"] = df["gliwice"].astype(str).str.strip().replace({"":"0","-":"0"})
        df["gliwice"] = df["gliwice"].apply(lambda x: "1" if x not in ("0","", "0.0") else "0")
    return df

df_level1 = load_level1_df(df_level1)

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
# Parser regole e OPT (sicuro, senza eval)
# -------------------------
def parse_gvw_int(value):
    if not value:
        return None
    s = str(value).lower().replace("kg","").strip()
    try:
        return int(s)
    except:
        # prova a estrarre numero
        import re
        m = re.search(r"\d+", s)
        if m:
            return int(m.group())
    return None

def eval_rules(rule_str, context):
    """
    rule_str: stringa tipo "sigla_prefix=AG;engine_digit_in=5,6;gvw_le=3500"
    context: dict con chiavi: sigla, engine_digit, body_label, gvw (int), model_code, length_code, height_code
    """
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
            # chiave non riconosciuta -> per sicurezza fallisce
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
# UI: modalità (switch)
# -------------------------
mode = st.sidebar.radio("Modalità", ["Verifica OPT", "Configura ordine"])

# -------------------------
# Modalità: Verifica OPT
# -------------------------
if mode == "Verifica OPT":
    st.header("Verifica OPT")
    st.markdown("Inserisci la sigla completa (es. AG5) o carica una configurazione per verificare lo stato degli OPT.")

    col1, col2 = st.columns([2,1])
    with col1:
        sigla_input = st.text_input("Sigla completa (es. AG5)", value="")
        body_input = st.text_input("Body (opzionale, es. PANEL VAN)", value="")
        gvw_input = st.text_input("GVW (opzionale, es. 3500)", value="")
        engine_digit_input = st.text_input("Engine digit (opzionale, es. 5)", value="")
    with col2:
        st.write("Carica CSV OPT (opzionale)")
        uploaded_opts = st.file_uploader("Carica opts.csv (se vuoi testare file custom)", type=["csv"])
        if uploaded_opts is not None:
            try:
                df_opts = pd.read_csv(uploaded_opts, dtype=str).fillna("")
                st.success("opts.csv caricato per questa sessione")
            except Exception as e:
                st.error(f"Errore caricamento opts: {e}")

    if st.button("Verifica"):
        if not sigla_input:
            st.error("Inserisci una sigla per procedere.")
        else:
            sigla = sigla_input.strip().upper()
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
            # permetti all'utente di selezionare alcuni OPT per testare i vincoli
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
# Modalità: Configura ordine
# -------------------------
else:
    st.header("Configura ordine ITPL")
    st.markdown("Costruisci la configurazione passo passo. Il sistema genera la sigla e verifica la producibilità in Sevel/Gliwice.")

    # Se possibile, popola le select con valori noti
    model_options = sorted(df_A["model_code"].unique()) if df_A is not None else ["290/252","295/254"]
    length_options = sorted(df_A["length_code"].unique()) if df_A is not None else ["L2","L3","L4","L2+","L0"]
    height_options = sorted(df_B["height_code"].unique()) if df_B is not None else ["H1","H2","H3"]
    engine_options = df_N["short_label"].unique().tolist() if df_N is not None else ["140HP","180HP"]

    col1, col2, col3 = st.columns(3)
    with col1:
        model_code = st.selectbox("Model / Gamma", options=model_options)
        gvw = st.text_input("GVW / PTT (es. 3500 o >3500)", value="")
        length_code = st.selectbox("Passo / Lunghezza", options=length_options)
    with col2:
        height_code = st.selectbox("Altezza", options=height_options)
        body_label = st.text_input("Body / Version (es. PANEL VAN)", value="PANEL VAN")
    with col3:
        engine_query = st.selectbox("Motore / Cambio (seleziona)", options=engine_options)
        st.write("Seleziona motore e cambio per ottenere il digit della sigla.")

    if st.button("Genera sigla e verifica producibilità"):
        A = find_A_symbol(model_code, gvw, length_code)
        B = find_B_symbol(height_code, body_label)
        n = find_engine_digit(engine_query)

        if not A or not B or not n:
            st.error(f"Impossibile generare sigla completa. A={A}, B={B}, n={n}")
            # mostra suggerimenti diagnostici
            if not A:
                st.info("Controlla mapping A (model/gvw/length).")
            if not B:
                st.info("Controlla mapping B (height/body).")
            if not n:
                st.info("Controlla mapping motore/cambio (file decode_sincom_n.csv).")
        else:
            sigla = f"{A}{B}{n}"
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

                    # Mostra OPT (base) per questa configurazione (senza editing avanzato)
                    st.markdown("---")
                    st.subheader("OPT (stato base)")
                    opts_list = get_opts_for_config(sigla, n, body_label, gvw)
                    if not opts_list:
                        st.info("Nessun OPT trovato (controlla opts.csv).")
                    else:
                        # tabella riassuntiva
                        df_opts_view = pd.DataFrame(opts_list)
                        df_opts_view = df_opts_view[["opt_code","opt_descr","state"]]
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

                    # Riepilogo ordine (testo pronto per copia)
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
                        f"Plant scelto: {chosen_plant}"
                    ]
                    if selected_opts:
                        riepilogo.append("OPT selezionati: " + ", ".join(selected_opts))
                    riepilogo_text = "\n".join(riepilogo)
                    st.code(riepilogo_text, language="text")
                    st.button("Copia riepilogo (usa clipboard del browser)")

                else:
                    st.warning("Questa configurazione non è producibile in nessuno dei due plant.")
                    st.info("Modifica le scelte per trovare una combinazione producibile.")

# -------------------------
# Footer: informazioni file caricati
# -------------------------
st.sidebar.markdown("---")
st.sidebar.write("Dati caricati:")
st.sidebar.write({
    "decode A": bool(df_A),
    "decode B": bool(df_B),
    "decode n": bool(df_N),
    "level1": bool(df_level1),
    "opts": bool(df_opts),
    "constraints": bool(df_constraints)
})
