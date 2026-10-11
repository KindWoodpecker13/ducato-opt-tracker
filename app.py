import streamlit as st
import pandas as pd
import os
import re
import html

# ---------------------------------------------------------
# MOTORE DI REGOLE MUST HAVE / INCOMPATIBILITÀ
# ---------------------------------------------------------
# Parole che segnalano una condizione testuale (scope) legata a gamma,
# motorizzazione, allestimento ecc. Se compaiono nella cella, la regola
# NON viene applicata in automatico ma segnalata per verifica manuale.
RULE_STOPWORDS = {
    "on", "for", "except", "su", "per", "tranne", "range", "all", "gamma",
    "euro", "bev", "ice", "hydrogen", "hybrid", "camper", "van", "cab",
    "chassis", "panel", "net", "rv", "tl", "pl", "pl8", "glazed", "toyota",
    "rete", "retail", "motor", "special", "half", "furgoni", "furgone",
    "lastrati", "lastrato", "vetrati", "vetrato", "fiancata", "mista",
    "semivetrato", "cassonato", "cassonati", "scudati", "cabinati",
    "cabinato", "the", "of", "without", "solo", "only",
}

def classify_rule(raw_text):
    """Ritorna (stato, testo) dove stato in {NONE, AUTO, MANUAL}."""
    if pd.isna(raw_text):
        return "NONE", ""
    text = str(raw_text).strip()
    low = text.lower()
    if not text or low.startswith("nessun"):
        return "NONE", ""
    words = re.findall(r"[A-Za-zÀ-ÿ]+", low)
    if any(w in RULE_STOPWORDS for w in words):
        return "MANUAL", text
    return "AUTO", text

def parse_or_groups(text):
    """'[A + B] or [C + D]' -> [[A,B],[C,D]]  (soddisfatta se un gruppo è tutto presente)."""
    groups_raw = re.findall(r"\[([^\]]*)\]", text)
    if not groups_raw:
        groups_raw = [text]
    groups = []
    for g in groups_raw:
        codes = [c.strip().upper() for c in re.split(r"\+", g) if c.strip()]
        if codes:
            groups.append(codes)
    return groups

def parse_forbidden_list(text):
    """'[A - B - C]' -> [A, B, C] (lista piatta di codici incompatibili)."""
    groups_raw = re.findall(r"\[([^\]]*)\]", text)
    if not groups_raw:
        groups_raw = [text]
    codes = []
    for g in groups_raw:
        for c in re.split(r"[-,]", g):
            c = c.strip().upper()
            if c:
                codes.append(c)
    return codes

def norm_code(c):
    return str(c).strip().upper().zfill(3)

def build_must_have_dict(df):
    d = {}
    for _, row in df.iterrows():
        code = norm_code(row.iloc[0])
        status, text = classify_rule(row.iloc[1])
        if status == "NONE":
            d[code] = {"status": "NONE"}
        elif status == "MANUAL":
            d[code] = {"status": "MANUAL", "raw": text}
        else:
            groups = [[norm_code(c) for c in g] for g in parse_or_groups(text)]
            d[code] = {"status": "AUTO", "groups": groups}
    return d

def build_incompat_dict(df):
    d = {}
    for _, row in df.iterrows():
        code = norm_code(row.iloc[0])
        status, text = classify_rule(row.iloc[1])
        if status == "NONE":
            d[code] = {"status": "NONE"}
        elif status == "MANUAL":
            d[code] = {"status": "MANUAL", "raw": text}
        else:
            forbidden = [norm_code(c) for c in parse_forbidden_list(text)]
            d[code] = {"status": "AUTO", "forbidden": forbidden}
    return d

def analyze_order(vehicle_codes, must_have_dict, incompat_dict):
    """Applica must-have (auto, non ambigui) e incompatibilità (auto) alla lista di codici.
    Ritorna (codici_finali_in_ordine, report_dict)."""
    ordered = list(dict.fromkeys(vehicle_codes))  # dedup mantenendo l'ordine
    current_set = set(ordered)

    report = {
        "must_have_ok": [],
        "must_have_added": [],
        "must_have_choice_needed": [],
        "must_have_manual": [],
        "must_have_unknown": [],
        "incompat_conflicts": [],
        "incompat_manual": [],
        "incompat_unknown": [],
    }

    # --- MUST HAVE: aggiunta automatica solo se non ambigua (un solo gruppo) ---
    for code in ordered:
        rule = must_have_dict.get(code)
        if rule is None:
            report["must_have_unknown"].append(code)
            continue
        if rule["status"] == "NONE":
            continue
        if rule["status"] == "MANUAL":
            report["must_have_manual"].append((code, rule["raw"]))
            continue
        groups = rule["groups"]
        satisfied = any(all(c in current_set for c in g) for g in groups)
        if satisfied:
            report["must_have_ok"].append(code)
        elif len(groups) == 1:
            missing = [c for c in groups[0] if c not in current_set]
            for m in missing:
                if m not in current_set:
                    ordered.append(m)
                    current_set.add(m)
            report["must_have_added"].append((code, missing))
        else:
            report["must_have_choice_needed"].append((code, groups))

    # --- INCOMPATIBILITÀ: rimozione automatica, vince il codice inserito prima ---
    kept = []
    kept_set = set()
    for code in ordered:
        rule = incompat_dict.get(code)
        conflict_with = None
        if rule is not None and rule["status"] == "AUTO":
            for forbidden_code in rule["forbidden"]:
                if forbidden_code in kept_set:
                    conflict_with = forbidden_code
                    break
        if conflict_with:
            report["incompat_conflicts"].append((code, conflict_with))
            continue  # codice scartato: incompatibile con uno già tenuto
        if rule is None:
            report["incompat_unknown"].append(code)
        elif rule["status"] == "MANUAL":
            report["incompat_manual"].append((code, rule["raw"]))
        kept.append(code)
        kept_set.add(code)

    return kept, report

