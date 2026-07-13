import streamlit as st
import pandas as pd
import os
import re

# ---------------------------------------------------------
# CONFIGURAZIONE PAGINA & GRAFICA AVANZATA (mantieni la tua)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ducato ITPL Toolbox", 
    page_icon="🚐", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    html, body, .stApp { background: none !important; }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        background: linear-gradient(135deg, #071426 0%, #0c203b 40%, #172d54 80%, #25447b 100%);
        z-index: -999;
    }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: rgba(255,255,255,0.05); padding: 8px 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); }
    .stTabs [data-baseweb="tab"] { height: 45px; white-space: pre; background-color: transparent; border-radius: 8px; color: #cbd5e1 !important; font-weight: 600; padding: 0px 20px; transition: all 0.3s ease; }
    .stTabs [aria-selected="true"] { background-color: #4f7bd6 !important; color: #ffffff !important; box-shadow: 0 4px 12px rgba(79, 123, 214, 0.3); }
    .custom-card { background: rgba(255,255,255,0.06); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12); border-radius: 16px; padding: 24px; text-align: center; transition: transform 0.2s ease; }
    .custom-card:hover { transform: translateY(-2px); }
    .opt-box { padding: 10px 14px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; margin-bottom: 6px; display:flex; justify-content:space-between; align-items:center; }
    .stSelectbox label, .stTextArea label { color: #e2e8f0 !important; font-weight: 500 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
st.title("Ducato ITPL Toolbox 🚐")
st.write("Piattaforma integrata per la validazione dei codici d'ordine e decodifica rapida degli OPT.")
st.markdown("---")

# Tabs
tab1, tab2 = st.tabs(["🎛️ Configuratore SINCOM & Plant", "🔬 Checker OPT Avanzato"])

# =========================================================
# Helper functions per parsing CSV di compatibilità / must-have
# =========================================================
def load_incompat_must(csv_path):
    """
    Carica un CSV con colonne: CODICE OPT;INCOMPATIBILIT�  oppure CODICE OPT;MUST HAVE
    Restituisce dict: key=codice (upper, stripped) -> raw string (value) e lista di codici estratti
    """
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path, sep=";", dtype=str, encoding="utf-8", engine="python").fillna("")
    except Exception:
        # tentativo con latin-1
        df = pd.read_csv(csv_path, sep=";", dtype=str, encoding="latin-1", engine="python").fillna("")
    mapping = {}
    for _, row in df.iterrows():
        key = str(row.iloc[0]).strip().upper()
        raw = str(row.iloc[1]) if len(row) > 1 else ""
        raw = raw.replace("\n", " ").strip()
        # estrai codici alfanumerici (es. 3JO, 02T, CMX, 640)
        codes = re.findall(r'\b[A-Z0-9]{1,4}\b', raw.upper())
        # rimuovi numeri che sono solo parentesi o parole comuni (ma manteniamo tutto)
        mapping[key] = {"raw": raw, "codes": sorted(set(codes))}
    return mapping

def extract_codes_from_input(opt_input):
    # normalizza e estrae codici dall'input dell'utente
    raw_codes = re.split(r'[,\s;]+', opt_input.strip().upper())
    codes = [c.strip() for c in raw_codes if c.strip()]
    # zfill(3) non sempre desiderato per alfanumerici; manteniamo originali ma upper
    return sorted(set(codes))

# =========================================================
# TAB 1: CONFIGURATORE SINCOM & Plant CHECKER + Compatibilità OPT
# =========================================================
with tab1:
    st.subheader("Configurazione Guidata del Veicolo")
    st.write("Seleziona i vincoli tecnici per comporre il codice modello + SINCOM e verificarne il Plant di produzione.")

    # Caricamento CSV principali (A, B, n, 1lev, model)
    try:
        df_a = pd.read_csv("decode_sincom_A.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        df_b = pd.read_csv("decode_sincom_B.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        df_n = pd.read_csv("decode_sincom_n.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        df_1lev = pd.read_csv("decode_1°lev.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        df_model = pd.read_csv("decode_model.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        db_ready = True
    except Exception as e:
        st.error(f"⚠️ Errore nel caricamento dei CSV del configuratore: {e}")
        st.info("Verifica che i file siano nominati correttamente e usino il punto e virgola ';' come separatore.")
        db_ready = False

    if db_ready:
        st.markdown("### 🎚️ Seleziona Parametri Griglia Prodotto")

        # Nuovo: selezione Marca/Brand sopra Portata
        col_brand, col_dummy = st.columns([2,1])
        with col_brand:
            brands = sorted([b for b in df_model["MARCA"].fillna("").unique() if b])
            marca_sel = st.selectbox("Marca / Brand", [""] + brands, index=0, key="cfg_marca")
        # Portata e resto
        col1, col2, col3 = st.columns(3)

        # ---------------------------
        # LETTERA A (Struttura)
        # ---------------------------
        with col1:
            st.markdown("#### 📐 Struttura (Lettera A)")
            portate = sorted(df_a["PORTATA"].unique())
            portata_sel = st.selectbox("Portata", portate, key="cfg_portata")

            df_a_f1 = df_a[df_a["PORTATA"] == portata_sel]
            pesi = sorted(df_a_f1["PESO"].unique())
            peso_sel = st.selectbox("Peso (GVW)", pesi, key="cfg_peso")

            df_a_f2 = df_a_f1[df_a_f1["PESO"] == peso_sel]
            lunghezze = sorted(df_a_f2["LUNGHEZZA"].unique())
            lunghezza_sel = st.selectbox("Lunghezza (Passo)", lunghezze, key="cfg_lunghezza")

            res_a = df_a_f2[df_a_f2["LUNGHEZZA"] == lunghezza_sel]
            lettera_A = res_a["SIGLA_A"].values[0] if not res_a.empty else None

        # ---------------------------
        # LETTERA B (Allestimento)
        # ---------------------------
        with col2:
            st.markdown("#### 🚐 Allestimento (Lettera B)")
            body_disponibili = sorted(df_b["BODY"].unique())
            body_sel = st.selectbox("Tipologia Body", body_disponibili, key="cfg_body")

            df_b_f1 = df_b[df_b["BODY"] == body_sel]
            altezze = sorted(df_b_f1["ALTEZZA"].unique())
            altezza_sel = st.selectbox("Altezza Sagoma", altezze, key="cfg_altezza")

            res_b = df_b_f1[df_b_f1["ALTEZZA"] == altezza_sel]
            lettera_B = res_b["CODICE_B"].values[0] if not res_b.empty else None

        # ---------------------------
        # NUMERO n (Motore & Cambio)
        # ---------------------------
        with col3:
            st.markdown("#### ⚙️ Motore & Cambio (Numero n)")
            motori = sorted(df_n["MOTORE"].unique())
            motore_sel = st.selectbox("Alimentazione", motori, key="cfg_motore")

            df_n_f1 = df_n[df_n["MOTORE"] == motore_sel]
            motorizzazioni = sorted(df_n_f1["MOTORIZZAZIONE"].unique())
            motorizz_sel = st.selectbox("Motorizzazione & Emissioni", motorizzazioni, key="cfg_motorizzazione")

            df_n_f2 = df_n_f1[df_n_f1["MOTORIZZAZIONE"] == motorizz_sel]
            cambi = sorted(df_n_f2["CAMBIO"].unique())
            cambio_sel = st.selectbox("Cambio", cambi, key="cfg_cambio")

            res_n = df_n_f2[df_n_f2["CAMBIO"] == cambio_sel]
            carattere_n = res_n["SIGLA_n"].values[0] if not res_n.empty else None

        # ---------------------------
        # Determina codice modello (decode_model.csv)
        # ---------------------------
        model_code = None
        if marca_sel and portata_sel:
            df_m_f = df_model[(df_model["MARCA"] == marca_sel) & (df_model["PORTATA"] == portata_sel)]
            if not df_m_f.empty and "LOGISTIC_MODEL" in df_m_f.columns:
                model_code = df_m_f["LOGISTIC_MODEL"].values[0].strip()

        # ---------------------------------------------------------
        # GENERAZIONE SINCOM + CHECK PLANT
        # ---------------------------------------------------------
        st.markdown("---")
        st.markdown("### 📋 Analisi di Fattibilità Industriale")

        if lettera_A and lettera_B and carattere_n:
            abn = f"{lettera_A}{lettera_B}{carattere_n}".upper()
            if model_code:
                sincom_generato = f"{model_code}.{abn}"
            else:
                sincom_generato = abn

            match = df_1lev[df_1lev["SINCOM"] == abn]  # la matrice 1°lev usa ABn senza prefisso model_code

            if match.empty:
                plant_text = "NON IN MATRICE<br><span style='font-size:16px;'>Combinazione Non Esistente</span>"
                plant_color = "#ff4b4b"
            else:
                sevel = match["SEVEL"].values[0]
                gliwice = match["GLIWICE"].values[0]

                if sevel == "SI" and gliwice == "SI":
                    plant_text = "CO-PRODUCTION<br><span style='font-size:16px;'>Sevel (IT) & Gliwice (PL)</span>"
                    plant_color = "#28a745"
                elif sevel == "SI":
                    plant_text = "SEVEL<br><span style='font-size:16px;'>Val di Sangro (Italia)</span>"
                    plant_color = "#21c35a"
                elif gliwice == "SI":
                    plant_text = "GLIWICE<br><span style='font-size:16px;'>Gliwice (Polonia)</span>"
                    plant_color = "#4f7bd6"
                else:
                    plant_text = "NON PRODUCIBILE<br><span style='font-size:16px;'>Escluso dai Sistemi</span>"
                    plant_color = "#ff4b4b"

            # Output grafico
            out_col1, out_col2 = st.columns(2)

            with out_col1:
                st.markdown(
                    f"""
                    <div class="custom-card" style="border-top: 5px solid #4f7bd6;">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">CODICE MODELLO + D'ORDINE GENERATO</span>
                        <div style="font-size: 44px; font-weight:800; color:#fff; margin: 12px 0;">{sincom_generato}</div>
                        <span style="background: rgba(79, 123, 214, 0.15); color: #93c5fd; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600;">
                            Model: {model_code if model_code else '—'} · Struttura: {lettera_A} | Allestimento: {lettera_B} | Motore: {carattere_n}
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
                        <div style="font-size: 28px; font-weight:800; color:{plant_color}; margin: 18px 0; line-height: 1.2;">{plant_text}</div>
                        <span style="color: #94a3b8; font-size: 12px;">Validato incrociando il database di 1° Livello</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:
            st.error("Combinazione incompleta. Assicurati che tutti i menù a tendina abbiano un valore valido selezionato.")

        # ---------------------------------------------------------
# SEZIONE: Compatibilità OPT ordine (con applicazione automatica)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 🔗 Compatibilità OPT ordine (con correzione automatica)")
st.write("Seleziona il progetto (Serial Life o Euro 7), incolla la stringa OPT dell'ordine e avvia l'analisi. Il sistema segnalerà incompatibilità e must-have e potrà applicare correzioni automaticamente.")

compat_col1, compat_col2 = st.columns([2,1])
with compat_col1:
    project = st.selectbox("Progetto", ["E7 (Euro 7)", "SL (Serial Life)"], key="cfg_project")
    opt_order_input = st.text_area("Stringa OPT ordine (es. 041, 140, 253, 316, 4BF)", height=120, key="cfg_opt_order")
    auto_apply = st.checkbox("Applica automaticamente le correzioni (rimuovi incompatibili / aggiungi must-have mancanti)", value=False, key="cfg_auto_apply")
    analyze_compat = st.button("Analizza e Applica Correzioni OPT", key="btn_analyze_compat_apply")
with compat_col2:
    st.info("I file usati per l'analisi devono essere presenti nella repo:\n- incompatibilità_E7.csv\n- incompatibilità_SL.csv\n- must_have_E7.csv\n- must_have_SL.csv\n\nSe mancano, il sistema mostrerà un errore.")

if analyze_compat:
    # seleziona i file in base al progetto
    if project.startswith("E7"):
        inc_file = "incompatibilità_E7.csv"
        must_file = "must_have_E7.csv"
    else:
        inc_file = "incompatibilità_SL.csv"
        must_file = "must_have_SL.csv"

    inc_map = load_incompat_must(inc_file)
    must_map = load_incompat_must(must_file)

    if not os.path.exists(inc_file):
        st.error(f"File incompatibilità non trovato: {inc_file}")
    elif not os.path.exists(must_file):
        st.error(f"File must-have non trovato: {must_file}")
    else:
        # estrai codici dall'input
        input_codes = extract_codes_from_input(opt_order_input)
        st.markdown(f"**Analisi su {len(input_codes)} codici inseriti**: {', '.join(input_codes) if input_codes else '—'}")

        # --- 1) Rileva incompatibilità dirette tra i codici inseriti
        direct_incompat = []
        for code in input_codes:
            key = code.upper()
            if key in inc_map:
                inc_codes = inc_map[key]["codes"]
                present = [c for c in inc_codes if c in input_codes]
                if present:
                    direct_incompat.append({"code": key, "conflicts": present, "raw": inc_map[key]["raw"]})

        # --- 2) Rileva incompatibilità reverse (altri che dichiarano incompat con i nostri)
        reverse_incompat = []
        for other, info in inc_map.items():
            inter = [c for c in info["codes"] if c in input_codes]
            if inter and other not in input_codes:
                reverse_incompat.append({"other": other, "conflicts": inter, "raw": info["raw"]})

        # --- 3) Must-have: verifica e raccogli mancanti
        must_report = []
        missing_must = []
        for code in input_codes:
            key = code.upper()
            if key in must_map:
                must_codes = must_map[key]["codes"]
                present = [c for c in must_codes if c in input_codes]
                missing = [c for c in must_codes if c not in input_codes]
                must_report.append({"code": key, "must": must_codes, "present": present, "missing": missing, "raw": must_map[key]["raw"]})
                if missing:
                    missing_must.append({"code": key, "missing": missing, "raw": must_map[key]["raw"]})

        # --- 4) Applicazione automatica (se richiesta)
        final_codes = input_codes.copy()
        removals = []
        additions = []

        # Rimuovi incompatibili diretti: per ogni codice A che dichiara incompat con B, se B è presente, rimuoviamo B (scelta: rimuovere il codice "in conflitto" trovato)
        # Nota: comportamento scelto: rimuoviamo i codici che risultano in conflitto con almeno un altro codice presente.
        if auto_apply:
            # costruisci set di codici da rimuovere: tutti i present nelle liste di incompatibilità dei codici inseriti
            to_remove = set()
            for rec in direct_incompat:
                for c in rec["conflicts"]:
                    to_remove.add(c)
            # anche consideriamo reverse incompat: se un OPT esterno dichiara incompat con uno dei nostri, rimuoviamo il nostro che è in conflitto? 
            # Qui preferiamo rimuovere il codice che è elencato nella mappa (cioè l'OPT che dichiara incompatibilità verso i nostri), solo se è presente.
            for rec in reverse_incompat:
                for c in rec["conflicts"]:
                    # rec["other"] è l'OPT che dichiara incompatibilità; se è presente tra i nostri, rimuovilo
                    if rec["other"] in final_codes:
                        to_remove.add(rec["other"])
                    # altrimenti rimuoviamo l'intersezione (i nostri codici che sono nella lista di altri)
                    for ic in rec["conflicts"]:
                        if ic in final_codes:
                            to_remove.add(ic)

            # applica rimozioni
            for r in sorted(to_remove):
                if r in final_codes:
                    final_codes.remove(r)
                    removals.append(r)

            # aggiungi must-have mancanti
            to_add = []
            for rec in missing_must:
                for m in rec["missing"]:
                    if m not in final_codes:
                        to_add.append(m)
            # dedup e applica
            for a in sorted(set(to_add)):
                final_codes.append(a)
                additions.append(a)

        # --- 5) Output report dettagliato
        st.markdown("#### 🔧 Incompatibilità rilevate (dirette)")
        if direct_incompat:
            for rec in direct_incompat:
                st.markdown(f"- **{rec['code']}** incompatibile con: {', '.join(rec['conflicts'])}; presenti nell'ordine: **{', '.join(rec['conflicts'])}**")
                if rec["raw"]:
                    st.caption(rec["raw"])
        else:
            st.success("Nessuna incompatibilità diretta tra i codici inseriti.")

        st.markdown("#### 🔁 Incompatibilità rilevate (reverse / da altri OPT)")
        if reverse_incompat:
            for rec in reverse_incompat:
                st.markdown(f"- **{rec['other']}** dichiara incompatibilità con: {', '.join(rec['conflicts'])}; interseca con i tuoi codici: **{', '.join(rec['conflicts'])}**")
                if rec["raw"]:
                    st.caption(rec["raw"])
        else:
            st.info("Nessuna incompatibilità reverse rilevata.")

        st.markdown("#### ✅ Must-have richiesti")
        if must_report:
            for rec in must_report:
                if rec["must"]:
                    st.markdown(f"- **{rec['code']}** richiede: {', '.join(rec['must'])}; presenti: {', '.join(rec['present']) if rec['present'] else '—'}; mancanti: {', '.join(rec['missing']) if rec['missing'] else '—'}")
                else:
                    st.markdown(f"- **{rec['code']}**: regola complessa o condizionale. Vedi dettaglio.")
                if rec["raw"]:
                    st.caption(rec["raw"])
        else:
            st.info("Nessun must-have rilevato per i codici inseriti.")

        st.markdown("#### 🛠️ Azioni automatiche applicate")
        if auto_apply:
            if removals:
                st.warning(f"Rimossi {len(removals)} codici incompatibili: {', '.join(removals)}")
            else:
                st.info("Nessuna rimozione necessaria.")
            if additions:
                st.success(f"Aggiunti {len(additions)} must-have mancanti: {', '.join(additions)}")
            else:
                st.info("Nessuna aggiunta necessaria.")
        else:
            st.info("Modalità di sola analisi: nessuna modifica automatica applicata. Abilita 'Applica automaticamente' per modificare la lista.")

        st.markdown("#### 📋 Lista OPT risultante (al netto delle correzioni)")
        st.code(", ".join(final_codes) if final_codes else "—", language="text")

        st.markdown("---")
        st.info("Report generato. Se vuoi, posso: 1) esportare la lista finale in un file, 2) applicare regole di priorità più sofisticate (es. preferire rimozione di OPT meno critici), 3) integrare condizioni contestuali (BEV/ICE, lunghezza, marca). Dimmi quale preferisci e lo implemento.")

# =========================================================
# TAB 2: CHECKER OPT (mantieni la logica originale quasi intatta)
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
            
            st.markdown(f"#### Analisi completata: Rilevati **{len(vehicle_codes)}** codici unici.")
            
            db_codes = set(df_opt["code"].unique())
            present, missing = [], []

            for code in vehicle_codes:
                if code in db_codes:
                    row = df_opt[df_opt["code"] == code].iloc[0]
                    present.append({"code": code, "descr_it": row["descr_it"]})
                else:
                    missing.append(code)

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

            st.markdown("### 📦 Elenco Completo OPT Decodificati")
            if present:
                for item in present:
                    st.markdown(f"<div class='opt-box'><div><b style='color:#4f7bd6; font-size:16px;'>{item['code']}</b> — <span style='color:#f1f5f9;'>{item['descr_it']}</span></div><span style='color:#21c35a; font-size:12px;'>● Validato</span></div>", unsafe_allow_html=True)
            else:
                st.info("Nessun codice inserito corrisponde al database.")

            if missing:
                with st.expander("⚠️ Visualizza Codici Anonimi o Non Trovati nel DB"):
                    st.warning(", ".join(missing))

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
