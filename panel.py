import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import base64
import json
import subprocess
import sys
import os

# =========================
# LOGIN
# =========================
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🔐 Acceso a la herramienta")

        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")

        if st.button("Ingresar"):
            if usuario == "LaCasadelActor" and password == "correo2026":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

        st.stop()

check_login()

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "envios.csv"
CONFIG_FILE = BASE_DIR / "config.json"
MAILER_FILE = BASE_DIR / "enviar_correos.py"

COLUMNAS = [
    "id","email","nombre","asunto","mensaje",
    "send_at","adjunto","reintentos","estado","ultimo_error"
]

# =========================
# FUNCIONES
# =========================
def ensure_csv():
    if not CSV_FILE.exists():
        pd.DataFrame(columns=COLUMNAS).to_csv(CSV_FILE, index=False)

def read_csv():
    ensure_csv()
    return pd.read_csv(CSV_FILE)

def save_csv(df):
    df.to_csv(CSV_FILE, index=False)

def banner_html(file):
    if file is None:
        return ""
    file.seek(0)
    data = base64.b64encode(file.read()).decode()
    return f'<br><img src="data:image/png;base64,{data}" width="500">'

def launch_mailer():
    return subprocess.Popen([sys.executable, str(MAILER_FILE)])

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# =========================
# INICIO
# =========================
st.set_page_config(page_title="Correos", layout="wide")

df = read_csv()

# =========================
# SIDEBAR
# =========================
with st.sidebar:

    st.markdown("## ⚙️ Opciones")

    uploaded = st.file_uploader("Subir Excel o CSV", type=["xlsx","csv"])

    if st.button("🚀 Enviar correos"):
        launch_mailer()
        st.success("Mailer iniciado")

    if st.button("🧹 Limpiar registros"):
        save_csv(pd.DataFrame(columns=COLUMNAS))
        st.success("Registros eliminados")
        st.rerun()

# =========================
# HEADER
# =========================
st.title("📨 Sistema de Correos Automáticos")

# =========================
# TABS
# =========================
tabs = st.tabs(["Configuración", "Correos", "Instrucciones", "Registros", "Detalle"])

# =========================
# TAB 1 CONFIG
# =========================
with tabs[0]:

    st.subheader("Configuración SMTP")

    config = load_config()

    smtp_host = st.text_input("SMTP", value=config.get("smtp_host",""))
    smtp_port = st.text_input("Puerto", value=config.get("smtp_port","587"))
    smtp_user = st.text_input("Correo", value=config.get("smtp_user",""))
    smtp_pass = st.text_input("Clave", type="password", value=config.get("smtp_pass",""))

    from_name = st.text_input("Nombre visible", value=config.get("from_name",""))
    from_email = st.text_input("Email visible", value=config.get("from_email",""))

    if st.button("Guardar configuración"):
        save_config({
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_pass": smtp_pass,
            "from_name": from_name,
            "from_email": from_email
        })
        st.success("Guardado")

# =========================
# TAB 2 CORREOS
# =========================
with tabs[1]:

    st.subheader("Contenido del correo")

    st.session_state.asunto = st.text_input(
        "Asunto",
        value=st.session_state.get("asunto","")
    )

    st.session_state.mensaje = st.text_area(
        "Mensaje",
        value=st.session_state.get("mensaje",""),
        height=200
    )

    col1, col2 = st.columns(2)

    with col1:
        fecha = st.date_input("Fecha")

    with col2:
        hora = st.time_input("Hora")

    st.session_state.send_at = f"{fecha} {hora.strftime('%H:%M')}"

    st.subheader("Banner")
    banner = st.file_uploader("Imagen", type=["png","jpg"])
    st.session_state.banner = banner

    st.subheader("Carga archivo")

    if uploaded is not None:

        if not st.session_state.asunto or not st.session_state.mensaje:
            st.error("Completa asunto y mensaje")
            st.stop()

        if uploaded.name.endswith(".xlsx"):
            df_upload = pd.read_excel(uploaded)
        else:
            df_upload = pd.read_csv(uploaded)

        df_upload["asunto"] = st.session_state.asunto
        df_upload["mensaje"] = st.session_state.mensaje + banner_html(st.session_state.banner)
        df_upload["send_at"] = st.session_state.send_at
        df_upload["estado"] = "PENDIENTE"
        df_upload["reintentos"] = 0

        save_csv(df_upload)
        st.success("Archivo cargado")

# =========================
# TAB 3 INSTRUCCIONES
# =========================
with tabs[2]:

    st.markdown("""
    1. Configura tu correo  
    2. Escribe asunto y mensaje  
    3. Sube archivo  
    4. Presiona enviar  
    """)

# =========================
# TAB 4 REGISTROS
# =========================
with tabs[3]:

    st.dataframe(df)

# =========================
# TAB 5 DETALLE
# =========================
with tabs[4]:

    if not df.empty:
        idx = st.selectbox("Selecciona correo", df.index)
        row = df.loc[idx]

        st.text_area("Mensaje", row.get("mensaje",""), height=200)
        st.write("Estado:", row.get("estado"))
    else:
        st.info("Sin datos")
