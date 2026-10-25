import streamlit as st
import pandas as pd
import os
import re
import html

def norm_code(c):
    return str(c).strip().upper().zfill(3)

# ---------------------------------------------------------
# TABELLONE OPT PER SINCOM (S = Serie, O = Optional, ND = Non disponibile)
# ---------------------------------------------------------
TABELLONI = {
    "Sevel": "TABELLONE_OPT_SEVEL.csv",
    "Gliwice": "TABELLONE_OPT_GLIWICE.csv",
}
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

    # forma con punto mancante tra modello e ABn: primo campo di 6 caratteri (es. 298AGU)
    if len(tokens) == 4 and len(tokens[0]) == 6:
        tokens = [tokens[0][:3], tokens[0][3:]] + tokens[1:]

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
# AUTENTICAZIONE (schermata iniziale di accesso)
# ---------------------------------------------------------
# Gli utenti NON sono scritti nel codice: stanno nei "Secrets" di Streamlit (vedi README_autenticazione.txt),
# come   [users]  nome.cognome = "pbkdf2$<iterazioni>$<salt>$<hash>"   (password mai in chiaro).
import hashlib as _hashlib
import hmac as _hmac
import time as _time

def _verify_password(password, stored):
    try:
        scheme, iters, salt, digest = str(stored).split("$")
        if scheme != "pbkdf2":
            return False
        calc = _hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters)).hex()
        return _hmac.compare_digest(calc, digest)
    except Exception:
        return False

def _load_users():
    try:
        return {str(k).strip().lower(): v for k, v in dict(st.secrets["users"]).items()}
    except Exception:
        return {}

def require_login():
    """Mostra la schermata di accesso e blocca l'app finché l'utente non è autenticato."""
    if st.session_state.get("auth_user"):
        with st.sidebar:
            st.caption(f"👤 Utente: **{st.session_state['auth_user']}**")
            if st.button("Esci (logout)", key="logout_btn"):
                for k in ("auth_user", "auth_fails", "auth_lock_until"):
                    st.session_state.pop(k, None)
                st.rerun()
        return

    users = _load_users()
    st.title("Ducato ITPL Toolbox 🚐")
    st.markdown("### 🔐 Accesso riservato")
    if not users:
        st.error("Accesso non configurato: nessun utente definito nei Secrets dell'applicazione. "
                 "Contatta l'amministratore.")
        st.stop()

    lock_until = st.session_state.get("auth_lock_until", 0)
    wait = int(lock_until - _time.time())
    if wait > 0:
        st.error(f"Troppi tentativi errati. Riprova tra {wait} secondi.")
        st.stop()

    with st.form("login_form"):
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Accedi", type="primary")
    if ok:
        stored = users.get(u.strip().lower())
        # si esegue sempre un confronto, anche con utente inesistente (stesso tempo di risposta)
        valid = _verify_password(p, stored if stored else "pbkdf2$1$00$00")
        if stored and valid:
            st.session_state["auth_user"] = u.strip()
            st.session_state["auth_fails"] = 0
            st.rerun()
        fails = st.session_state.get("auth_fails", 0) + 1
        st.session_state["auth_fails"] = fails
        if fails >= 5:
            st.session_state["auth_lock_until"] = _time.time() + 60 * min(fails - 4, 10)
        _time.sleep(1)
        st.error("Utente o password non corretti.")
    st.stop()

require_login()

