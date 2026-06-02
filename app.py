import streamlit as st
import pandas as pd
import os

# --- Config pagina ---
st.set_page_config(page_title="Ducato OPT Checker (Beta)", page_icon="🚐")
st.title("Ducato OPT Checker (Beta) 🚐")
st.write("Versione beta per la lettura rapida degli OPT da griglia prodotto.")

# --- Nome del file CSV presente nella repository ---
CSV_FILENAME = "griglia_prodotto.csv"  # metti qui il nome esatto del file nella repo

# --- 1. Caricamento automatico del CSV dalla repository ---
st.subheader("1. Database OPT (caricato dalla repository)")

df_opt = None
if os.path.exists(CSV_FILENAME):
    try:
        # Il CSV è strutturato: colonna0 = descr_it, colonna1 = descr_en, colonna2 = code
        df_raw = pd.read_csv(CSV_FILENAME, header=None, sep=";", dtype=str, encoding="utf-8", engine="python")
        df_raw = df_raw.rename(columns={0: "descr_it", 1: "descr_en", 2: "code"})

        # Pulizia base
        df_raw["code"] = df_raw["code"].astype(str).str.strip().str.upper()
        df_raw["descr_it"] = df_raw["descr_it"].astype(str).str.strip()
        df_raw["descr_en"] = df_raw["descr_en"].astype(str).str.strip()

        # Rimuovi righe senza codice
        df_raw = df_raw[df_raw["code"] != ""]

        # Elimina duplicati per codice, tenendo la prima occorrenza
        df_opt = df_raw.drop_duplicates(subset=["code"]).reset_index(drop=True)

        st.success(f"Database OPT caricato automaticamente. Codici unici: {len(df_opt)}")
    except Exception as e:
        st.error(f"Errore nel leggere il file CSV '{CSV_FILENAME}': {e}")
        df_opt = None
else:
    st.error(f"File CSV non trovato nella repository: '{CSV_FILENAME}'. Caricalo nella repo e riprova.")
    st.info("Nome file atteso: " + CSV_FILENAME)

# --- 2. Input OPT vettura ---
st.subheader("2. Inserisci gli OPT della vettura")
opt_input = st.text_area(
    "Incolla qui la stringa con i codici OPT (separati da spazio, virgola o a capo)",
    height=120,
    placeholder="Esempio: 253 316 980 499 ..."
)

analyze_button = st.button("Analizza OPT")

# --- 3. Mappa OPT critici per RFID / RdT (modificabile) ---
opt_rfid_map = {
    "Ruote in lega": ["0R2", "1LR", "431", "404"],
    "Ruote in lamiera": ["03G", "5EV", "980"],
    "Autoradio": ["1RB", "2PX", "2PZ", "CMX", "CMY"],
    "Kit gonfiaggio (Fix&Go)": ["499"],
    "Ruota di scorta": ["980"],
}

def find_opt_in_group(vehicle_codes, group_codes, df):
    """Ritorna lista di (code, descr_it) presenti nel gruppo."""
    found = []
    if df is None:
        return found
    db_codes_set = set(df["code"])
    for code in vehicle_codes:
        if code in group_codes and code in db_codes_set:
            row = df[df["code"] == code].iloc[0]
            found.append((code, row["descr_it"]))
    return found

# --- 4. Logica di analisi e rendering output ---
if analyze_button:
    if df_opt is None:
        st.error("Database non disponibile. Controlla che il file CSV sia presente nella repository.")
    elif not opt_input.strip():
        st.error("Inserisci almeno un codice OPT nella textarea.")
    else:
        # Normalizza input: supporta spazi, virgole, punti e virgola, a capo
        raw_codes = opt_input.replace(",", " ").replace(";", " ").split()
        vehicle_codes = sorted(set(code.strip().upper() for code in raw_codes if code.strip()))

        st.write(f"Codici trovati nella stringa: **{len(vehicle_codes)}**")

        db_codes = set(df_opt["code"].unique())

        present = []
        missing = []

        for code in vehicle_codes:
            if code in db_codes:
                row = df_opt[df_opt["code"] == code].iloc[0]
                present.append({
                    "code": code,
                    "descr_it": row["descr_it"]
                })
            else:
                missing.append(code)

        # --- 4.1 Sezione speciale RFID / RdT ---
        st.markdown("## 🔧 OPT per RFID / RdT")
        for label, group_codes in opt_rfid_map.items():
            found = find_opt_in_group(vehicle_codes, group_codes, df_opt)
            if found:
                # Mostra tutte le occorrenze trovate per il gruppo (più informativo)
                lines = "; ".join(f"**{c}** — {d}" for c, d in found)
                st.markdown(f"**{label}:** ✅ Presente — {lines}")
            else:
                # Se non trovato, mostriamo anche se uno dei codici del gruppo è nella stringa ma non nel DB
                # (utile per capire se il codice è scritto ma non presente nella griglia)
                in_string_but_not_in_db = [c for c in group_codes if c in vehicle_codes and c not in set(df_opt["code"])]
                if in_string_but_not_in_db:
                    st.markdown(f"**{label}:** ❌ Assente nel DB (codice presente nella stringa: {', '.join(in_string_but_not_in_db)})")
                else:
                    st.markdown(f"**{label}:** ❌ Assente")

        # --- 4.2 Sezione OPT presenti (solo quelli trovati) ---
        st.markdown("## 📦 OPT presenti in vettura")
        if present:
            for item in present:
                st.markdown(f"- **{item['code']}** — {item['descr_it']}")
        else:
            st.write("_Nessun codice della vettura è presente nel database._")

        # --- 4.3 OPT non trovati (in expander per non appesantire la pagina) ---
        if missing:
            with st.expander("OPT non trovati nel database"):
                st.write(", ".join(missing))

        # --- 4.4 Suggerimento rapido per copia output (testo pronto) ---
        # Costruisco un testo sintetico che l'utente può copiare velocemente
        output_lines = []
        output_lines.append("🔧 OPT per RFID / RdT")
        for label, group_codes in opt_rfid_map.items():
            found = find_opt_in_group(vehicle_codes, group_codes, df_opt)
            if found:
                lines = "; ".join(f"{c} - {d}" for c, d in found)
                output_lines.append(f"{label}: Presente — {lines}")
            else:
                output_lines.append(f"{label}: Assente")
        output_lines.append("\n📦 OPT presenti")
        if present:
            for item in present:
                output_lines.append(f"{item['code']} - {item['descr_it']}")
        else:
            output_lines.append("Nessun codice presente nel DB.")
        if missing:
            output_lines.append("\n❓ OPT non trovati")
            output_lines.append(", ".join(missing))

        output_text = "\n".join(output_lines)
        st.subheader("Testo sintetico (copia e incolla)")
        st.text_area("Output pronto da copiare", value=output_text, height=240)
