import sqlite3
import hashlib
import os
import json
import uuid as _uuid
import pandas as pd
from datetime import datetime
from pathlib import Path

DB_DIR = Path(__file__).parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "sygs.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def init_db(admin_email=None, admin_nome=None, admin_password=None):
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            password TEXT NOT NULL,
            ruolo TEXT DEFAULT 'utente',
            creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_accesso TIMESTAMP,
            avatar_color TEXT DEFAULT '#1E3A5F'
        );
        CREATE TABLE IF NOT EXISTS file_excel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utente_id INTEGER NOT NULL,
            percorso TEXT NOT NULL,
            nome_file TEXT NOT NULL,
            foglio TEXT DEFAULT 'Sheet1',
            colonne TEXT,
            righe INTEGER DEFAULT 0,
            contenuto BLOB,
            caricato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (utente_id) REFERENCES utenti(id) ON DELETE CASCADE
        );
    """)
    try:
        conn.execute("ALTER TABLE file_excel ADD COLUMN contenuto BLOB")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE file_excel ADD COLUMN ordine INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campi_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            nome_campo TEXT NOT NULL,
            tipo_campo TEXT DEFAULT 'text',
            obbligatorio INTEGER DEFAULT 0,
            opzioni TEXT,
            ordine INTEGER DEFAULT 0,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE
        );
    """)
    try:
        conn.execute("ALTER TABLE campi_config ADD COLUMN opzioni TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE campi_config ADD COLUMN mostra_modulo INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE campi_config ADD COLUMN valore_predefinito TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE campi_config ADD COLUMN validazione_unico INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE campi_config ADD COLUMN validazione_min TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE campi_config ADD COLUMN validazione_max TEXT")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS filtri_salvati (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            filtri TEXT NOT NULL,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permessi_file (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utente_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            colonne_visibili TEXT,
            filtro_righe TEXT,
            UNIQUE(utente_id, file_id),
            FOREIGN KEY (utente_id) REFERENCES utenti(id) ON DELETE CASCADE,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessioni (
            sid TEXT PRIMARY KEY,
            dati TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_accesso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires TIMESTAMP
        )
    """)
    # Migrazione per DB vecchi senza colonna ultimo_accesso (PRIMA del DELETE)
    try:
        conn.execute("SELECT ultimo_accesso FROM sessioni LIMIT 1")
    except Exception:
        conn.execute("DROP TABLE IF EXISTS sessioni")
        conn.execute("""
            CREATE TABLE sessioni (
                sid TEXT PRIMARY KEY,
                dati TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultimo_accesso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires TIMESTAMP
            )
        """)
    conn.execute("DELETE FROM sessioni WHERE expires < datetime('now') OR ultimo_accesso < datetime('now', '-1 day')")
    conn.commit()
    conn.close()


def conta_utenti() -> int:
    conn = get_conn()
    cnt = conn.execute("SELECT COUNT(*) as n FROM utenti").fetchone()["n"]
    conn.close()
    return cnt


def init_log_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS log_modifiche (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            record_id INTEGER,
            utente_id INTEGER NOT NULL,
            azione TEXT NOT NULL,
            dettaglio TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE,
            FOREIGN KEY (utente_id) REFERENCES utenti(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            record_id INTEGER NOT NULL,
            utente_id INTEGER NOT NULL,
            testo TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE,
            FOREIGN KEY (utente_id) REFERENCES utenti(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def log_azione(file_id, record_id, utente_id, azione, dettaglio=""):
    init_log_table()
    conn = get_conn()
    conn.execute("INSERT INTO log_modifiche (file_id, record_id, utente_id, azione, dettaglio) VALUES (?,?,?,?,?)",
                 (file_id, record_id, utente_id, azione, dettaglio))
    conn.commit()
    conn.close()


def get_log(file_id, limit=50):
    init_log_table()
    conn = get_conn()
    rows = conn.execute("""
        SELECT l.*, u.nome as utente_nome
        FROM log_modifiche l
        LEFT JOIN utenti u ON u.id = l.utente_id
        WHERE l.file_id = ?
        ORDER BY l.created DESC
        LIMIT ?
    """, (file_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def aggiungi_commento(file_id, record_id, utente_id, testo):
    init_log_table()
    conn = get_conn()
    conn.execute("INSERT INTO commenti (file_id, record_id, utente_id, testo) VALUES (?,?,?,?)",
                 (file_id, record_id, utente_id, testo))
    conn.commit()
    conn.close()


def get_commenti(file_id, record_id):
    init_log_table()
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.*, u.nome as utente_nome
        FROM commenti c
        LEFT JOIN utenti u ON u.id = c.utente_id
        WHERE c.file_id = ? AND c.record_id = ?
        ORDER BY c.created ASC
    """, (file_id, record_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Auth ──

def get_utente_by_email(email: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, email, nome, ruolo, avatar_color FROM utenti WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Sessioni server-side (DB, sopravvivono a F5 e restart) ──


def _pulisci_sessioni_scadute():
    conn = get_conn()
    conn.execute("DELETE FROM sessioni WHERE expires < datetime('now')")
    conn.commit()
    conn.close()


def crea_sessione(dati_utente: dict, giorni: int = 7) -> str:
    sid = _uuid.uuid4().hex
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessioni (sid, dati, expires, ultimo_accesso) VALUES (?, ?, datetime('now', '+' || ? || ' days'), CURRENT_TIMESTAMP)",
        (sid, json.dumps(dati_utente), giorni),
    )
    conn.commit()
    conn.close()
    return sid


def leggi_sessione(sid: str):
    conn = get_conn()
    # Scadenza per inattività 30 min OPPURE expires assoluto
    row = conn.execute(
        "SELECT dati FROM sessioni WHERE sid = ? AND expires > datetime('now')"
        " AND ultimo_accesso > datetime('now', '-30 minutes')",
        (sid,),
    ).fetchone()
    conn.close()
    return json.loads(row["dati"]) if row else None


def elimina_sessione(sid: str):
    conn = get_conn()
    conn.execute("DELETE FROM sessioni WHERE sid = ?", (sid,))
    conn.commit()
    conn.close()


def aggiorna_accesso_sessione(sid: str):
    conn = get_conn()
    conn.execute("UPDATE sessioni SET ultimo_accesso = CURRENT_TIMESTAMP WHERE sid = ?", (sid,))
    conn.commit()
    conn.close()


def login(email: str, password: str):
    conn = get_conn()
    cur = conn.execute(
        "SELECT id, email, nome, ruolo, avatar_color FROM utenti WHERE email = ? AND password = ?",
        (email, hash_pw(password)),
    )
    row = cur.fetchone()
    if row:
        conn.execute("UPDATE utenti SET ultimo_accesso = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


def lista_utenti():
    conn = get_conn()
    rows = conn.execute("SELECT id, email, nome, ruolo, ultimo_accesso FROM utenti ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crea_utente(email: str, nome: str, password: str, ruolo: str = "utente"):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO utenti (email, nome, password, ruolo) VALUES (?, ?, ?, ?)",
                     (email, nome, hash_pw(password), ruolo))
        conn.commit()
        return True, "Utente creato con successo"
    except sqlite3.IntegrityError:
        return False, "Email già esistente"
    finally:
        conn.close()


def elimina_utente(uid: int):
    conn = get_conn()
    conn.execute("DELETE FROM utenti WHERE id = ?", (uid,))
    conn.commit()
    conn.close()


def cambia_password(uid: int, nuova_pw: str):
    conn = get_conn()
    conn.execute("UPDATE utenti SET password = ? WHERE id = ?", (hash_pw(nuova_pw), uid))
    conn.commit()
    conn.close()


def utenti_online(entro_secondi: int = 120):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, email, nome, avatar_color FROM utenti WHERE ultimo_accesso >= datetime('now', ? || ' seconds')",
        (f"-{entro_secondi}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def aggiorna_accesso(uid: int):
    conn = get_conn()
    conn.execute("UPDATE utenti SET ultimo_accesso = CURRENT_TIMESTAMP WHERE id = ?", (uid,))
    conn.commit()
    conn.close()


# ── File Excel ──

def salva_file_excel(utente_id: int, nome_file: str, foglio: str, colonne: list, righe: int, contenuto: bytes = None):
    conn = get_conn()
    cur = conn.execute("SELECT id FROM file_excel WHERE utente_id = ? AND nome_file = ?", (utente_id, nome_file))
    existing = cur.fetchone()
    if existing:
        conn.execute(
            "UPDATE file_excel SET foglio=?, colonne=?, righe=?, contenuto=COALESCE(?, contenuto), caricato_il=CURRENT_TIMESTAMP WHERE id=?",
            (foglio, ",".join(colonne), righe, contenuto, existing["id"]),
        )
        fid = existing["id"]
    else:
        max_ord = conn.execute("SELECT COALESCE(MAX(ordine),0) as mx FROM file_excel WHERE utente_id = ?", (utente_id,)).fetchone()["mx"]
        cur = conn.execute(
            "INSERT INTO file_excel (utente_id, percorso, nome_file, foglio, colonne, righe, contenuto, ordine) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (utente_id, nome_file, nome_file, foglio, ",".join(colonne), righe, contenuto, max_ord + 1),
        )
        fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid


def file_utente(utente_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, percorso, nome_file, foglio, colonne, righe, caricato_il, ordine FROM file_excel WHERE utente_id = ? ORDER BY ordine, caricato_il",
        (utente_id,),
    ).fetchall()
    user_rows = conn.execute(
        "SELECT fe.id, fe.percorso, fe.nome_file, fe.foglio, fe.colonne, fe.righe, fe.caricato_il, 9999 as ordine "
        "FROM permessi_file pf JOIN file_excel fe ON pf.file_id = fe.id WHERE pf.utente_id = ?", (utente_id,)
    ).fetchall()
    conn.close()
    seen = set(r["id"] for r in rows)
    for r in user_rows:
        if r["id"] not in seen:
            rows.append(r)
    return [dict(r) for r in rows]


def aggiorna_ordine_file(fid: int, nuovo_ordine: int):
    conn = get_conn()
    conn.execute("UPDATE file_excel SET ordine = ? WHERE id = ?", (nuovo_ordine, fid))
    conn.commit()
    conn.close()


def esporta_file_excel(fid: int) -> bytes:
    conn = get_conn()
    row = conn.execute("SELECT contenuto FROM file_excel WHERE id = ?", (fid,)).fetchone()
    conn.close()
    if row and row["contenuto"]:
        return bytes(row["contenuto"])
    return None


def get_file_contenuto(fid: int):
    conn = get_conn()
    row = conn.execute("SELECT contenuto, percorso, foglio FROM file_excel WHERE id = ?", (fid,)).fetchone()
    conn.close()
    if row and row["contenuto"]:
        import io
        return io.BytesIO(row["contenuto"]), row["foglio"]
    return None, None


def rinumera_ordini(utente_id: int):
    """Renumerà ordine 0,1,2,… per tutti i file dell'utente."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id FROM file_excel WHERE utente_id = ? ORDER BY ordine, id",
        (utente_id,),
    ).fetchall()
    for i, r in enumerate(rows):
        conn.execute("UPDATE file_excel SET ordine = ? WHERE id = ?", (i, r["id"]))
    conn.commit()
    conn.close()


def elimina_file(fid: int):
    conn = get_conn()
    conn.execute(f"DROP TABLE IF EXISTS [dati_{fid}]")
    conn.execute("DELETE FROM file_excel WHERE id = ?", (fid,))
    conn.commit()
    conn.close()


# ── Configurazione Campi ──

def init_campi_config(file_id: int, colonne: list):
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) as cnt FROM campi_config WHERE file_id = ?", (file_id,)).fetchone()
    if existing and existing["cnt"] > 0:
        conn.close()
        return
    for i, c in enumerate(colonne):
        conn.execute(
            "INSERT INTO campi_config (file_id, nome_campo, tipo_campo, obbligatorio, ordine) VALUES (?, ?, 'text', 0, ?)",
            (file_id, c, i),
        )
    conn.commit()
    conn.close()


def prossimo_valore_auto(file_id: int, nome_campo: str) -> int:
    conn = get_conn()
    table = f"dati_{file_id}"
    row = conn.execute(f'SELECT MAX(CAST("{nome_campo}" AS INTEGER)) as mx FROM [{table}]').fetchone()
    conn.close()
    return (row["mx"] or 0) + 1


def duplica_record(file_id: int, record_id: int, utente_id: int = None) -> int:
    conn = get_conn()
    table = f"dati_{file_id}"
    row = conn.execute(f"SELECT * FROM [{table}] WHERE id = ?", (record_id,)).fetchone()
    if not row:
        conn.close()
        return None
    d = dict(row)
    d.pop("id", None)
    d.pop("creato_il", None)
    d["creato_da"] = utente_id
    cols = ", ".join(f'"{k}"' for k in d)
    placeholders = ", ".join(["?" for _ in d])
    cur = conn.execute(f"INSERT INTO [{table}] ({cols}) VALUES ({placeholders})", list(d.values()))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def salva_validazione(file_id: int, nome_campo: str, unico: bool = False, minimo: str = None, massimo: str = None):
    conn = get_conn()
    conn.execute("""
        UPDATE campi_config SET validazione_unico=?, validazione_min=?, validazione_max=?
        WHERE file_id=? AND nome_campo=?
    """, (1 if unico else 0, minimo, massimo, file_id, nome_campo))
    conn.commit()
    conn.close()


def get_validazioni(file_id: int) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT nome_campo, validazione_unico, validazione_min, validazione_max FROM campi_config WHERE file_id=?",
        (file_id,),
    ).fetchall()
    conn.close()
    result = {}
    for r in rows:
        result[r["nome_campo"]] = {
            "unico": bool(r["validazione_unico"]),
            "min": r["validazione_min"],
            "max": r["validazione_max"],
        }
    return result


def valida_record(file_id: int, valori: dict, exclude_id: int = None) -> list:
    validazioni = get_validazioni(file_id)
    errori = []
    campi = get_campi_config(file_id)
    campi_map = {c["nome_campo"]: c for c in campi}
    for campo, v in valori.items():
        cfg = campi_map.get(campo, {})
        val = str(v) if v is not None and v != "" else ""
        if cfg.get("obbligatorio"):
            if not val.strip():
                errori.append(f"'{campo}' e obbligatorio")
        if cfg.get("validazione_unico") and val.strip():
            conn = get_conn()
            table = f"dati_{file_id}"
            if exclude_id:
                row = conn.execute(f'SELECT id FROM [{table}] WHERE "{campo}"=? AND id!=?', (val, exclude_id)).fetchone()
            else:
                row = conn.execute(f'SELECT id FROM [{table}] WHERE "{campo}"=?', (val,)).fetchone()
            conn.close()
            if row:
                errori.append(f"'{campo}' deve essere unico (gia usato da #{row['id']})")
        if cfg.get("validazione_min") and val.strip():
            try:
                if float(val) < float(cfg["validazione_min"]):
                    errori.append(f"'{campo}' minimo {cfg['validazione_min']}")
            except ValueError:
                pass
        if cfg.get("validazione_max") and val.strip():
            try:
                if float(val) > float(cfg["validazione_max"]):
                    errori.append(f"'{campo}' massimo {cfg['validazione_max']}")
            except ValueError:
                pass
    return errori


def get_campi_config(file_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, nome_campo, tipo_campo, obbligatorio, opzioni, mostra_modulo, valore_predefinito, validazione_unico, validazione_min, validazione_max FROM campi_config WHERE file_id = ? ORDER BY ordine",
        (file_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d["opzioni"]:
            import json
            d["opzioni"] = json.loads(d["opzioni"])
        d["obbligatorio"] = bool(d["obbligatorio"])
        d["mostra_modulo"] = bool(d["mostra_modulo"])
        d["validazione_unico"] = bool(d["validazione_unico"]) if d["validazione_unico"] else False
        result.append(d)
    return result


def aggiorna_campo_config(config_id: int, tipo_campo: str = None, obbligatorio: bool = None, opzioni: list = None, mostra_modulo: bool = None, valore_predefinito: str = None):
    conn = get_conn()
    sets = []
    params = []
    if tipo_campo is not None:
        sets.append("tipo_campo = ?")
        params.append(tipo_campo)
    if obbligatorio is not None:
        sets.append("obbligatorio = ?")
        params.append(1 if obbligatorio else 0)
    if opzioni is not None:
        import json
        sets.append("opzioni = ?")
        params.append(json.dumps(opzioni))
    if mostra_modulo is not None:
        sets.append("mostra_modulo = ?")
        params.append(1 if mostra_modulo else 0)
    if valore_predefinito is not None:
        sets.append("valore_predefinito = ?")
        params.append(valore_predefinito)
    if sets:
        conn.execute(f"UPDATE campi_config SET {', '.join(sets)} WHERE id = ?", params + [config_id])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS log_modifiche (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            record_id INTEGER,
            utente_id INTEGER NOT NULL,
            azione TEXT NOT NULL,
            dettaglio TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE,
            FOREIGN KEY (utente_id) REFERENCES utenti(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            record_id INTEGER NOT NULL,
            utente_id INTEGER NOT NULL,
            testo TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE,
            FOREIGN KEY (utente_id) REFERENCES utenti(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def aggiungi_colonna(file_id: int, nome_colonna: str, tipo_campo: str = "text"):
    conn = get_conn()
    table = f"dati_{file_id}"
    safe = nome_colonna.strip().replace(" ", "_").replace("'", "").replace('"', "").replace(".", "_")
    sql_type = "REAL" if tipo_campo == "number" else "TEXT"
    conn.execute(f"ALTER TABLE [{table}] ADD COLUMN \"{safe}\" {sql_type}")
    max_ord = conn.execute("SELECT COALESCE(MAX(ordine), -1) as mx FROM campi_config WHERE file_id = ?", (file_id,)).fetchone()["mx"]
    conn.execute(
        "INSERT INTO campi_config (file_id, nome_campo, tipo_campo, obbligatorio, ordine) VALUES (?, ?, ?, 0, ?)",
        (file_id, nome_colonna, tipo_campo, max_ord + 1),
    )
    conn.commit()
    conn.close()


def elimina_colonna(file_id: int, config_id: int, nome_colonna: str):
    conn = get_conn()
    table = f"dati_{file_id}"
    conn.execute("DELETE FROM campi_config WHERE id = ?", (config_id,))
    try:
        conn.execute(f"ALTER TABLE [{table}] DROP COLUMN \"{nome_colonna}\"")
    except Exception:
        pass
    conn.commit()
    conn.close()


def rinomina_colonna(file_id: int, vecchio_nome: str, nuovo_nome: str):
    conn = get_conn()
    table = f"dati_{file_id}"
    safe_new = nuovo_nome.strip().replace(" ", "_").replace("'", "").replace('"', "").replace(".", "_")
    conn.execute(f"ALTER TABLE [{table}] RENAME COLUMN \"{vecchio_nome}\" TO \"{safe_new}\"")
    conn.execute("UPDATE campi_config SET nome_campo = ? WHERE file_id = ? AND nome_campo = ?",
                 (nuovo_nome, file_id, vecchio_nome))
    conn.commit()
    conn.close()


# ── Permessi ──

def get_all_files():
    conn = get_conn()
    rows = conn.execute("SELECT id, nome_file, utente_id FROM file_excel ORDER BY nome_file").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_file_ids(utente_id: int, ruolo: str):
    if ruolo == "admin":
        conn = get_conn()
        rows = conn.execute("SELECT id FROM file_excel").fetchall()
        conn.close()
        return [r["id"] for r in rows]
    conn = get_conn()
    rows = conn.execute("SELECT file_id FROM permessi_file WHERE utente_id = ?", (utente_id,)).fetchall()
    conn.close()
    return [r["file_id"] for r in rows]


def can_edit(utente_id: int, ruolo: str, file_id: int) -> bool:
    if ruolo == "admin":
        return True
    conn = get_conn()
    row = conn.execute("SELECT modifica FROM permessi_file WHERE utente_id = ? AND file_id = ?",
                       (utente_id, file_id)).fetchone()
    conn.close()
    return bool(row and row["modifica"])


def get_permesso_file(utente_id: int, file_id: int):
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE permessi_file ADD COLUMN modifica INTEGER DEFAULT 0")
    except Exception:
        pass
    row = conn.execute("SELECT colonne_visibili, filtro_righe, modifica FROM permessi_file WHERE utente_id = ? AND file_id = ?",
                       (utente_id, file_id)).fetchone()
    conn.close()
    if not row:
        return None
    import json
    d = dict(row)
    d["modifica"] = bool(d["modifica"])
    if d["colonne_visibili"]:
        d["colonne_visibili"] = json.loads(d["colonne_visibili"])
    if d["filtro_righe"]:
        d["filtro_righe"] = json.loads(d["filtro_righe"])
    return d


def set_permesso_file(utente_id: int, file_id: int, colonne_visibili: list = None, filtro_righe: dict = None, modifica: bool = False):
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE permessi_file ADD COLUMN modifica INTEGER DEFAULT 0")
    except Exception:
        pass
    import json
    cv = json.dumps(colonne_visibili) if colonne_visibili else None
    fr = json.dumps(filtro_righe) if filtro_righe else None
    conn.execute("""
        INSERT INTO permessi_file (utente_id, file_id, colonne_visibili, filtro_righe, modifica)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(utente_id, file_id)
        DO UPDATE SET colonne_visibili=excluded.colonne_visibili, filtro_righe=excluded.filtro_righe, modifica=excluded.modifica
    """, (utente_id, file_id, cv, fr, 1 if modifica else 0))
    conn.commit()
    conn.close()


def elimina_permesso_file(utente_id: int, file_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM permessi_file WHERE utente_id = ? AND file_id = ?", (utente_id, file_id))
    conn.commit()
    conn.close()


# ── Dati (CRUD) ──

def init_data_table(file_id: int, df: pd.DataFrame):
    conn = get_conn()
    table = f"dati_{file_id}"
    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
    import re as _re
    def _sanitize(n):
        n = n.strip().replace(" ", "_")
        n = _re.sub(r'[^a-zA-Z0-9_]', '', n)
        if not n or n[0].isdigit():
            n = 'col_' + n
        return n or 'colonna'
    cols_def = []
    safe_cols = []
    for c in df.columns:
        safe = _sanitize(c)
        safe_cols.append(safe)
        if pd.api.types.is_numeric_dtype(df[c]):
            cols_def.append(f'"{safe}" REAL')
        elif pd.api.types.is_datetime64_any_dtype(df[c]):
            cols_def.append(f'"{safe}" TEXT')
        else:
            cols_def.append(f'"{safe}" TEXT')
    conn.execute(f'CREATE TABLE [{table}] (id INTEGER PRIMARY KEY AUTOINCREMENT, creato_da INTEGER, creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP, {", ".join(cols_def)})')
    placeholders = ", ".join(["?" for _ in df.columns])
    cols_insert = ", ".join(f'"{c}"' for c in safe_cols)
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                vals.append(None)
            elif pd.api.types.is_numeric_dtype(df[c]):
                vals.append(float(v))
            else:
                vals.append(str(v) if pd.notna(v) else None)
        conn.execute(f"INSERT INTO [{table}] ({cols_insert}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()
    return safe_cols


def init_data_table_vuoto(file_id: int, colonne: list) -> list:
    conn = get_conn()
    table = f"dati_{file_id}"
    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
    import re as _re
    def _sanitize(n):
        n = n.strip().replace(" ", "_")
        n = _re.sub(r'[^a-zA-Z0-9_]', '', n)
        if not n or n[0].isdigit():
            n = 'col_' + n
        return n or 'colonna'
    safe_list = [_sanitize(c) for c in colonne]
    cols_def = [f'"{s}" TEXT' for s in safe_list]
    conn.execute(f'CREATE TABLE [{table}] (id INTEGER PRIMARY KEY AUTOINCREMENT, creato_da INTEGER, creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP, {", ".join(cols_def)})')
    conn.commit()
    conn.close()
    return safe_list


def ricrea_tabella_da_config(file_id: int) -> list:
    """Ricrea la tabella dati dal campi_config (fallback se la tabella è assente)."""
    conn = get_conn()
    table = f"dati_{file_id}"
    campi = conn.execute("SELECT nome_campo, tipo_campo FROM campi_config WHERE file_id = ? ORDER BY ordine", (file_id,)).fetchall()
    if not campi:
        conn.close()
        return []
    safe_cols = []
    cols_def = []
    for r in campi:
        n = r["nome_campo"]
        import re as _re
        safe = n.strip().replace(" ", "_")
        safe = _re.sub(r'[^a-zA-Z0-9_]', '', safe)
        if not safe or safe[0].isdigit():
            safe = 'col_' + safe
        safe = safe or 'colonna'
        safe_cols.append(safe)
        sql_type = "REAL" if r["tipo_campo"] == "number" else "TEXT"
        cols_def.append(f'"{safe}" {sql_type}')
    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
    conn.execute(f'CREATE TABLE [{table}] (id INTEGER PRIMARY KEY AUTOINCREMENT, creato_da INTEGER, creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP, {", ".join(cols_def)})')
    conn.commit()
    conn.close()
    return safe_cols


def migra_tabella(file_id: int):
    conn = get_conn()
    table = f"dati_{file_id}"
    for col in ["creato_da", "creato_il"]:
        try:
            conn.execute(f"ALTER TABLE [{table}] ADD COLUMN {col} TEXT")
        except Exception:
            pass
    try:
        conn.execute(f"ALTER TABLE [{table}] ADD COLUMN creato_da INTEGER")
    except Exception:
        pass
    try:
        conn.execute(f"ALTER TABLE [{table}] ADD COLUMN creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass
    conn.commit()
    conn.close()


def carica_dati(file_id: int):
    conn = get_conn()
    table = f"dati_{file_id}"
    try:
        df = pd.read_sql(f"SELECT * FROM [{table}]", conn)
        conn.close()
        return df
    except Exception:
        conn.close()
        return None


def aggiorna_record(file_id: int, record_id: int, valori: dict):
    conn = get_conn()
    sets = ", ".join(f'"{k}" = ?' for k in valori)
    conn.execute(f"UPDATE [dati_{file_id}] SET {sets} WHERE id = ?", list(valori.values()) + [record_id])
    conn.commit()
    conn.close()


def elimina_record(file_id: int, record_id: int, utente_id: int = None, ruolo: str = None):
    conn = get_conn()
    if ruolo == "admin":
        conn.execute(f"DELETE FROM [dati_{file_id}] WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return True, None
    row = conn.execute(f"SELECT creato_da, creato_il FROM [dati_{file_id}] WHERE id = ?", (record_id,)).fetchone()
    if not row:
        conn.close()
        return False, "Record non trovato"
    if row["creato_da"] != utente_id:
        conn.close()
        return False, "Non puoi eliminare record creati da altri utenti. Contatta l'amministratore."
    import time
    from datetime import datetime, timedelta
    ts = row["creato_il"]
    if ts:
        try:
            created = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - created > timedelta(minutes=5):
                conn.close()
                return False, "Sono passati più di 5 minuti dalla creazione. Contatta l'amministratore per eliminare."
        except Exception:
            pass
    conn.execute(f"DELETE FROM [dati_{file_id}] WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True, None


def aggiungi_record(file_id: int, valori: dict, utente_id: int = None) -> int:
    conn = get_conn()
    extra_cols = []
    extra_vals = []
    if utente_id is not None:
        extra_cols.append("creato_da")
        extra_vals.append(utente_id)
    all_cols = [f'"{k}"' for k in valori] + extra_cols
    all_vals = list(valori.values()) + extra_vals
    cols = ", ".join(all_cols)
    placeholders = ", ".join(["?" for _ in all_vals])
    cur = conn.execute(f"INSERT INTO [dati_{file_id}] ({cols}) VALUES ({placeholders})", all_vals)
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def esporta_excel(file_id: int, percorso: str):
    df = carica_dati(file_id)
    if df is not None:
        df = df.drop(columns=["id"], errors="ignore")
        df.to_excel(percorso, index=False)
        return True
    return False


# ── Stati (Kanban) ──

def init_stati_table(file_id: int):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stati_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            ordine INTEGER DEFAULT 0,
            colore TEXT DEFAULT '#6B7280',
            mostra_kanban INTEGER DEFAULT 1,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE
        )
    """)
    try:
        conn.execute("ALTER TABLE stati_config ADD COLUMN mostra_kanban INTEGER DEFAULT 1")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transizioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            stato_da TEXT NOT NULL,
            stato_a TEXT NOT NULL,
            azione_tipo TEXT,
            colonna_destinazione TEXT,
            valore TEXT,
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER UNIQUE NOT NULL,
            colonna_stato TEXT DEFAULT '',
            colonna_titolo TEXT DEFAULT '',
            colonna_data_calendario TEXT DEFAULT '',
            FOREIGN KEY (file_id) REFERENCES file_excel(id) ON DELETE CASCADE
        )
    """)
    try:
        conn.execute("ALTER TABLE file_config ADD COLUMN colonna_data_calendario TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE file_config ADD COLUMN dashboard_config TEXT DEFAULT '[]'")
    except Exception:
        pass
    conn.commit()
    conn.close()


def get_file_config(file_id: int):
    init_stati_table(file_id)
    conn = get_conn()
    row = conn.execute("SELECT colonna_stato, colonna_titolo, colonna_data_calendario, dashboard_config FROM file_config WHERE file_id = ?", (file_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"colonna_stato": "", "colonna_titolo": "", "colonna_data_calendario": "", "dashboard_config": "[]"}


def save_file_config(file_id: int, colonna_stato: str | None = None, colonna_titolo: str | None = None, colonna_data_calendario: str | None = None, dashboard_config: str | None = None):
    init_stati_table(file_id)
    conn = get_conn()
    # read existing row to avoid overwriting unset fields with defaults
    existing = conn.execute("SELECT * FROM file_config WHERE file_id = ?", (file_id,)).fetchone()
    if existing:
        cur = dict(existing)
    else:
        cur = {"colonna_stato": "", "colonna_titolo": "", "colonna_data_calendario": "", "dashboard_config": "[]"}
    if colonna_stato is not None:
        cur["colonna_stato"] = colonna_stato
    if colonna_titolo is not None:
        cur["colonna_titolo"] = colonna_titolo
    if colonna_data_calendario is not None:
        cur["colonna_data_calendario"] = colonna_data_calendario
    if dashboard_config is not None:
        cur["dashboard_config"] = dashboard_config
    conn.execute("""
        INSERT INTO file_config (file_id, colonna_stato, colonna_titolo, colonna_data_calendario, dashboard_config)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(file_id)
        DO UPDATE SET colonna_stato=excluded.colonna_stato, colonna_titolo=excluded.colonna_titolo, colonna_data_calendario=excluded.colonna_data_calendario, dashboard_config=excluded.dashboard_config
    """, (file_id, cur["colonna_stato"], cur["colonna_titolo"], cur["colonna_data_calendario"], cur["dashboard_config"]))
    conn.commit()
    conn.close()


def get_dashboard_config(file_id: int) -> list:
    import json
    cfg = get_file_config(file_id)
    try:
        return json.loads(cfg.get("dashboard_config", "[]"))
    except Exception:
        return []


def save_dashboard_config(file_id: int, widgets: list):
    import json
    save_file_config(file_id, dashboard_config=json.dumps(widgets))


def get_stati_config(file_id: int, solo_kanban: bool = False):
    init_stati_table(file_id)
    conn = get_conn()
    where = "WHERE file_id = ?"
    if solo_kanban:
        where += " AND mostra_kanban = 1"
    rows = conn.execute(
        f"SELECT id, nome, ordine, colore, mostra_kanban FROM stati_config {where} ORDER BY ordine",
        (file_id,),
    ).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    for r in result:
        r["mostra_kanban"] = bool(r["mostra_kanban"])
    return result


def save_stati_list(file_id: int, stati: list):
    conn = get_conn()
    conn.execute("DELETE FROM stati_config WHERE file_id = ?", (file_id,))
    for i, s in enumerate(stati):
        conn.execute(
            "INSERT INTO stati_config (file_id, nome, ordine, colore, mostra_kanban) VALUES (?, ?, ?, ?, ?)",
            (file_id, s["nome"], i, s.get("colore", "#6B7280"), 1 if s.get("mostra_kanban", True) else 0),
        )
    conn.commit()
    conn.close()


def get_transizioni(file_id: int):
    init_stati_table(file_id)
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, stato_da, stato_a, azione_tipo, colonna_destinazione, valore FROM transizioni WHERE file_id = ? ORDER BY id",
        (file_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_transizione(file_id: int, stato_da: str, stato_a: str, azione_tipo: str, colonna: str, valore: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transizioni (file_id, stato_da, stato_a, azione_tipo, colonna_destinazione, valore) VALUES (?, ?, ?, ?, ?, ?)",
        (file_id, stato_da, stato_a, azione_tipo, colonna, valore),
    )
    conn.commit()
    conn.close()


def elimina_transizione(tid: int):
    conn = get_conn()
    conn.execute("DELETE FROM transizioni WHERE id = ?", (tid,))
    conn.commit()
    conn.close()


# ── Filtri salvati ──
def salva_filtro_salvato(file_id: int, nome: str, filtri: list):
    conn = get_conn()
    import json
    conn.execute("INSERT INTO filtri_salvati (file_id, nome, filtri) VALUES (?, ?, ?)",
                 (file_id, nome, json.dumps(filtri)))
    conn.commit()
    conn.close()


def get_filtri_salvati(file_id: int) -> list:
    conn = get_conn()
    rows = conn.execute("SELECT id, nome, filtri FROM filtri_salvati WHERE file_id = ? ORDER BY nome", (file_id,)).fetchall()
    conn.close()
    result = []
    import json
    for r in rows:
        d = dict(r)
        d["filtri"] = json.loads(d["filtri"])
        result.append(d)
    return result


def elimina_filtro_salvato(fid_salvato: int):
    conn = get_conn()
    conn.execute("DELETE FROM filtri_salvati WHERE id = ?", (fid_salvato,))
    conn.commit()
    conn.close()