# ---------------------------------------------------------
# HEADER DELL'APPLICAZIONE
# ---------------------------------------------------------
st.title("Ducato ITPL Toolbox 🚐")
st.write("Piattaforma integrata per la validazione dei codici d'ordine e decodifica rapida degli OPT.")
st.markdown("---")

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

    # --- scelta del plant (ogni plant ha il proprio tabellone: lo stesso SINCOM può avere disponibilità diverse)
    plant_default = 0
    _plants = list(TABELLONI.keys())
    if sincom_from_tab1:
        if globals().get("producibile_gliwice") and not globals().get("producibile_sevel") and "Gliwice" in _plants:
            plant_default = _plants.index("Gliwice")
    plant_sel = st.radio("Plant / Tabellone di riferimento:", _plants, index=plant_default,
                         horizontal=True, key="tab3_plant",
                         help="Sevel: TABELLONE_OPT_SEVEL.csv — Gliwice: TABELLONE_OPT_GLIWICE.csv")
    TABELLONE_FILE = TABELLONI[plant_sel]

    df_tab, tab_avvisi, tab_ok = None, [], False
    if not os.path.exists(TABELLONE_FILE):
        st.error(f"⚠️ File '{TABELLONE_FILE}' non rilevato nella repository corrente.")
    else:
        try:
            df_tab, tab_avvisi = load_tabellone(TABELLONE_FILE, os.path.getmtime(TABELLONE_FILE))
            tab_ok = True
        except Exception as e:
            st.error(f"⚠️ Errore nel caricamento di '{TABELLONE_FILE}': {e}")

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
                st.warning(f"Il SINCOM **{sincom_key}** non è presente nel tabellone OPT di **{plant_sel}**.")
                # presente nell'altro plant?
                for _p, _f in TABELLONI.items():
                    if _p != plant_sel and os.path.exists(_f):
                        try:
                            _df2, _ = load_tabellone(_f, os.path.getmtime(_f))
                            if sincom_key in _df2.index:
                                st.info(f"Questo SINCOM è presente nel tabellone **{_p}**: selezionalo nel riquadro 'Plant' qui sopra.")
                        except Exception:
                            pass
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
                st.markdown(f"##### SINCOM analizzato: `{sincom_key}` — Plant: **{plant_sel}**")
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

                report_lines = [f"--- DISPONIBILITÀ OPT PER SINCOM {sincom_key} (PLANT {plant_sel.upper()}) ---"]
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
# TAB 4: VERIFICA ORDINE (MUST HAVE & INCOMPATIBILITÀ) — NUOVO FORMATO
# =========================================================
#
# File letti (separatore ';', una riga = una regola):
#   incompatibilita_SL.csv / incompatibilita_E7.csv   ->  OPT;CONDIZIONE;INCOMPATIBILI
#   must_have_SL.csv        / must_have_E7.csv        ->  OPT;CONDIZIONE;MUST HAVE
# CONDIZIONE: vuota = sempre; CAMPO=v1|v2 ; più termini con &  ; CAMPO=!v = negazione.
# MUST HAVE : '+' = AND, '|' = OR  (es. 4EB+50E+4N5 | 4EB+50E+732).
# INCOMPATIBILI: codici separati da virgola (la regola vale in entrambe le direzioni).
import io as _io
import re as _re

_CODE = _re.compile(r"^[0-9A-Z]{3}$")
_FIELDS = {"ALIMENTAZIONE", "EMISSIONI", "GAMMA", "BODY", "MARCA",
           "LUNGHEZZA", "ALTEZZA", "PESO", "CLASSE", "MODELLO"}
_FIELD_ALIAS = {"ALIEMNTAZIONE": "ALIMENTAZIONE", "ALIMENTAZIONI": "ALIMENTAZIONE",
                "EMISSIONE": "EMISSIONI"}


def _canon(s):
    """Maiuscolo, senza spazi/punti/trattini; sinonimi comuni uniformati."""
    s = _re.sub(r"[\s.\-_/]", "", str(s).upper())
    syn = {
        "EUROVI": "EURO6E", "EUROVIE": "EURO6E", "EURO6EVIE": "EURO6E",
        "EURO7E": "EURO7", "EUROVII": "EURO7",
        "FURGONE": "VAN", "FURGONI": "VAN",
        "FURGONELASTRATO": "PANELVAN", "FURGONILASTRATI": "PANELVAN",
        "FURGONEVETRATO": "GLAZEDVAN", "FURGONESEMIVETRATO": "HALFGLAZEDVAN",
        "SEMIVETRATO": "HALFGLAZEDVAN", "VETRATO": "GLAZEDVAN",
        "SCUDATI": "SCUDATO", "SCUDATISPECIAL": "SCUDATOSPECIAL",
        "CABINATI": "CABINATO", "CABIINATO": "CABINATO",
        "TL": "CAMPER", "TEMPOLIBERO": "CAMPER", "RETE": "RETAIL",
        "IDROGENO": "HYDROGEN", "ELETTRICO": "BEV",
    }
    return syn.get(s, s)