# ---------------------------------------------------------
# TABELLONE OPT PER SINCOM (S = Serie, O = Optional, ND = Non disponibile)
# ---------------------------------------------------------
TABELLONE_FILENAME = "TABELLONE_OPT.csv"
OPT_DESCR_FILENAME = "griglia_prodotto.csv"

def normalize_sincom(text):
    """Normalizza un SINCOM completo nella chiave 'MODELLO.ABn.SERIE.GUIDA.MERCATO'.

    Accetta sia l'ordine del tabellone (serie.guida.mercato) sia quello generato dal
    Configuratore (serie.mercato.guida): guida = 2 caratteri, mercato = 3 caratteri,
    quindi i due campi si distinguono dalla lunghezza.
    Tollera anche la forma con punto mancante tra guida e mercato (es. '02250').
    Ritorna (chiave, errore): se la stringa non è interpretabile, chiave è None.
    """
    if text is None:
        return None, "SINCOM vuoto."
    raw = re.sub(r"\s+", "", str(text)).upper()
    if not raw:
        return None, "SINCOM vuoto."
    tokens = [t for t in raw.split(".") if t != ""]

    # forma con punto mancante: ultimo campo di 5 caratteri = guida (2) + mercato (3)
    if len(tokens) == 4 and len(tokens[3]) == 5:
        tokens = tokens[:3] + [tokens[3][:2], tokens[3][2:]]

    if len(tokens) != 5:
        return None, (
            "Formato non riconosciuto: attesi 5 campi separati da punto "
            "(modello.ABn.serie.guida.mercato, es. 290.ALD.2.01.000)."
        )
    modello, abn, serie, t4, t5 = tokens
    if len(modello) != 3 or len(abn) != 3:
        return None, "Modello e sigla ABn devono essere di 3 caratteri ciascuno."

    campi = [t4, t5]
    guida = next((t for t in campi if len(t) == 2), None)
    mercato = next((t for t in campi if len(t) == 3), None)
    if guida is None or mercato is None:
        return None, "Guida (2 cifre, es. 01) e mercato (3 cifre, es. 000) non riconosciuti."
    return f"{modello}.{abn}.{serie}.{guida}.{mercato}", None

def build_tabellone(df):
    """Da DataFrame grezzo del tabellone a (DataFrame indicizzato per SINCOM normalizzato, avvisi)."""
    avvisi = []
    df = df.copy()
    df.columns = [str(c).strip().rstrip(".").upper() for c in df.columns]
    if "SINCOM" not in df.columns:
        raise ValueError("Colonna 'SINCOM' non trovata nel tabellone.")

    dup_cols = [c for c in df.columns[df.columns.duplicated()].unique()]
    if dup_cols:
        avvisi.append(f"Colonne OPT duplicate nel tabellone (tenuta la prima): {', '.join(dup_cols)}")
        df = df.loc[:, ~df.columns.duplicated()]

    keys, bad_rows = [], []
    for raw in df["SINCOM"]:
        key, err = normalize_sincom(raw)
        keys.append(key)
        if key is None:
            bad_rows.append(str(raw))
    df["_KEY"] = keys
    if bad_rows:
        avvisi.append(f"{len(bad_rows)} righe con SINCOM non interpretabile ignorate: {', '.join(bad_rows[:5])}")
        df = df[df["_KEY"].notna()]

    dup_rows = df["_KEY"].duplicated().sum()
    if dup_rows:
        avvisi.append(f"{dup_rows} righe con SINCOM duplicato: tenuta la prima occorrenza.")
        df = df.drop_duplicates(subset="_KEY", keep="first")

    df = df.set_index("_KEY").drop(columns=["SINCOM"])
    df.columns = [norm_code(c) for c in df.columns]
    df = df.apply(lambda col: col.astype("string").str.strip().str.upper())
    return df, avvisi

@st.cache_data(show_spinner=False)
def load_tabellone(path, mtime):
    """Carica il tabellone (mtime serve solo a invalidare la cache se il file cambia)."""
    try:
        raw = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        raw = pd.read_csv(path, sep=";", dtype=str, encoding="latin-1")
    return build_tabellone(raw)

@st.cache_data(show_spinner=False)
def load_opt_descriptions(path, mtime):
    """Dizionario codice -> descrizione italiana, dal file griglia_prodotto.csv."""
    raw = pd.read_csv(path, header=None, sep=";", dtype=str, encoding="utf-8", engine="python")
    raw = raw.rename(columns={0: "descr_it", 1: "descr_en", 2: "code"})
    raw["code"] = raw["code"].apply(norm_code)
    raw["descr_it"] = raw["descr_it"].astype(str).str.strip()
    raw = raw.drop_duplicates(subset=["code"])
    return dict(zip(raw["code"], raw["descr_it"]))

