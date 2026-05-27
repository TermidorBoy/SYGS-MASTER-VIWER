import streamlit as st
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import database as db

st.set_page_config(page_title="SYGS MASTER VIEWER", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")

# ── CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main > div { padding: 0.5rem 1.5rem; }
    div[data-testid="stSidebarContent"] { padding: 1rem 0.8rem; }

    .login-box {
        max-width: 400px; margin: 4rem auto; padding: 2.5rem;
        background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        text-align: center;
    }
    .login-box h1 { font-size: 1.6rem; font-weight: 700; color: #1E3A5F; margin-bottom: 0.2rem; }
    .login-box .subtitle { color: #6B7280; font-size: 0.85rem; margin-bottom: 1.5rem; }

    .card {
        background: white; border-radius: 12px; padding: 1.2rem 1.5rem;
        box-shadow: 0 1px 6px rgba(0,0,0,0.04); border: 1px solid #f0f0f0;
        margin-bottom: 0.6rem; transition: 0.15s;
    }
    .card:hover { border-color: #1E3A5F20; box-shadow: 0 2px 12px rgba(30,58,95,0.06); }

    .badge-online {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        background: #10B981; margin-right: 6px;
    }
    .badge-offline {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        background: #D1D5DB; margin-right: 6px;
    }

    .page-title { font-size: 1.5rem; font-weight: 700; color: #1E3A5F; margin-bottom: 0.3rem; }
    .page-sub { color: #6B7280; font-size: 0.9rem; margin-bottom: 1.5rem; }

    div.stButton > button { border-radius: 8px; font-weight: 500; }
    div.stButton > button[data-kind="primary"] { background: #1E3A5F; color: white; }
    div[data-testid="stDataFrame"] { border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }

    .user-avatar {
        width: 36px; height: 36px; border-radius: 50%; display: inline-flex;
        align-items: center; justify-content: center; color: white;
        font-weight: 600; font-size: 0.9rem; flex-shrink: 0;
    }
    .user-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Session State ───────────────────────────────────────────────
INIT = {
    "pagina": "login", "utente": None, "msg": "", "msg_tipo": "success",
    "file_id": None, "filtro_col": "", "filtro_val": "", "ricerca": "",
    "modifica_id": None, "vedi_id": None,
}
for k, v in INIT.items():
    if k not in st.session_state:
        st.session_state[k] = v


def msg(text, tipo="success"):
    st.session_state.msg = text
    st.session_state.msg_tipo = tipo


def cambia_pagina(pag):
    st.session_state.pagina = pag
    st.session_state.msg = ""
    st.rerun()


def iniziali(nome):
    parts = nome.strip().split()
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


db.init_db()

# ── SIDEBAR ─────────────────────────────────────────────────────
with st.sidebar:
    if st.session_state.utente:
        u = st.session_state.utente
        col_av, col_info = st.columns([1, 3])
        with col_av:
            st.markdown(
                f'<div class="user-avatar" style="background:{u["avatar_color"]}">{iniziali(u["nome"])}</div>',
                unsafe_allow_html=True,
            )
        with col_info:
            st.markdown(f"**{u['nome']}**  ")
            st.caption(f"{u['email']}  ·  {'Admin' if u['ruolo']=='admin' else 'Utente'}")

        st.divider()

        # Navigation
        nav_items = [
            ("🏠", "Dashboard", "dashboard"),
            ("📂", "Carica Excel", "carica"),
        ]
        if u["ruolo"] == "admin":
            nav_items.append(("👥", "Gestione Utenti", "utenti"))

        for icon, label, page in nav_items:
            if st.button(f"{icon}  {label}", use_container_width=True, type="secondary" if st.session_state.pagina != page else "primary"):
                cambia_pagina(page)

        st.divider()

        # File list
        files = db.file_utente(u["id"])
        if files:
            st.markdown("**📁 File aperti**")
            for f in files[:5]:
                cols = st.columns([1, 4])
                with cols[0]:
                    is_active = st.session_state.file_id == f["id"]
                    st.markdown("📊" if not is_active else "📌")
                with cols[1]:
                    if st.button(f["nome_file"], key=f"side_f_{f['id']}", help=os.path.dirname(f["percorso"]),
                                 use_container_width=True, type="secondary" if not is_active else "primary"):
                        st.session_state.file_id = f["id"]
                        st.session_state.pagina = "vedi_file"
                        st.rerun()

        st.divider()
        if st.button("🚪  Esci", use_container_width=True):
            st.session_state.utente = None
            st.session_state.pagina = "login"
            st.session_state.file_id = None
            st.rerun()

# ── MAIN ─────────────────────────────────────────────────────────
if st.session_state.msg:
    fn = getattr(st, st.session_state.msg_tipo)
    fn(st.session_state.msg)
    st.session_state.msg = ""

# ── LOGIN ────────────────────────────────────────────────────────
if st.session_state.pagina == "login":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:2.5rem;margin-bottom:0.3rem;">📊</div>', unsafe_allow_html=True)
        st.markdown('<h1>SYGS MASTER VIEWER</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Gestione dati Excel multi-utente</p>', unsafe_allow_html=True)
        email = st.text_input("Email", placeholder="nome@esempio.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        if st.button("Accedi", use_container_width=True, type="primary"):
            if email and password:
                utente = db.login(email, password)
                if utente:
                    st.session_state.utente = utente
                    st.session_state.pagina = "dashboard"
                    msg(f"Benvenuto, {utente['nome']}!")
                    st.rerun()
                else:
                    msg("Email o password non validi", "error")
            else:
                msg("Inserisci email e password", "warning")
        st.markdown('<div style="margin-top:1rem;font-size:0.8rem;color:#9CA3AF;">'
                    'Primo accesso: usa le credenziali fornite dall\'amministratore</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ── Guard ────────────────────────────────────────────────────────
if not st.session_state.utente:
    st.session_state.pagina = "login"
    st.rerun()

db.aggiorna_accesso(st.session_state.utente["id"])

# ── DASHBOARD ───────────────────────────────────────────────────
if st.session_state.pagina == "dashboard":
    u = st.session_state.utente
    st.markdown(f'<div class="page-title">🏠 Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">Benvenuto, {u["nome"]}</div>', unsafe_allow_html=True)

    # Stats
    files = db.file_utente(u["id"])
    online = db.utenti_online()
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown(f'<div class="card"><h3 style="margin:0;color:#1E3A5F;">{len(files)}</h3>'
                    f'<div style="color:#6B7280;font-size:0.85rem;">File Excel caricati</div></div>',
                    unsafe_allow_html=True)
    with col_s2:
        tot = sum(f["righe"] for f in files)
        st.markdown(f'<div class="card"><h3 style="margin:0;color:#1E3A5F;">{tot}</h3>'
                    f'<div style="color:#6B7280;font-size:0.85rem;">Record totali</div></div>',
                    unsafe_allow_html=True)
    with col_s3:
        st.markdown(f'<div class="card"><h3 style="margin:0;color:#1E3A5F;">{len(online)}</h3>'
                    f'<div style="color:#6B7280;font-size:0.85rem;">Utenti online</div></div>',
                    unsafe_allow_html=True)

    st.divider()

    # Online users
    st.markdown("#### 👥 Utenti online")
    if online:
        for ou in online:
            col_img, col_nome = st.columns([0.5, 3])
            with col_img:
                st.markdown(
                    f'<div class="user-avatar" style="background:{ou["avatar_color"]}">{iniziali(ou["nome"])}</div>',
                    unsafe_allow_html=True,
                )
            with col_nome:
                st.markdown(f"**{ou['nome']}**  ·  {ou['email']}")
    else:
        st.caption("Nessun altro utente online")

    st.divider()

    # Recent files
    st.markdown("#### 📁 I tuoi file")
    if files:
        for f in files:
            cols = st.columns([2.5, 1, 1, 1.2, 0.5])
            with cols[0]:
                st.markdown(f"**{f['nome_file']}**")
                st.caption(os.path.dirname(f["percorso"]))
            with cols[1]:
                st.markdown(f"📄 {f['foglio']}")
            with cols[2]:
                st.markdown(f"{f['righe']} righe")
            with cols[3]:
                st.markdown(f"🕐 {f['caricato_il'][:10] if f['caricato_il'] else ''}")
            with cols[4]:
                if st.button("▶️", key=f"dash_open_{f['id']}", help="Apri"):
                    st.session_state.file_id = f["id"]
                    st.session_state.pagina = "vedi_file"
                    st.rerun()
    else:
        st.info("Nessun file caricato. Vai su **Carica Excel** per iniziare.")

# ── CARICA EXCEL ────────────────────────────────────────────────
elif st.session_state.pagina == "carica":
    st.markdown('<div class="page-title">📂 Carica file Excel</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Importa un file Excel nel database</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Carica file Excel", type=["xlsx", "xls"], label_visibility="collapsed")
    if uploaded:
        try:
            contenuto = uploaded.read()
            uploaded.seek(0)
            df = pd.read_excel(uploaded, sheet_name=0, engine='openpyxl')
            if df.empty:
                msg("Il file è vuoto", "warning")
            else:
                nome = uploaded.name
                fid = db.salva_file_excel(st.session_state.utente["id"], nome,
                                          "Sheet1", list(df.columns), len(df), contenuto)
                db.init_data_table(fid, df)
                db.init_campi_config(fid, list(df.columns))
                st.session_state.file_id = fid
                msg(f"✅ Importati {len(df)} record da '{nome}'")
                st.session_state.pagina = "vedi_file"
                st.rerun()
        except Exception as e:
            msg(f"Errore: {e}", "error")

    st.divider()
    st.markdown("#### File caricati in precedenza")
    files = db.file_utente(st.session_state.utente["id"])
    if files:
        for f in files:
            cols = st.columns([3, 1, 1, 0.5])
            with cols[0]:
                st.markdown(f"**{f['nome_file']}**  \n{f['percorso']}")
            with cols[1]:
                st.markdown(f"📄 {f['foglio']}  ·  {f['righe']} righe")
            with cols[2]:
                if st.button("📌 Apri", key=f"carica_open_{f['id']}"):
                    st.session_state.file_id = f["id"]
                    st.session_state.pagina = "vedi_file"
                    st.rerun()
            with cols[3]:
                if st.button("🗑️", key=f"carica_del_{f['id']}", help="Elimina"):
                    db.elimina_file(f["id"])
                    msg(f"File '{f['nome_file']}' rimosso")
                    st.rerun()
    else:
        st.info("Nessun file caricato")

# ── VEDI FILE ───────────────────────────────────────────────────
elif st.session_state.pagina in ("vedi_file", "aggiungi_record", "modifica_record", "dettaglio_record"):
    fid = st.session_state.file_id
    if fid is None:
        msg("Nessun file selezionato", "warning")
        st.session_state.pagina = "dashboard"
        st.rerun()

    # Get file info
    files = db.file_utente(st.session_state.utente["id"])
    info = next((f for f in files if f["id"] == fid), None)
    if not info:
        msg("File non trovato", "error")
        st.session_state.pagina = "dashboard"
        st.rerun()

    col_tit, col_back = st.columns([3, 1])
    with col_tit:
        st.markdown(f'<div class="page-title">📊 {info["nome_file"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="page-sub">{info["percorso"]}  ·  {info["foglio"]}  ·  {info["righe"]} righe</div>',
                     unsafe_allow_html=True)
    with col_back:
        if st.button("🏠  Dashboard", use_container_width=True):
            cambia_pagina("dashboard")

    df = db.carica_dati(fid)
    if df is None or df.empty:
        st.warning("Nessun dato disponibile")
        st.stop()

    colonne_dati = [c for c in df.columns if c != "id"]

    # ── MODIFICA / AGGIUNGI ──
    if st.session_state.pagina == "modifica_record" or st.session_state.pagina == "aggiungi_record":
        is_new = st.session_state.pagina == "aggiungi_record"
        titolo = "➕ Nuovo record" if is_new else f"✏️ Modifica record #{st.session_state.modifica_id}"
        st.markdown(f"#### {titolo}")

        campi_config = db.get_campi_config(fid)
        if not campi_config:
            campi_config = [{"id": 0, "nome_campo": c, "tipo_campo": "text", "obbligatorio": False, "opzioni": None} for c in colonne_dati]

        rec = None
        if not is_new:
            rec_df = df[df["id"] == st.session_state.modifica_id]
            if not rec_df.empty:
                rec = rec_df.iloc[0]

        vals = {}
        errori = {}
        for cfg in campi_config:
            c = cfg["nome_campo"]
            if c not in colonne_dati:
                continue
            dv = rec[c] if rec is not None and pd.notna(rec[c]) else None
            tipo = cfg["tipo_campo"]
            obbl = cfg["obbligatorio"]
            etichetta = f"{c} *" if obbl else c
            opts = cfg.get("opzioni") or []

            if tipo == "number":
                vals[c] = st.number_input(etichetta, value=float(dv) if dv is not None else None, step=0.01, format="%f", key=f"f_{c}")
            elif tipo == "date":
                vals[c] = st.date_input(etichetta, value=pd.to_datetime(dv) if dv is not None else None, key=f"f_{c}")
            elif tipo == "boolean":
                vals[c] = st.checkbox(etichetta, value=bool(dv) if dv is not None else False, key=f"f_{c}")
            elif tipo == "single_select":
                idx = opts.index(str(dv)) if dv is not None and str(dv) in opts else 0
                vals[c] = st.selectbox(etichetta, opts if opts else [""], index=idx, key=f"f_{c}")
            elif tipo == "multi_select":
                current = str(dv).split(",") if dv else []
                selected = st.multiselect(etichetta, opts if opts else [], default=[s for s in current if s in opts], key=f"f_{c}")
                vals[c] = ",".join(selected)
            elif tipo == "text_area":
                vals[c] = st.text_area(etichetta, value=str(dv) if dv is not None else "", key=f"f_{c}")
            else:
                vals[c] = st.text_input(etichetta, value=str(dv) if dv is not None else "", key=f"f_{c}")

            if obbl:
                v = vals[c]
                if v is None or (isinstance(v, str) and v.strip() == "") or (isinstance(v, float) and pd.isna(v)):
                    errori[c] = True

        if errori:
            msg("Compila tutti i campi obbligatori (*)", "warning")

        ca, cb = st.columns([1, 1])
        with ca:
            lbl = "💾 Aggiungi" if is_new else "💾 Salva modifiche"
            if st.button(lbl, use_container_width=True, type="primary"):
                if errori:
                    st.rerun()
                safe_vals = {}
                for c in colonne_dati:
                    v = vals.get(c)
                    if isinstance(v, str) and v.strip() == "":
                        safe_vals[c] = None
                    elif isinstance(v, bool):
                        safe_vals[c] = 1 if v else 0
                    else:
                        safe_vals[c] = v
                if is_new:
                    db.aggiungi_record(fid, safe_vals)
                    msg("✅ Record aggiunto")
                else:
                    db.aggiorna_record(fid, st.session_state.modifica_id, safe_vals)
                    msg(f"✅ Record #{st.session_state.modifica_id} aggiornato")
                st.session_state.pagina = "vedi_file"
                st.rerun()
        with cb:
            if st.button("Annulla", use_container_width=True):
                st.session_state.pagina = "vedi_file"
                st.rerun()
        st.stop()

    # ── VEDI DETTAGLIO ──
    if st.session_state.pagina == "dettaglio_record":
        rid = st.session_state.vedi_id
        rec_df = df[df["id"] == rid]
        if rec_df.empty:
            msg("Record non trovato", "error")
            st.session_state.pagina = "vedi_file"
            st.rerun()
        rec = rec_df.iloc[0]
        st.markdown(f"#### 👁️ Record #{rid}")
        for c in colonne_dati:
            v = rec[c]
            v = "—" if pd.isna(v) else v
            st.markdown(f"**{c}:** {v}")
        st.divider()
        ce1, ce2, ce3 = st.columns([1, 1, 1])
        with ce1:
            if st.button("✏️ Modifica", use_container_width=True):
                st.session_state.modifica_id = rid
                st.session_state.pagina = "modifica_record"
                st.rerun()
        with ce2:
            if st.button("🗑️ Elimina", use_container_width=True):
                db.elimina_record(fid, rid)
                msg(f"✅ Record #{rid} eliminato")
                st.session_state.pagina = "vedi_file"
                st.rerun()
        with ce3:
            if st.button("🔙 Indietro", use_container_width=True):
                st.session_state.pagina = "vedi_file"
                st.rerun()
        st.stop()

    # ── TOOLBAR ──
    tb = st.columns([2, 1.3, 1.3, 0.8, 0.8, 0.8, 0.5])
    with tb[0]:
        s = st.text_input("🔍 Cerca", value=st.session_state.ricerca,
                          placeholder="Cerca in tutto...", label_visibility="collapsed")
        if s != st.session_state.ricerca:
            st.session_state.ricerca = s
            st.rerun()
    with tb[1]:
        fc = st.selectbox("Colonna", [""] + colonne_dati, label_visibility="collapsed",
                          index=0 if not st.session_state.filtro_col
                          else (colonne_dati.index(st.session_state.filtro_col) + 1) if st.session_state.filtro_col in colonne_dati else 0)
        if fc != st.session_state.filtro_col:
            st.session_state.filtro_col = fc
            st.session_state.filtro_val = ""
            st.rerun()
    with tb[2]:
        if st.session_state.filtro_col:
            fv = st.text_input("Valore", value=st.session_state.filtro_val,
                               placeholder="Filtra...", label_visibility="collapsed")
            if fv != st.session_state.filtro_val:
                st.session_state.filtro_val = fv
                st.rerun()
    with tb[3]:
        if st.button("➕ Nuovo", use_container_width=True):
            st.session_state.pagina = "aggiungi_record"
            st.rerun()
    with tb[4]:
        if st.button("📥 Export", use_container_width=True, help="Esporta in Excel"):
            percorso = info["percorso"]
            if db.esporta_excel(fid, percorso):
                msg(f"✅ Dati esportati in '{percorso}'")
            else:
                msg("Errore durante l'esportazione", "error")
            st.rerun()
    with tb[5]:
        if st.button("⚙️ Campi", use_container_width=True, help="Configura campi"):
            st.session_state.pagina = "configura_campi"
            st.rerun()
    with tb[6]:
        if st.button("🔄", use_container_width=True, help="Ricarica dati"):
            try:
                buf, foglio_db = db.get_file_contenuto(fid)
                if buf:
                    foglio_sn = info.get("foglio", 0)
                    if foglio_sn == "Sheet1":
                        foglio_sn = 0
                    df_new = pd.read_excel(buf, sheet_name=foglio_sn, engine='openpyxl')
                else:
                    df_new = pd.read_excel(info["percorso"], sheet_name=info["foglio"] if info["foglio"] != "Sheet1" else 0, engine='openpyxl')
                db.init_data_table(fid, df_new)
                msg("✅ Dati ricaricati dal file Excel")
            except Exception as e:
                msg(f"Errore: {e}", "error")
            st.rerun()

    # ── FILTER ──
    view_df = df
    if st.session_state.ricerca:
        q = st.session_state.ricerca.lower()
        mask = view_df[colonne_dati].astype(str).apply(lambda x: x.str.lower().str.contains(q, na=False)).any(axis=1)
        view_df = view_df[mask]

    if st.session_state.filtro_col and st.session_state.filtro_val:
        c = st.session_state.filtro_col
        v = st.session_state.filtro_val
        if c in view_df.columns:
            view_df = view_df[view_df[c].astype(str).str.contains(v, case=False, na=False)]

    total = len(view_df)
    st.caption(f"{total} record{' (filtrati da ' + str(len(df)) + ' totali)' if total != len(df) else ''}")

    if view_df.empty:
        st.warning("Nessun record trovato")
        st.stop()

    # ── TABLE ──
    display_cols = colonne_dati
    ev = st.dataframe(
        view_df[["id"] + display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={"id": "ID"},
        on_select="rerun",
        selection_mode="single-row",
    )

    # ── ACTIONS ──
    if ev.selection and ev.selection.rows:
        sel_idx = view_df.index[ev.selection.rows[0]]
        sel = view_df.loc[sel_idx]
        rid = int(sel["id"])

        st.divider()
        st.markdown(f"**Record #{rid}** selezionato")
        # preview
        preview = sel[display_cols[:min(4, len(display_cols))]]
        for c, v in preview.items():
            v = "—" if pd.isna(v) else v
            st.markdown(f"**{c}:** {v}")
        if len(display_cols) > 4:
            st.caption(f"+ {len(display_cols) - 4} campi")

        ac1, ac2, ac3, ac4 = st.columns([1, 1, 1, 6])
        with ac1:
            if st.button("👁️ Vedi", use_container_width=True):
                st.session_state.vedi_id = rid
                st.session_state.pagina = "dettaglio_record"
                st.rerun()
        with ac2:
            if st.button("✏️ Modifica", use_container_width=True):
                st.session_state.modifica_id = rid
                st.session_state.pagina = "modifica_record"
                st.rerun()
        with ac3:
            if st.button("🗑️ Elimina", use_container_width=True):
                db.elimina_record(fid, rid)
                msg(f"✅ Record #{rid} eliminato")
                st.rerun()
    else:
        st.info("👆 Seleziona una riga per vedere le azioni")

# ── CONFIGURA CAMPI ─────────────────────────────────────────────
elif st.session_state.pagina == "configura_campi":
    fid = st.session_state.file_id
    if fid is None:
        msg("Nessun file selezionato", "warning")
        st.session_state.pagina = "dashboard"
        st.rerun()

    st.markdown(f'<div class="page-title">⚙️ Configura campi</div>', unsafe_allow_html=True)
    if st.button("🔙 Torna al file", use_container_width=False):
        st.session_state.pagina = "vedi_file"
        st.rerun()
    st.divider()

    campi = db.get_campi_config(fid)
    if not campi:
        st.info("Nessuna configurazione trovata")
        st.stop()

    for campo in campi:
        with st.container():
            cols = st.columns([2, 1.5, 0.8, 1.5, 0.5])
            with cols[0]:
                st.markdown(f"**{campo['nome_campo']}**")
            with cols[1]:
                tipo = st.selectbox(
                    "Tipo",
                    ["text", "text_area", "number", "date", "single_select", "multi_select", "boolean"],
                    index=["text", "text_area", "number", "date", "single_select", "multi_select", "boolean"].index(campo["tipo_campo"]) if campo["tipo_campo"] in ["text", "text_area", "number", "date", "single_select", "multi_select", "boolean"] else 0,
                    key=f"tipo_{campo['id']}",
                    label_visibility="collapsed",
                )
            with cols[2]:
                obbl = st.checkbox("Obbligatorio", value=campo["obbligatorio"], key=f"obbl_{campo['id']}",
                                   label_visibility="collapsed")
            with cols[3]:
                if tipo in ("single_select", "multi_select"):
                    current_opts = ", ".join(campo.get("opzioni", [])) if campo.get("opzioni") else ""
                    opts_str = st.text_input("Opzioni (separate da virgola)", value=current_opts,
                                             key=f"opts_{campo['id']}", label_visibility="collapsed",
                                             placeholder="Opzione1, Opzione2, ...")
                else:
                    opts_str = None
                    st.markdown("—")
            with cols[4]:
                if st.button("💾", key=f"save_cfg_{campo['id']}", help="Salva"):
                    new_opzioni = [o.strip() for o in opts_str.split(",")] if opts_str and opts_str.strip() else None
                    db.aggiorna_campo_config(campo["id"], tipo_campo=tipo, obbligatorio=obbl, opzioni=new_opzioni)
                    msg(f"Campo '{campo['nome_campo']}' aggiornato")
                    st.rerun()
            st.divider()

# ── GESTIONE UTENTI (admin only) ────────────────────────────────
elif st.session_state.pagina == "utenti":
    if st.session_state.utente["ruolo"] != "admin":
        msg("Accesso non autorizzato", "error")
        cambia_pagina("dashboard")

    st.markdown('<div class="page-title">👥 Gestione Utenti</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Crea e gestisci gli account utente</div>', unsafe_allow_html=True)

    with st.expander("➕ Crea nuovo utente", expanded=False):
        with st.form("nuovo_utente"):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome completo")
                email_nuovo = st.text_input("Email")
            with col2:
                pw = st.text_input("Password", type="password")
                ruolo = st.selectbox("Ruolo", ["utente", "admin"])
            if st.form_submit_button("Crea utente", use_container_width=True, type="primary"):
                if nome and email_nuovo and pw:
                    ok, msg_text = db.crea_utente(email_nuovo, nome, pw, ruolo)
                    if ok:
                        msg(msg_text)
                        st.rerun()
                    else:
                        msg(msg_text, "error")
                else:
                    msg("Compila tutti i campi", "warning")

    st.divider()
    st.markdown("#### Elenco utenti")
    utenti = db.lista_utenti()
    for ut in utenti:
        is_online = ut["ultimo_accesso"] and (datetime.now() - datetime.strptime(ut["ultimo_accesso"][:19], "%Y-%m-%d %H:%M:%S")).seconds < 120
        cols = st.columns([2, 2, 1, 0.5, 0.5])
        with cols[0]:
            st.markdown(f"**{ut['nome']}**")
        with cols[1]:
            st.markdown(ut["email"])
        with cols[2]:
            badge = "🟢 Online" if is_online else "⚪ Offline"
            st.markdown(badge)
        with cols[3]:
            st.markdown(f"`{ut['ruolo']}`")
        with cols[4]:
            if ut["email"] != "s.galvis@setinstudio.com":
                if st.button("🗑️", key=f"del_user_{ut['id']}", help="Elimina"):
                    db.elimina_utente(ut["id"])
                    msg(f"Utente {ut['nome']} eliminato")
                    st.rerun()