# Un valore di regola "contiene" i valori del veicolo di questi gruppi (es. VAN ⊃ PANEL VAN)
_GROUPS = {"VAN": {"PANELVAN", "GLAZEDVAN", "HALFGLAZEDVAN"}}
_BODY_WORDS = {"VAN", "PANELVAN", "GLAZEDVAN", "HALFGLAZEDVAN", "CHASSISCAB", "CHASSISCABSPECIAL",
               "MOTORCAB", "COWL", "MOTORCOWL", "COWLSPECIAL", "CHASSISCOWL", "CABINATO",
               "CABINATOSPECIAL", "SCUDATO", "SCUDATOSPECIAL", "CABINAMOTRICE", "DOPPIACABINA",
               "CHASSISSINGLECAB", "CHASSISDOUBLECAB", "DROPSIDESINGLECAB", "DROPSIDEDOUBLECAB"}


def _is_body_value(v):
    c = _canon(v)
    return (c in _BODY_WORDS or c.startswith("CABINATOCABINA") or c.startswith("CASSONATOCABINA")
            or c.startswith("FURGONECABINA"))


def _parse_cond(cond):
    """'A=x|y & B=!z' -> ([(campo, neg, [valori])], [avvisi]). Solleva ValueError se non valida."""
    terms, notes = [], []
    cond = (cond or "").strip()
    if not cond:
        return terms, notes
    for t in cond.split("&"):
        t = t.strip()
        if "=" not in t:
            raise ValueError(f"termine senza '=': '{t}'")
        f, v = t.split("=", 1)
        f = f.strip().upper()
        f2 = _FIELD_ALIAS.get(f, f)
        if f2 != f:
            notes.append(f"campo '{f}' corretto in '{f2}'")
            f = f2
        if f not in _FIELDS:
            raise ValueError(f"campo sconosciuto '{f}'")
        v = v.strip()
        neg = v.startswith("!")
        if neg:
            v = v[1:].strip()
        vals = [x.strip() for x in v.split("|") if x.strip()]
        if not vals:
            raise ValueError(f"valore vuoto per '{f}'")
        if f == "GAMMA" and all(_is_body_value(x) for x in vals):
            notes.append("GAMMA=" + "|".join(vals) + " interpretato come BODY")
            f = "BODY"
        terms.append((f, neg, vals))
    return terms, notes


def _parse_must(expr):
    """'A+B|C+D' -> [[A,B],[C,D]]. Solleva ValueError se non valido."""
    expr = (expr or "").strip().strip(";").strip().upper()
    out = []
    for alt in expr.split("|"):
        codes = [c.strip() for c in alt.split("+")]
        for c in codes:
            if not _CODE.match(c):
                raise ValueError(f"codice non valido '{c}'")
        out.append(codes)
    return out


def _read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def load_rules(path, kind):
    """kind = 'inc' | 'must'. Ritorna dict(rules=[...], known=set, problems=[...], fixes=[...])."""
    text = _read_text(path).replace("\r", "")
    lines = [l for l in text.split("\n") if l.strip()]
    res = {"rules": [], "known": set(), "problems": [], "fixes": []}
    if not lines:
        res["problems"].append((0, "", "file vuoto"))
        return res
    header = [h.strip().upper() for h in lines[0].split(";")]
    if len(header) < 3 or "CONDIZIONE" not in header:
        res["problems"].append((1, lines[0][:80],
                                "intestazione non nel nuovo formato (servono 3 colonne: OPT;CONDIZIONE;...)"))
        return res
    for n, line in enumerate(lines[1:], start=2):
        parts = [p.strip() for p in line.split(";")]
        parts = [p for i, p in enumerate(parts) if not (i >= 3 and p == "")]
        if len(parts) != 3:
            res["problems"].append((n, line[:100], f"{len(parts)} campi invece di 3"))
            continue
        code, cond, body = parts[0].upper(), parts[1], parts[2].strip().rstrip(";").strip()
        if not _CODE.match(code):
            res["problems"].append((n, line[:100], f"codice OPT non valido '{code}'"))
            continue
        res["known"].add(code)
        if body == "" or body.lower().startswith("nessun"):
            continue
        try:
            terms, notes = _parse_cond(cond)
            if kind == "must":
                alts = _parse_must(body)
            else:
                alts = []
                for c in _re.split(r"[,\s]+", body.upper()):
                    if not c:
                        continue
                    if not _CODE.match(c):
                        raise ValueError(f"codice non valido '{c}'")
                    alts.append(c)
                if not alts:
                    raise ValueError("lista vuota")
        except ValueError as e:
            res["problems"].append((n, line[:100], str(e)))
            continue
        for nt in notes:
            res["fixes"].append((n, code, nt))
        res["rules"].append({"line": n, "code": code, "cond": cond, "terms": terms, "data": alts})
    return res