def split_availability(row):
    """Divide una riga del tabellone in liste ordinate di codici S / O / ND (+ valori anomali)."""
    out = {"S": [], "O": [], "ND": [], "ALTRO": []}
    for code, val in row.items():
        v = "" if pd.isna(val) else str(val)
        out[v if v in ("S", "O", "ND") else "ALTRO"].append(code)
    for k in out:
        out[k].sort()
    return out

def render_opt_column(title, color, codes, descr, filtro):
    """HTML di una colonna (card colorata con elenco scorrevole di codice + descrizione)."""
    items = []
    for c in codes:
        d = descr.get(c, "")
        if filtro and filtro not in c.lower() and filtro not in d.lower():
            continue
        d_html = html.escape(d) if d else "<i>descrizione non presente in griglia</i>"
        items.append(
            f"<div style='padding:7px 0; border-bottom:1px solid rgba(255,255,255,0.08); font-size:13px; color:#e2e8f0;'>"
            f"<b style='color:{color}; font-size:14px;'>{html.escape(c)}</b> — {d_html}</div>"
        )
    body = "".join(items) if items else "<div style='color:#94a3b8; font-size:13px; padding:8px 0;'>Nessun codice</div>"
    return (
        f"<div style='background: rgba(255,255,255,0.05); border:1px solid {color}; "
        f"border-top:5px solid {color}; border-radius:14px; padding:16px 18px;'>"
        f"<div style='font-size:18px; font-weight:800; color:{color};'>{title} "
        f"<span style='font-size:14px; font-weight:600; color:#cbd5e1;'>({len(items)})</span></div>"
        f"<div style='max-height:620px; overflow-y:auto; margin-top:10px; padding-right:6px;'>{body}</div>"
        f"</div>"
    )

# ---------------------------------------------------------
# CONFIGURAZIONE PAGINA & GRAFICA AVANZATA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ducato ITPL Toolbox", 
    page_icon="🚐", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# STILE CSS PERSONALIZZATO PER INTERFACCIA PREMIUM
