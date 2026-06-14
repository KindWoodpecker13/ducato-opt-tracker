import streamlit as st
import pandas as pd
import os

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

# Definizione dei Tab principali
tab1, tab2 = st.tabs(["🎛️ Configuratore SINCOM & Plant", "🔬 Checker OPT Avanzato"])

# =========================================================
# TAB 1: CONFIGURATORE SINCOM & PLANT CHECKER
# =========================================================
with tab1:
    st.subheader("Configurazione Guidata del Veicolo")
    st.write("Seleziona i vincoli tecnici per comporre il codice SINCOM corretto e verificarne il Plant di produzione.")
    
    # Tentativo di caricamento di tutti i CSV di configurazione
    try:
        df_a = pd.read_csv("decode_sincom_A.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        df_b = pd.read_csv("decode_sincom_B.csv", sep=";", dtype=str)
        df_b["ALTEZZA"] = df_b["ALTEZZA"].fillna("").astype(str).str.strip()
        df_b["BODY"] = df_b["BODY"].fillna("").astype(str).str.strip()
        
        df_n = pd.read_csv("decode_sincom_n.csv", sep=";", dtype=str).apply(lambda x: x.str.strip())
        
        # Il file di 1° livello fa da matrice di controllo finale per i Plant
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
            modelli_disponibili = sorted(df_a["MODELLO"].unique())
            modello_sel = st.selectbox("Modello", modelli_disponibili, key="cfg_modello")
            
            df_a_f1 = df_a[df_a["MODELLO"] == modello_sel]
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

        # ---------------------------------------------------------
        # ELABORAZIONE LOGICA DELLE COMPATIBILITÀ E DEI PLANT
        # ---------------------------------------------------------
        st.markdown("---")
        st.markdown("### 📋 Analisi di Fattibilità Industriale")
        
        if lettera_A and lettera_B and carattere_n:
            sincom_generato = f"{lettera_A}{lettera_B}{carattere_n}".upper()
            
            # Reset variabili di controllo plant
            producibile_sevel = False
            producibile_gliwice = False
            
            # Eseguiamo il lookup sul foglio di 1° livello per stanare il SINCOM nelle colonne dei Plant
            # Assumiamo che nel file decode_1°lev.csv ci siano le colonne nominate 'SEVEL' e 'GLIWICE'
            if "SEVEL" in df_1lev.columns and "GLIWICE" in df_1lev.columns:
                # Cerchiamo se il codice è presente nella colonna Sevel (cella non vuota e diversa da '-')
                match_sevel = df_1lev[(df_1lev["SEVEL"] == sincom_generato) & (df_1lev["SEVEL"] != "-")]
                # Cerchiamo se il codice è presente nella colonna Gliwice
                match_gliwice = df_1lev[(df_1lev["GLIWICE"] == sincom_generato) & (df_1lev["GLIWICE"] != "-")]
                
                if not match_sevel.empty: producibile_sevel = True
                if not match_gliwice.empty: producibile_gliwice = True
            else:
                # Logica di backup nel caso le colonne abbiano nomi leggermente diversi
                st.warning("⚠️ Intestazioni 'SEVEL' o 'GLIWICE' non trovate in `decode_1°lev.csv`. Uso della logica dimensionale di sicurezza.")
                if lunghezza_sel in ["L4"] or altezza_sel == "H3" or motore_sel in ["BEV", "HYDROGEN"]:
                    producibile_gliwice = True
                else:
                    producibile_sevel = True

            # Determinazione del verdetto finale del plant
            if producibile_sevel and producibile_gliwice:
                plant_text = "CO-PRODUCTION<br><span style='font-size:16px;'>Sevel (IT) & Gliwice (PL)</span>"
                plant_color = "#28a745" # Verde successo
            elif producibile_sevel:
                plant_text = "SEVEL<br><span style='font-size:16px;'>Val di Sangro (Italia)</span>"
                plant_color = "#21c35a" # Verde Sevel
            elif producibile_gliwice:
                plant_text = "GLIWICE<br><span style='font-size:16px;'>Gliwice (Polonia)</span>"
                plant_color = "#4f7bd6" # Blu Stellantis
            else:
                plant_text = "NON PRODUCIBILE<br><span style='font-size:16px;'>Combinazione Esclusa da Matrice</span>"
                plant_color = "#ff4b4b" # Rosso Errore

            # Interfaccia Output Grafica Elegante
            out_col1, out_col2 = st.columns(2)
            
            with out_col1:
                st.markdown(
                    f"""
                    <div class="custom-card" style="border-top: 5px solid #4f7bd6;">
                        <span style="letter-spacing: 1px; color: #cbd5e1; font-weight: 500; font-size: 14px;">CODICE D'ORDINE GENERATO</span>
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
                        <span style="color: #94a3b8; font-size: 12px;">Verificato incrociando i vincoli di 1° Livello</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
            # Preview della feature futura per la Griglia OPT di serie/optional
            st.markdown("---")
            with st.expander("🔮 Matrice dotazioni di serie ed esclusioni OPT (Roadmap)"):
                st.info(f"Logica pronta per l'aggancio: il codice {sincom_generato} interrogherà la griglia prodotto per estrarre la lista degli OPT standard e i pacchetti ordinabili associati a questa specifica combinazione.")
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
            df_raw = df_raw[df_raw["code"] != ""]
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
        placeholder="Esempio: 041, 140, 253, 316, 4bf",
        key="opt_checker_area"
    )
    
    analyze_button = st.button("Avvia Decodifica Stringa", type="primary")

    opt_rfid_map = {
        "Ruote in lega": ["0R2", "1LR", "431", "404"],
        "Ruote in lamiera": ["03G", "5EV", "980"],
        "Autoradio / Infotainment": ["1RB", "2PX", "2PZ", "CMX", "CMY"],
        "Kit gonfiaggio (Fix&Go)": ["499"],
        "Ruota di scorta": ["980"],
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