@st.cache_data(show_spinner=False)
def _load_rules_cached(path, kind, mtime):
    return load_rules(path, kind)


def _match_value(rule_val, veh_val, field):
    rv, vv = _canon(rule_val), _canon(veh_val)
    if field == "PESO":
        m = _re.match(r"^(<=|>=|<|>)?(\d+(?:\.\d+)?)Q?$", rv)
        try:
            vnum = float(_re.sub(r"[^\d.]", "", str(veh_val)) or "nan")
        except ValueError:
            return None
        if vnum > 200:
            vnum /= 100.0
        if not m or vnum != vnum:
            return None
        op, num = m.group(1), float(m.group(2))
        return {"<": vnum < num, ">": vnum > num, "<=": vnum <= num, ">=": vnum >= num,
                None: vnum == num}[op]
    if rv == vv:
        return True
    if field == "BODY" and vv in _GROUPS.get(rv, set()):
        return True
    if field == "BODY" and rv == "VAN" and vv.endswith("VAN"):
        return True
    if field == "EMISSIONI" and rv == "EURO64" and vv == "EURO64PL8":
        return True
    return False


def eval_cond(terms, attrs):
    """True / False / None (None = non valutabile perché manca una caratteristica del veicolo)."""
    unknown = False
    for field, neg, vals in terms:
        a = attrs.get(field)
        if a is None or str(a).strip() == "":
            unknown = True
            continue
        hits = [_match_value(v, a, field) for v in vals]
        if any(h is True for h in hits):
            res = True
        elif any(h is None for h in hits):
            unknown = True
            continue
        else:
            res = False
        if neg:
            res = not res
        if not res:
            return False
    return None if unknown else True


def build_incompat_map(rules, attrs):
    """-> (mappa codice->{incompatibili: motivo}, regole non valutabili)."""
    inc, unk = {}, []
    for r in rules:
        ok = eval_cond(r["terms"], attrs)
        if ok is False:
            continue
        if ok is None:
            unk.append(r)
            continue
        for y in r["data"]:
            if y == r["code"]:
                continue
            inc.setdefault(r["code"], {})[y] = r["line"]
            inc.setdefault(y, {})[r["code"]] = r["line"]
    return inc, unk


def verify_order(user_codes, must_rules, inc_rules, must_known, inc_known, attrs):
    """Motore: ritorna dict con codici finali, aggiunti, rimossi e dettagli."""
    inc_map, inc_unknown = build_incompat_map(inc_rules, attrs)

    by_code = {}
    must_unknown = []
    for r in must_rules:
        ok = eval_cond(r["terms"], attrs)
        if ok is None:
            must_unknown.append(r)
        elif ok:
            by_code.setdefault(r["code"], []).append(r)

    order = list(dict.fromkeys(user_codes))
    kept, removed = [], []          # removed: (codice, in conflitto con, riga regola)
    for c in order:                 # 1) incompatibilità tra i codici inseriti: vince chi è prima
        hit = next((k for k in kept if k in inc_map.get(c, {})), None)
        if hit:
            removed.append((c, hit, inc_map[c][hit]))
        else:
            kept.append(c)

    added = []                      # (codice aggiunto, richiesto da, riga regola)
    choices = []                    # (codice, [alternative], suggerita)
    blocked = []                    # (codice mancante, richiesto da, in conflitto con)
    ok_list = []
    present = set(kept)
    queue = list(kept)
    handled = set()
    while queue:
        c = queue.pop(0)
        for r in by_code.get(c, []):
            key = (c, r["line"])
            if key in handled:
                continue
            handled.add(key)
            alts = r["data"]
            if any(all(x in present for x in a) for a in alts):
                ok_list.append(c)
                continue
            if len(alts) == 1:
                pick = alts[0]
            else:
                pick = min(alts, key=lambda a: (len([x for x in a if x not in present]), alts.index(a)))
                choices.append((c, alts, pick))
            for m in [x for x in pick if x not in present]:
                clash = next((k for k in present if k in inc_map.get(m, {})), None)
                if clash:
                    blocked.append((m, c, clash))
                    continue
                present.add(m)
                kept.append(m)
                added.append((m, c, r["line"]))
                queue.append(m)

    inc_warn = []                   # possibili incompatibilità con condizione non valutabile
    for r in inc_unknown:
        x = r["code"]
        if x in present:
            for y in r["data"]:
                if y in present:
                    inc_warn.append((x, y, r))
    must_warn = [r for r in must_unknown if r["code"] in present]

    unknown_codes = [c for c in order if c not in must_known and c not in inc_known]
    return {"final": kept, "added": added, "removed": removed, "choices": choices,
            "blocked": blocked, "ok": sorted(set(ok_list)), "inc_warn": inc_warn,
            "must_warn": must_warn, "unknown_codes": unknown_codes, "order": order}