st.markdown(
    """
    <style>
    /* Reset e Sfondo Blu Profondo Sfumato */
    html, body, .stApp {
        background: none !important;
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        background: linear-gradient(135deg, #071426 0%, #0c203b 40%, #172d54 80%, #25447b 100%);
        z-index: -999;
    }
    
    /* Pulizia container Streamlit */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Stile personalizzato per i Tab */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255, 255, 255, 0.05);
        padding: 8px 12px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre;
        background-color: transparent;
        border-radius: 8px;
        color: #cbd5e1 !important;
        font-weight: 600;
        padding: 0px 20px;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4f7bd6 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(79, 123, 214, 0.3);
    }

    /* Card custom per i risultati */
    .custom-card {
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        transition: transform 0.2s ease;
    }
    .custom-card:hover {
        transform: translateY(-2px);
    }

    /* Card per il codice SINCOM completo (hero) */
    .hero-card {
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 28px;
        text-align: center;
    }
    
    /* Box per gli OPT del Checker */
    .opt-box {
        padding: 10px 14px; 
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.1); 
        border-radius: 8px; 
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    /* Input e Form Styling */
    .stSelectbox label, .stTextArea label {
        color: #e2e8f0 !important;
        font-weight: 500 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# HEADER DELL'APPLICAZIONE
# ---------------------------------------------------------
st.title("Ducato ITPL Toolbox 🚐")
st.write("Piattaforma integrata per la validazione dei codici d'ordine e decodifica rapida degli OPT.")
st.markdown("---")

# Caricamento regole Must Have / Incompatibilità (SL e E7), indipendente dai tab
def _read_rules_csv(path):
    try:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", dtype=str, encoding="latin-1")

rules_ready = True
rules_error = None
try:
    mh_sl_raw = _read_rules_csv("must_have_SL.csv")
    mh_e7_raw = _read_rules_csv("must_have_E7.csv")
    inc_sl_raw = _read_rules_csv("incompatibilita_SL.csv")
    inc_e7_raw = _read_rules_csv("incompatibilita_E7.csv")

    MUST_HAVE = {
        "2": build_must_have_dict(mh_sl_raw),   # Serial Life
        "3": build_must_have_dict(mh_e7_raw),   # €7 / MY28
    }
    INCOMPAT = {
        "2": build_incompat_dict(inc_sl_raw),
        "3": build_incompat_dict(inc_e7_raw),
    }
except Exception as e:
    rules_ready = False
    rules_error = e

# Valore di default per evitare NameError se il Tab 1 non ha ancora girato/fallito
serie_sel = None
# SINCOM completo generato nel Tab 1 (serve a precompilare il campo del Tab 3)
sincom_from_tab1 = None

# Definizione dei Tab principali
tab1, tab2, tab3, tab4 = st.tabs([
    "🎛️ Configuratore SINCOM & Plant",
    "🔬 Checker OPT Avanzato",
    "📊 Verifica OPT in base a SINCOM",
    "✅ Verifica Ordine (Must Have & Incompatibilità)",
])

# =========================================================
# TAB 1: CONFIGURATORE SINCOM & PLANT CHECKER
# =========================================================
with tab1:
    st.subheader("Configurazione Guidata del Veicolo")
    st.write("Seleziona i vincoli tecnici per comporre il codice SINCOM completo e verificarne il Plant di produzione.")
    
    # Tentativo di caricamento di tutti i CSV di configurazione
    try:
        df_model = pd.read_csv("decode_model.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())

        df_a = pd.read_csv("decode_sincom_A.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        df_b = pd.read_csv("decode_sincom_B.csv", sep=";", dtype=str)
        df_b["ALTEZZA"] = df_b["ALTEZZA"].fillna("").astype(str).str.strip()
        df_b["BODY"] = df_b["BODY"].fillna("").astype(str).str.strip()
        
        df_n = pd.read_csv("decode_sincom_n.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        
        # Caricamento del file di 1° livello con la mappatura reale dei plant
        df_1lev = pd.read_csv("decode_1°lev.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        db_ready = True
    except Exception as e:
        st.error(f"⚠️ Errore nel caricamento dei CSV del configuratore: {e}")
        st.info("Verifica che i file siano nominati correttamente e usino il punto e virgola ';' come separatore.")
        db_ready = False

    if db_ready:
        st.markdown("### 🎚️ Seleziona Parametri Griglia Prodotto")
        
        # Griglia a 3 colonne per gli Step di configurazione
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### 📐 Struttura (Lettera A)")

            marche_disponibili = sorted(df_model["MARCA"].unique())
            marca_sel = st.selectbox("Marca", marche_disponibili, key="cfg_marca")

            portate_disponibili = sorted(df_a["PORTATA"].unique())
            portata_sel = st.selectbox("Portata", portate_disponibili, key="cfg_portata")
            
            df_a_f1 = df_a[df_a["PORTATA"] == portata_sel]
            pesi_disponibili = sorted(df_a_f1["PESO"].unique())
            peso_sel = st.selectbox("Peso (GVW)", pesi_disponibili, key="cfg_peso")
            
            df_a_f2 = df_a_f1[df_a_f1["PESO"] == peso_sel]
            lunghezze_disponibili = sorted(df_a_f2["LUNGHEZZA"].unique())
            lunghezza_sel = st.selectbox("Lunghezza (Passo)", lunghezze_disponibili, key="cfg_lunghezza")
            
            res_a = df_a_f2[df_a_f2["LUNGHEZZA"] == lunghezza_sel]
            lettera_A = res_a["SIGLA_A"].values[0] if not res_a.empty else None

        with col2:
            st.markdown("#### 🚐 Allestimento (Lettera B)")
            body_disponibili = sorted(df_b["BODY"].unique())
            body_sel = st.selectbox("Tipologia Body", body_disponibili, key="cfg_body")
            
            df_b_f1 = df_b[df_b["BODY"] == body_sel]
            altezze_disponibili = df_b_f1["ALTEZZA"].unique()
            altezze_labels = [h if h != "" else "Standard / Non Specificato" for h in altezze_disponibili]
            
            altezza_sel_label = st.selectbox("Altezza Sagoma", altezze_labels, key="cfg_altezza")
            altezza_sel = "" if altezza_sel_label == "Standard / Non Specificato" else altezza_sel_label
            
            res_b = df_b_f1[df_b_f1["ALTEZZA"] == altezza_sel]
            lettera_B = res_b["CODICE_B"].values[0] if not res_b.empty else None

        with col3:
            st.markdown("#### ⚙️ Motore & Cambio (Numero n)")
            motori_disponibili = sorted(df_n["MOTORE"].unique())
            motore_sel = st.selectbox("Alimentazione", motori_disponibili, key="cfg_motore")
            
            df_n_f1 = df_n[df_n["MOTORE"] == motore_sel]
            potenze_disponibili = sorted(df_n_f1["MOTORIZZAZIONE"].unique())
            potenza_sel = st.selectbox("Motorizzazione & Emissioni", potenze_disponibili, key="cfg_potenza")
            
            df_n_f2 = df_n_f1[df_n_f1["MOTORIZZAZIONE"] == potenza_sel]
            cambi_disponibili = sorted(df_n_f2["CAMBIO"].unique())
            cambio_sel = st.selectbox("Trasmissione", cambi_disponibili, key="cfg_cambio")
            
            res_n = df_n_f2[df_n_f2["CAMBIO"] == cambio_sel]
            carattere_n = res_n["SIGLA_n"].values[0] if not res_n.empty else None

        st.markdown("---")
        st.markdown("### 🏷️ Parametri Aggiuntivi Codice d'Ordine")

        col4, col5, col6 = st.columns(3)

        with col4:
            serie_options = {"Serial Life": "2", "€7 o MY28": "3"}
            serie_label = st.selectbox("Numero di Serie", list(serie_options.keys()), key="cfg_serie")
            serie_sel = serie_options[serie_label]

        with col5:
            mercato_options = {"Europa": "000", "UK o Giappone": "870"}
            mercato_label = st.selectbox("Mercato", list(mercato_options.keys()), key="cfg_mercato")
            mercato_sel = mercato_options[mercato_label]

        with col6:
            guida_options = {"Sinistra (SX)": "01", "Destra (DX)": "02"}
            guida_label = st.selectbox("Posizione di Guida", list(guida_options.keys()), key="cfg_guida")
            guida_sel = guida_options[guida_label]

        # ---------------------------------------------------------
        # ELABORAZIONE LOGICA DETTAGLIATA REALE DEI PLANT
        # ---------------------------------------------------------
        st.markdown("---")
        st.markdown("### 📋 Analisi di Fattibilità Industriale")
        
        if lettera_A and lettera_B and carattere_n:
            sincom_generato = f"{lettera_A}{lettera_B}{carattere_n}".upper()

            # Ricerca del codice modello (3 cifre) incrociando Marca, Portata e Alimentazione
            match_model = df_model[
                (df_model["MARCA"] == marca_sel) & (df_model["ALIMENTAZIONE"] == motore_sel)
            ]
            if len(match_model) > 1:
                match_model = match_model[match_model["PORTATA"] == portata_sel]
            codice_modello = match_model["LOGISTIC_MODEL"].values[0] if not match_model.empty else None

            if codice_modello:
                sincom_completo = f"{codice_modello}.{sincom_generato}.{serie_sel}.{mercato_sel}.{guida_sel}"
            else:
                sincom_completo = None
            sincom_from_tab1 = sincom_completo

            producibile_sevel = False
            producibile_gliwice = False
            codice_mappato = False
            
            # Controllo di lookup basato sulla corrispondenza esatta dell'indice SINCOM
            if "SINCOM" in df_1lev.columns and "SEVEL" in df_1lev.columns and "GLIWICE" in df_1lev.columns:
                match_sincom = df_1lev[df_1lev["SINCOM"] == sincom_generato]
                
                if not match_sincom.empty:
                    codice_mappato = True
                    prod_sevel = match_sincom["SEVEL"].values[0].strip().upper()
                    prod_gliwice = match_sincom["GLIWICE"].values[0].strip().upper()
                    
                    if prod_sevel == "SI": producibile_sevel = True
                    if prod_gliwice == "SI": producibile_gliwice = True
            
            # Determinazione dell'output visivo in base al matricione reale delle celle
            if codice_mappato:
                if producibile_sevel and producibile_gliwice:
                    plant_text = "CO-PRODUCTION<br><span style='font-size:16px;'>Sevel (IT) & Gliwice (PL)</span>"
                    plant_color = "#28a745" # Verde successo speculare
                elif producibile_sevel:
                    plant_text = "SEVEL<br><span style='font-size:16px;'>Val di Sangro (Italia)</span>"
                    plant_color = "#21c35a" # Verde stabilimento Sevel
                elif producibile_gliwice:
                    plant_text = "GLIWICE<br><span style='font-size:16px;'>Gliwice (Polonia)</span>"
                    plant_color = "#4f7bd6" # Blu Stellantis
                else:
                    plant_text = "NON PRODUCIBILE<br><span style='font-size:16px;'>Escluso dai Sistemi di Produzione</span>"
                    plant_color = "#ff4b4b" # Rosso Bloccato
            else:
                plant_text = "NON IN MATRICE<br><span style='font-size:16px;'>Combinazione Teorica Non Esistente</span>"
                plant_color = "#ff4b4b"

            # Card hero con il codice SINCOM completo
            if sincom_completo:
                st.markdown(
                    f"""
                    <div class="hero-card" style="border-top: 5px solid #21c35a;">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">CODICE SINCOM COMPLETO</span>
                        <div style="font-size: 46px; font-weight: 800; color: #ffffff; margin: 14px 0; letter-spacing: 2px;">{sincom_completo}</div>
                        <span style="background: rgba(33, 195, 90, 0.15); color: #86efac; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600;">
                            Modello: {codice_modello} | ABn: {sincom_generato} | Serie: {serie_sel} | Mercato: {mercato_sel} | Guida: {guida_sel}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.error("⚠️ Nessuna corrispondenza trovata in 'decode_model.csv' per la combinazione Marca / Portata / Alimentazione selezionata. Impossibile generare il codice modello (3 cifre).")

            st.markdown("")

            # Interfaccia Output Grafica Elegante (dettaglio ABn + Plant)
            out_col1, out_col2 = st.columns(2)
            
            with out_col1:
                st.markdown(
                    f"""
                    <div class="custom-card" style="border-top: 5px solid #4f7bd6;">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">SIGLA ABn</span>
                        <div style="font-size: 54px; font-weight: 800; color: #ffffff; margin: 12px 0; letter-spacing: 4px;">{sincom_generato}</div>
                        <span style="background: rgba(79, 123, 214, 0.15); color: #93c5fd; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600;">
                            Struttura: {lettera_A} | Allestimento: {lettera_B} | Motore: {carattere_n}
                        </span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
            with out_col2:
                st.markdown(
                    f"""
                    <div class="custom-card" style="border-top: 5px solid {plant_color};">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">ALLOCAZIONE STABILIMENTO</span>
                        <div style="font-size: 32px; font-weight: 800; color: {plant_color}; margin: 18px 0; line-height: 1.2;">{plant_text}</div>
                        <span style="color: #94a3b8; font-size: 12px;">Validato incrociando il database di 1° Livello</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
            # Preview della feature futura per la Griglia OPT di serie/optional
            st.markdown("---")
            st.info("📊 Per vedere gli OPT di serie, optional e non disponibili di questa configurazione apri il tab **Verifica OPT in base a SINCOM**: il campo viene precompilato con il codice SINCOM completo generato qui sopra.")
        else:
            st.error("Combinazione incompleta. Assicurati che tutti i menù a tendina abbiano un valore valido selezionato.")

# =========================================================
# TAB 2: CHECKER OPT (IL TUO STRUMENTO OTTIMIZZATO)
# =========================================================
with tab2:
    CSV_FILENAME = "griglia_prodotto.csv"
    st.subheader("Decodificatore Istantaneo Stringhe OPT")
    
    df_opt = None
    if os.path.exists(CSV_FILENAME):
        try:
            df_raw = pd.read_csv(CSV_FILENAME, header=None, sep=";", dtype=str, encoding="utf-8", engine="python")
            df_raw = df_raw.rename(columns={0: "descr_it", 1: "descr_en", 2: "code"})
            df_raw["code"] = df_raw["code"].apply(lambda x: str(x).strip().upper().zfill(3))
            df_raw["descr_it"] = df_raw["descr_it"].astype(str).str.strip()
            df_opt = df_raw.drop_duplicates(subset=["code"]).reset_index(drop=True)
            st.success(f"✔️ Database di decodifica attivo. Caricati {len(df_opt)} codici OPT unici della griglia.")
        except Exception as e:
            st.error(f"Errore nel parsing del file '{CSV_FILENAME}': {e}")
    else:
        st.error(f"File '{CSV_FILENAME}' non rilevato nella repository corrente.")

    st.markdown("---")
    opt_input = st.text_area(
        "Incolla qui la stringa o la lista dei codici OPT da analizzare:",
        height=130,
        placeholder="Esempio: 041, 140, 253, 316, 4BF",
        key="opt_checker_area"
    )
    
    analyze_button = st.button("Avvia Decodifica Stringa", type="primary")

    opt_rfid_map = {
        "Ruote in lega": ["0R2", "1LR", "431", "404"],
        "Ruote in lamiera": ["03G", "5EV", "980"],
        "Autoradio / Infotainment": ["1RB", "2PX", "2PZ", "CMX", "CMY"],
        "Kit gonfiaggio (Fix&Go)": ["499"],
        "Ruota di scorta": ["980"],
        "Gancio traino": ["734"],
    }

    def find_opt_in_group(vehicle_codes, group_codes, df):
        found = []
        if df is None: return found
        db_codes_set = set(df["code"])
        normalized_group = [str(c).strip().upper().zfill(3) for c in group_codes]
        for code in vehicle_codes:
            if code in normalized_group and code in db_codes_set:
                row = df[df["code"] == code].iloc[0]
                found.append((code, row["descr_it"]))
        return found

    if analyze_button:
        if df_opt is None:
            st.error("Database OPT non pronto.")
        elif not opt_input.strip():
            st.error("Nessun codice inserito nel box di testo.")
        else:
            raw_codes = opt_input.replace(",", " ").replace(";", " ").split()
            vehicle_codes = sorted(set(str(code).strip().upper().zfill(3) for code in raw_codes if str(code).strip()))
            
            # Layout Risultati Analisi
            st.markdown(f"#### Analisi completata: Rilevati **{len(vehicle_codes)}** codici unici.")
            
            db_codes = set(df_opt["code"].unique())
            present, missing = [], []

            for code in vehicle_codes:
                if code in db_codes:
                    row = df_opt[df_opt["code"] == code].iloc[0]
                    present.append({"code": code, "descr_it": row["descr_it"]})
                else:
                    missing.append(code)

            # Sezione Controlli Critici Omologativi
            st.markdown("### 🔧 Componenti Critici Rilevati")
            crit_col1, crit_col2 = st.columns(2)
            
            for i, (label, group_codes) in enumerate(opt_rfid_map.items()):
                found = find_opt_in_group(vehicle_codes, group_codes, df_opt)
                target_col = crit_col1 if i % 2 == 0 else crit_col2
                
                with target_col:
                    if found:
                        lines = "; ".join(f"[{c}] {d}" for c, d in found)
                        st.markdown(f"<div style='padding:12px; background: rgba(40, 167, 69, 0.1); border: 1px solid #28a745; border-radius:8px; margin-bottom:8px;'><b style='color:#28a745;'>✔️ {label}</b><br><span style='font-size:13px; color:#e2e8f0;'>Presente: {lines}</span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='padding:12px; background: rgba(220, 53, 69, 0.1); border: 1px solid #dc3545; border-radius:8px; margin-bottom:8px;'><b style='color:#dc3545;'>❌ {label}</b><br><span style='font-size:13px; color:#cbd5e1;'>Non configurato in lista</span></div>", unsafe_allow_html=True)

            # Elenco completo delle decodifiche estese
            st.markdown("### 📦 Elenco Completo OPT Decodificati")
            if present:
                for item in present:
                    st.markdown(f"<div class='opt-box'><div><b style='color:#4f7bd6; font-size:16px;'>{item['code']}</b> — <span style='color:#f1f5f9;'>{item['descr_it']}</span></div><span style='color:#21c35a; font-size:12px;'>● Validato</span></div>", unsafe_allow_html=True)
            else:
                st.info("Nessun codice inserito corrisponde al database.")

            if missing:
                with st.expander("⚠️ Visualizza Codici Anonimi o Non Trovati nel DB"):
                    st.warning(", ".join(missing))

            # Creazione blocco di testo pulito pronto per Excel/Mail
            output_lines = ["--- REPORT DECODIFICA OPT DUCATO ---"]
            for label, group_codes in opt_rfid_map.items():
                found = find_opt_in_group(vehicle_codes, group_codes, df_opt)
                output_lines.append(f"{label}: PRESENTE -> {'; '.join(f'[{c}] {d}' for c, d in found)}" if found else f"{label}: ASSENTE")
            
            output_lines.append("\n[ELENCO COMPLETO]")
            for item in present:
                output_lines.append(f"{item['code']} - {item['descr_it']}")
            if missing:
                output_lines.append(f"\nNON TROVATI NEL DB: {', '.join(missing)}")
                
            st.markdown("---")
            st.subheader("📋 Output pronto da Copiare / Incollare")
            st.text_area("Copia questo testo per i tuoi log o per le comunicazioni di stabilimento:", value="\n".join(output_lines), height=200)

# =========================================================
# TAB 3: VERIFICA OPT IN BASE A SINCOM (S / O / ND)
# =========================================================
with tab3:
    st.subheader("Verifica OPT in base a SINCOM")
    st.write("Inserisci il codice SINCOM completo: il sistema mostra quali OPT sono di serie (S), quali sono optional selezionabili (O) e quali non sono disponibili (ND).")

    df_tab, tab_avvisi, tab_ok = None, [], False
    if not os.path.exists(TABELLONE_FILENAME):
        st.error(f"⚠️ File '{TABELLONE_FILENAME}' non rilevato nella repository corrente.")
    else:
        try:
            df_tab, tab_avvisi = load_tabellone(TABELLONE_FILENAME, os.path.getmtime(TABELLONE_FILENAME))
            tab_ok = True
        except Exception as e:
            st.error(f"⚠️ Errore nel caricamento di '{TABELLONE_FILENAME}': {e}")

    opt_descr = {}
    if tab_ok:
        if os.path.exists(OPT_DESCR_FILENAME):
            try:
                opt_descr = load_opt_descriptions(OPT_DESCR_FILENAME, os.path.getmtime(OPT_DESCR_FILENAME))
            except Exception as e:
                st.warning(f"Descrizioni OPT non caricate ('{OPT_DESCR_FILENAME}'): {e}. Verranno mostrati solo i codici.")
        else:
            st.warning(f"File '{OPT_DESCR_FILENAME}' non rilevato: verranno mostrati solo i codici, senza descrizione.")

        if tab_avvisi:
            with st.expander(f"ℹ️ Avvisi sul tabellone ({len(tab_avvisi)})"):
                for a in tab_avvisi:
                    st.markdown(f"- {a}")

        sincom_input = st.text_input(
            "Codice SINCOM completo:",
            value=sincom_from_tab1 or "",
            placeholder="Esempio: 290.ALD.2.01.000",
        )
        filtro_opt = st.text_input(
            "Filtra per codice o descrizione (opzionale):",
            placeholder="Esempio: ruote, 0R2, radio",
        ).strip().lower()

        if sincom_input.strip():
            sincom_key, sincom_err = normalize_sincom(sincom_input)
            if sincom_err:
                st.error(f"⚠️ {sincom_err}")
            elif sincom_key not in df_tab.index:
                st.warning(f"Il SINCOM **{sincom_key}** non è presente nel tabellone OPT.")
                serie_presenti = sorted({k.split(".")[2] for k in df_tab.index})
                st.caption(f"Serie presenti nel tabellone: {', '.join(serie_presenti)}.")
                prefisso = ".".join(sincom_key.split(".")[:2]) + "."
                simili = [k for k in df_tab.index if k.startswith(prefisso)]
                if simili:
                    st.info("Varianti disponibili per lo stesso modello e sigla ABn:\n\n" + "\n".join(f"- `{k}`" for k in simili[:20]))
                else:
                    st.info("Nessuna variante con questo modello e sigla ABn nel tabellone.")
            else:
                avail = split_availability(df_tab.loc[sincom_key])

                st.markdown("---")
                st.markdown(f"##### SINCOM analizzato: `{sincom_key}`")
                st.markdown("**Per il SINCOM da te inserito la disponibilità dei codici opt è la seguente:**")

                col_s, col_o, col_nd = st.columns(3)
                with col_s:
                    st.markdown(render_opt_column("Serie", "#21c35a", avail["S"], opt_descr, filtro_opt), unsafe_allow_html=True)
                with col_o:
                    st.markdown(render_opt_column("Optional", "#4f7bd6", avail["O"], opt_descr, filtro_opt), unsafe_allow_html=True)
                with col_nd:
                    st.markdown(render_opt_column("Non disponibile", "#ff4b4b", avail["ND"], opt_descr, filtro_opt), unsafe_allow_html=True)

                if avail["ALTRO"]:
                    with st.expander(f"⚠️ Codici con valore non riconosciuto nel tabellone ({len(avail['ALTRO'])})"):
                        st.write(", ".join(avail["ALTRO"]))

                report_lines = [f"--- DISPONIBILITÀ OPT PER SINCOM {sincom_key} ---"]
                for label, key_av in (("SERIE", "S"), ("OPTIONAL", "O"), ("NON DISPONIBILE", "ND")):
                    report_lines.append(f"\n[{label}] ({len(avail[key_av])})")
                    for c in avail[key_av]:
                        report_lines.append(f"{c} - {opt_descr.get(c, '(descrizione non in griglia)')}")

                st.markdown("---")
                st.subheader("📋 Output pronto da Copiare / Incollare")
                st.text_area(
                    "Copia questo testo per i tuoi log o per le comunicazioni di stabilimento:",
                    value="\n".join(report_lines),
                    height=220,
                )

# =========================================================
# TAB 4: VERIFICA ORDINE (MUST HAVE & INCOMPATIBILITÀ)
# =========================================================
with tab4:
    st.subheader("Verifica e Correzione Automatica dell'Ordine")
    st.write("Incolla la lista di OPT desiderata: il sistema aggiunge i must-have mancanti (dove non ambigui) e rimuove le incompatibilità, generando una stringa pronta all'uso.")

    if not rules_ready:
        st.error(f"⚠️ Errore nel caricamento dei file di regole (must have / incompatibilità): {rules_error}")
        st.info("Verifica i nomi dei file: must_have_SL.csv, must_have_E7.csv, incompatibilita_SL.csv, incompatibilita_E7.csv (senza accenti, separatore ';').")
    elif serie_sel is None:
        st.warning("⚠️ Vai prima nel tab **Configuratore SINCOM & Plant** e seleziona la Serie (Serial Life / €7 o MY28): questa scelta determina quale set di regole (SL o E7) viene applicato qui.")
    else:
        serie_label_map = {"2": "Serial Life (SL)", "3": "€7 / MY28 (E7)"}
        st.info(f"Set di regole attivo: **{serie_label_map.get(serie_sel, serie_sel)}** — coerente con la Serie scelta nel tab Configuratore.")

        must_have_dict = MUST_HAVE[serie_sel]
        incompat_dict = INCOMPAT[serie_sel]

        order_input = st.text_area(
            "Incolla qui la stringa o la lista dei codici OPT dell'ordine:",
            height=130,
            placeholder="Esempio: 129, 901, 070, 213",
            key="order_check_area"
        )

        check_button = st.button("Verifica e Correggi Ordine", type="primary", key="order_check_button")

        if check_button:
            if not order_input.strip():
                st.error("Nessun codice inserito nel box di testo.")
            else:
                raw_codes = order_input.replace(",", " ").replace(";", " ").split()
                vehicle_codes = [norm_code(c) for c in raw_codes if c.strip()]

                final_codes, report = analyze_order(vehicle_codes, must_have_dict, incompat_dict)

                st.markdown("---")
                st.markdown(
                    f"""
                    <div class="hero-card" style="border-top: 5px solid #21c35a;">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">STRINGA OPT CORRETTA</span>
                        <div style="font-size: 30px; font-weight: 800; color: #ffffff; margin: 14px 0; letter-spacing: 1px; word-break: break-word;">{', '.join(final_codes) if final_codes else '—'}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.text_area("Copia la stringa corretta:", value=", ".join(final_codes), height=80, key="order_result_copy")

                st.markdown("### 📋 Analisi Codice per Codice")

                if report["must_have_added"]:
                    with st.expander(f"➕ Must Have aggiunti automaticamente ({len(report['must_have_added'])})", expanded=True):
                        for code, added in report["must_have_added"]:
                            st.markdown(f"- **{code}** → aggiunti: `{', '.join(added)}`")

                if report["must_have_choice_needed"]:
                    with st.expander(f"❓ Must Have con alternative — scelta manuale richiesta ({len(report['must_have_choice_needed'])})", expanded=True):
                        for code, groups in report["must_have_choice_needed"]:
                            alt_text = "  oppure  ".join(f"[{' + '.join(g)}]" for g in groups)
                            st.markdown(f"- **{code}** richiede una tra: {alt_text}")

                if report["incompat_conflicts"]:
                    with st.expander(f"🚫 Incompatibilità rimosse automaticamente ({len(report['incompat_conflicts'])})", expanded=True):
                        for removed_code, kept_code in report["incompat_conflicts"]:
                            st.markdown(f"- **{removed_code}** rimosso perché incompatibile con **{kept_code}** (già presente/prioritario)")

                if report["must_have_manual"] or report["incompat_manual"]:
                    with st.expander(f"🔎 Regole con condizioni particolari — verifica manuale ({len(report['must_have_manual']) + len(report['incompat_manual'])})"):
                        for code, raw in report["must_have_manual"]:
                            st.markdown(f"- **{code}** (must have): _{raw}_")
                        for code, raw in report["incompat_manual"]:
                            st.markdown(f"- **{code}** (incompatibilità): _{raw}_")

                unknown = sorted(set(report["must_have_unknown"]) | set(report["incompat_unknown"]))
                if unknown:
                    with st.expander(f"ℹ️ Codici non presenti nei file di regole ({len(unknown)})"):
                        st.write(", ".join(unknown))

                if report["must_have_ok"]:
                    with st.expander(f"✔️ Must Have già soddisfatti ({len(report['must_have_ok'])})"):
                        st.write(", ".join(report["must_have_ok"]))

                if not any([report["must_have_added"], report["must_have_choice_needed"],
                            report["incompat_conflicts"], report["must_have_manual"],
                            report["incompat_manual"]]):
                    st.success("Nessuna correzione automatica necessaria e nessuna condizione particolare da verificare manualmente.")
