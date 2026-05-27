import sqlite3
import hashlib
import os
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


def init_db():
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
    cur = conn.execute("SELECT id FROM utenti WHERE email = ?", ("s.galvis@setinstudio.com",))
    if not cur.fetchone():
        conn.execute(
            "INSERT INTO utenti (email, nome, password, ruolo) VALUES (?, ?, ?, ?)",
            ("s.galvis@setinstudio.com", "Sergio Galvis", hash_pw("2385"), "admin"),
        )
    conn.commit()
    conn.close()


# ── Auth ──

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

def salva_file_excel(utente_id: int, percorso: str, foglio: str, colonne: list, righe: int, contenuto: bytes = None):
    conn = get_conn()
    nome = os.path.basename(percorso)
    cur = conn.execute("SELECT id FROM file_excel WHERE utente_id = ? AND percorso = ?", (utente_id, percorso))
    existing = cur.fetchone()
    if existing:
        conn.execute(
            "UPDATE file_excel SET foglio=?, colonne=?, righe=?, contenuto=COALESCE(?, contenuto), caricato_il=CURRENT_TIMESTAMP WHERE id=?",
            (foglio, ",".join(colonne), righe, contenuto, existing["id"]),
        )
        fid = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO file_excel (utente_id, percorso, nome_file, foglio, colonne, righe, contenuto) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (utente_id, percorso, nome, foglio, ",".join(colonne), righe, contenuto),
        )
        fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid


def file_utente(utente_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, percorso, nome_file, foglio, colonne, righe, caricato_il FROM file_excel WHERE utente_id = ? ORDER BY caricato_il DESC",
        (utente_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_file_contenuto(fid: int):
    conn = get_conn()
    row = conn.execute("SELECT contenuto, percorso, foglio FROM file_excel WHERE id = ?", (fid,)).fetchone()
    conn.close()
    if row and row["contenuto"]:
        import io
        return io.BytesIO(row["contenuto"]), row["foglio"]
    return None, None


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


def get_campi_config(file_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, nome_campo, tipo_campo, obbligatorio, opzioni FROM campi_config WHERE file_id = ? ORDER BY ordine",
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
        result.append(d)
    return result


def aggiorna_campo_config(config_id: int, tipo_campo: str = None, obbligatorio: bool = None, opzioni: list = None):
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
    if sets:
        conn.execute(f"UPDATE campi_config SET {', '.join(sets)} WHERE id = ?", params + [config_id])
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


# ── Dati (CRUD) ──

def init_data_table(file_id: int, df: pd.DataFrame):
    conn = get_conn()
    table = f"dati_{file_id}"
    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
    cols_def = []
    safe_cols = []
    for c in df.columns:
        safe = c.strip().replace(" ", "_").replace("'", "").replace('"', "").replace(".", "_")
        safe_cols.append(safe)
        if pd.api.types.is_numeric_dtype(df[c]):
            cols_def.append(f'"{safe}" REAL')
        elif pd.api.types.is_datetime64_any_dtype(df[c]):
            cols_def.append(f'"{safe}" TEXT')
        else:
            cols_def.append(f'"{safe}" TEXT')
    conn.execute(f'CREATE TABLE [{table}] (id INTEGER PRIMARY KEY AUTOINCREMENT, {", ".join(cols_def)})')
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


def init_data_table_vuoto(file_id: int, colonne: list):
    conn = get_conn()
    table = f"dati_{file_id}"
    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
    cols_def = [f'"{c.strip().replace(" ", "_").replace("'", "").replace("\"", "").replace(".", "_")}" TEXT' for c in colonne]
    conn.execute(f'CREATE TABLE [{table}] (id INTEGER PRIMARY KEY AUTOINCREMENT, {", ".join(cols_def)})')
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


def elimina_record(file_id: int, record_id: int):
    conn = get_conn()
    conn.execute(f"DELETE FROM [dati_{file_id}] WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def aggiungi_record(file_id: int, valori: dict):
    conn = get_conn()
    cols = ", ".join(f'"{k}"' for k in valori)
    placeholders = ", ".join(["?" for _ in valori])
    conn.execute(f"INSERT INTO [dati_{file_id}] ({cols}) VALUES ({placeholders})", list(valori.values()))
    conn.commit()
    conn.close()


def esporta_excel(file_id: int, percorso: str):
    df = carica_dati(file_id)
    if df is not None:
        df = df.drop(columns=["id"], errors="ignore")
        df.to_excel(percorso, index=False)
        return True
    return False