def _first_match(options, text):
    t = _canon(text or "")
    best = None
    for o in options:
        co = _canon(o)
        if co and co in t and (best is None or len(co) > len(_canon(best))):
            best = o
    return best


def _hl_string(res, descr_fn=None):
    """Stringa finale in HTML: aggiunti in verde, rimossi barrati in rosso."""
    added = {a[0] for a in res["added"]}
    removed = {r[0] for r in res["removed"]}
    chips = []
    for c in res["order"]:
        if c in removed:
            chips.append(f'<span style="background:#7f1d1d;color:#fecaca;padding:2px 8px;border-radius:6px;'
                         f'text-decoration:line-through;margin:2px;display:inline-block">{c}</span>')
        else:
            chips.append(f'<span style="background:#1f2937;color:#fff;padding:2px 8px;border-radius:6px;'
                         f'margin:2px;display:inline-block">{c}</span>')
    for c in res["final"]:
        if c in added:
            chips.append(f'<span style="background:#166534;color:#bbf7d0;padding:2px 8px;border-radius:6px;'
                         f'margin:2px;display:inline-block">+ {c}</span>')
    return "".join(chips)


# ---------------------------------------------------------
# INTERFACCIA
# ---------------------------------------------------------
_RULE_FILES = {
    "2": ("Serial Life (SL)", "must_have_SL.csv", "incompatibilita_SL.csv"),
    "3": ("€7 / MY28 (E7)", "must_have_E7.csv", "incompatibilita_E7.csv"),
}
_EMISSIONI_OPT = ["Euro 6E", "Euro 3", "Euro 4", "Euro 5", "Euro 6.1", "Euro 6.4PL8", "Euro 7"]
_ALIM_OPT = ["BEV", "ICE", "HYDROGEN"]
_GAMMA_OPT = ["CAMPER", "RETAIL", "NET RV", "LIGHT", "LIGHT MT NET RV", "LIGHT AT NET RV", "HEAVY NET RV"]
_MARCA_OPT = ["FIAT", "PCOV", "TOYOTA", "JUPITER", "OPEL", "PEUGEOT", "CITROEN", "IVECO", "TME"]
_CLASSE_OPT = ["N1", "N2", "LCV"]


def _sel(label, options, prefill, key):
    opts = ["— non specificato —"] + options
    idx = opts.index(prefill) if prefill in opts else 0
    v = st.selectbox(label, opts, index=idx, key=f"{key}_{prefill}")
    return None if v.startswith("—") else v


with tab4:
    st.subheader("Verifica e Correzione Automatica dell'Ordine")
    st.write("Incolla la lista di OPT: il sistema aggiunge i must have mancanti e rimuove le incompatibilità, "
             "valutando le condizioni (gamma, alimentazione, emissioni…) in base al veicolo.")

    if serie_sel not in _RULE_FILES:
        st.warning("⚠️ Vai prima nel tab **Configuratore SINCOM & Plant** e seleziona la Serie "
                   "(Serial Life / €7 o MY28): determina quale set di regole viene applicato qui.")
    else:
        set_label, mh_file, inc_file = _RULE_FILES[serie_sel]
        missing = [f for f in (mh_file, inc_file) if not os.path.exists(f)]
        if missing:
            st.error(f"⚠️ File di regole non trovati nella repository: {', '.join(missing)}")
        else:
            mh = _load_rules_cached(mh_file, "must", os.path.getmtime(mh_file))
            ic = _load_rules_cached(inc_file, "inc", os.path.getmtime(inc_file))
            st.info(f"Set di regole attivo: **{set_label}** — {len(mh['rules'])} regole must have, "
                    f"{len(ic['rules'])} regole di incompatibilità.")

            bad = mh["problems"] + ic["problems"]
            if bad or mh["fixes"] or ic["fixes"]:
                with st.expander(f"🧪 Controllo file regole ({len(bad)} righe da correggere, "
                                 f"{len(mh['fixes']) + len(ic['fixes'])} correzioni automatiche)",
                                 expanded=bool(bad)):
                    for name, d in ((mh_file, mh), (inc_file, ic)):
                        for n, txt, why in d["problems"]:
                            st.markdown(f"- ❌ **{name}** riga {n}: {why} — `{txt}` _(riga ignorata)_")
                        for n, code, why in d["fixes"]:
                            st.markdown(f"- 🔧 **{name}** OPT {code} (riga {n}): {why}")

            # ---- caratteristiche del veicolo (precompilate dal Configuratore dove possibile)
            ss = st.session_state
            sinc = globals().get("sincom_from_tab1") or ""
            modello_pre = sinc.split(".")[0] if sinc else ""
            lung_m = _re.search(r"\bL\d\b", str(ss.get("cfg_lunghezza", "")).upper())
            alt_m = _re.search(r"\bH\d\b", str(ss.get("cfg_altezza", "")).upper())
            alim_txt = str(ss.get("cfg_motore", ""))
            alim_pre = (_first_match(_ALIM_OPT, alim_txt)
                        or ("BEV" if "ELETTR" in alim_txt.upper() else None)
                        or ("HYDROGEN" if "IDROGEN" in alim_txt.upper() else None)
                        or ("ICE" if alim_txt else None))
            with st.expander("🚐 Caratteristiche del veicolo (usate per valutare le CONDIZIONI delle regole)",
                             expanded=True):
                st.caption("I campi sono precompilati dal Configuratore dove possibile: correggili se serve. "
                           "Una regola con condizione su un campo non specificato NON viene applicata "
                           "e viene segnalata per verifica.")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    a_alim = _sel("Alimentazione", _ALIM_OPT, alim_pre, "v_alim")
                    a_emis = _sel("Emissioni", _EMISSIONI_OPT,
                                  _first_match(_EMISSIONI_OPT, ss.get("cfg_potenza", "")), "v_emis")
                with c2:
                    a_gamma = _sel("Gamma", _GAMMA_OPT, None, "v_gamma")
                    a_marca = _sel("Marca", _MARCA_OPT,
                                   _first_match(_MARCA_OPT, ss.get("cfg_marca", "")), "v_marca")
                with c3:
                    a_body = st.text_input("Body", value=str(ss.get("cfg_body", "")), key=f"v_body_{ss.get('cfg_body','')}")
                    a_mod = st.text_input("Modello", value=modello_pre, key=f"v_mod_{modello_pre}")
                with c4:
                    a_lung = st.text_input("Lunghezza", value=lung_m.group(0) if lung_m else "", key=f"v_lung_{lung_m and lung_m.group(0)}")
                    a_alt = st.text_input("Altezza", value=alt_m.group(0) if alt_m else "", key=f"v_alt_{alt_m and alt_m.group(0)}")
                c5, c6 = st.columns(2)
                with c5:
                    a_peso = st.text_input("Peso (q o kg)", value=str(ss.get("cfg_peso", "")), key=f"v_peso_{ss.get('cfg_peso','')}")
                with c6:
                    a_cl = _sel("Classe", _CLASSE_OPT, None, "v_classe")

            attrs = {"ALIMENTAZIONE": a_alim, "EMISSIONI": a_emis, "GAMMA": a_gamma, "MARCA": a_marca,
                     "BODY": a_body.strip() or None, "MODELLO": a_mod.strip() or None,
                     "LUNGHEZZA": a_lung.strip() or None, "ALTEZZA": a_alt.strip() or None,
                     "PESO": a_peso.strip() or None, "CLASSE": a_cl}

            order_input = st.text_area("Incolla qui la stringa o la lista dei codici OPT dell'ordine:",
                                       height=130, placeholder="Esempio: 129, 901, 070, 213",
                                       key="order_check_area")
            if st.button("Verifica e Correggi Ordine", type="primary", key="order_check_button"):
                codes = [c.strip().upper() for c in _re.split(r"[,;\s]+", order_input) if c.strip()]
                bad_codes = [c for c in codes if not _CODE.match(c)]
                codes = [c for c in codes if _CODE.match(c)]
                if not codes:
                    st.error("Nessun codice OPT valido inserito nel box di testo.")
                else:
                    if bad_codes:
                        st.warning("Token ignorati (non sono codici OPT di 3 caratteri): " + ", ".join(bad_codes))
                    res = verify_order(codes, mh["rules"], ic["rules"], mh["known"], ic["known"], attrs)
                    final = res["final"]

                    st.markdown("---")
                    st.markdown(
                        f"""<div class="hero-card" style="border-top: 5px solid #21c35a;">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">STRINGA OPT CORRETTA</span>
                        <div style="font-size: 26px; font-weight: 800; color: #ffffff; margin: 14px 0; letter-spacing: 1px; word-break: break-word;">{', '.join(final) if final else '—'}</div>
                        </div>""", unsafe_allow_html=True)
                    st.markdown("**Confronto con l'ordine inserito** — "
                                "<span style='color:#86efac'>verde = aggiunto (must have)</span>, "
                                "<span style='color:#fca5a5'>rosso barrato = rimosso (incompatibilità)</span>",
                                unsafe_allow_html=True)
                    st.markdown(_hl_string(res), unsafe_allow_html=True)
                    st.text_area("Copia la stringa corretta:", value=", ".join(final), height=80,
                                 key="order_result_copy")

                    st.markdown("### 📋 Dettaglio")
                    if res["added"]:
                        with st.expander(f"➕ Must have aggiunti ({len(res['added'])})", expanded=True):
                            for m, by, ln in res["added"]:
                                st.markdown(f"- **{m}** richiesto da **{by}** _(riga {ln} di {mh_file})_")
                    if res["choices"]:
                        with st.expander(f"❓ Alternative tra must have — scelta suggerita ({len(res['choices'])})", expanded=True):
                            for c, alts, pick in res["choices"]:
                                alt_txt = "  oppure  ".join("[" + " + ".join(a) + "]" for a in alts)
                                st.markdown(f"- **{c}** richiede una tra: {alt_txt} → aggiunta la più vicina all'ordine: "
                                            f"`{' + '.join(pick)}`. Se serve un'altra alternativa modifica l'ordine e riprova.")
                    if res["removed"]:
                        with st.expander(f"🚫 Incompatibilità rimosse ({len(res['removed'])})", expanded=True):
                            for c, k, ln in res["removed"]:
                                st.markdown(f"- **{c}** rimosso: incompatibile con **{k}** (inserito prima) _(riga {ln} di {inc_file})_")
                    if res["blocked"]:
                        with st.expander(f"⛔ Must have non aggiungibili per incompatibilità ({len(res['blocked'])})", expanded=True):
                            for m, by, clash in res["blocked"]:
                                st.markdown(f"- **{by}** richiede **{m}**, ma **{m}** è incompatibile con **{clash}**: "
                                            f"l'ordine va rivisto a mano.")
                    if res["must_warn"] or res["inc_warn"]:
                        n = len(res["must_warn"]) + len(res["inc_warn"])
                        with st.expander(f"🔎 Regole con condizione non valutabile — specifica le caratteristiche del veicolo ({n})"):
                            for r in res["must_warn"]:
                                st.markdown(f"- **{r['code']}** must have `{'|'.join('+'.join(a) for a in r['data'])}` "
                                            f"se `{r['cond']}`")
                            for x, y, r in res["inc_warn"]:
                                st.markdown(f"- **{x}** e **{y}** potrebbero essere incompatibili se `{r['cond']}`")
                    if res["unknown_codes"]:
                        with st.expander(f"ℹ️ Codici non presenti nei file di regole ({len(res['unknown_codes'])})"):
                            st.write(", ".join(res["unknown_codes"]))
                    if res["ok"]:
                        with st.expander(f"✔️ Must have già soddisfatti ({len(res['ok'])})"):
                            st.write(", ".join(res["ok"]))
                    if not (res["added"] or res["removed"] or res["choices"] or res["blocked"]
                            or res["must_warn"] or res["inc_warn"]):
                        st.success("Nessuna correzione necessaria.")
