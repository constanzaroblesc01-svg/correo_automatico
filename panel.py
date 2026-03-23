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

def save_csv(df):
    df.to_csv(CSV_FILE, index=False)

def read_csv():
    ensure_csv()
    return pd.read_csv(CSV_FILE)

def banner_html(file):
    if file is None:
        return ""
    file.seek(0)
    data = base64.b64encode(file.read()).decode()
    return f'<br><img src="data:image/png;base64,{data}" width="500">'

def launch_mailer():
    return subprocess.Popen([sys.executable, str(MAILER_FILE)])

# =========================
# UI
# =========================
st.set_page_config(page_title="Correos", layout="wide")

st.title("📨 Sistema de Correos Automáticos")

# =========================
# SIDEBAR
# =========================
with st.sidebar:

    st.markdown("## ⚙️ Opciones")

    uploaded = st.file_uploader("Subir Excel o CSV", type=["xlsx","csv"])

    if st.button("🚀 Enviar correos"):
        st.session_state.start_send = True

    if st.button("🛑 Detener"):
        st.session_state.start_send = False

    if st.button("🧹 Limpiar registros"):
        save_csv(pd.DataFrame(columns=COLUMNAS))
        st.success("Registros eliminados")
        st.rerun()

# =========================
# CONTENIDO PRINCIPAL
# =========================

st.subheader("✉️ Contenido del correo")

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
    fecha = st.date_input("Fecha envío")

with col2:
    hora = st.time_input("Hora envío")

send_at = f"{fecha} {hora.strftime('%H:%M')}"
st.session_state.send_at = send_at

# =========================
# BANNER
# =========================
st.subheader("🖼️ Banner (opcional)")
banner = st.file_uploader("Subir imagen", type=["png","jpg","jpeg"])
st.session_state.banner = banner

# =========================
# CARGA ARCHIVO
# =========================
st.subheader("📂 Cargar contactos")

if uploaded is not None:

    if not st.session_state.asunto or not st.session_state.mensaje:
        st.error("Debes escribir asunto y mensaje")
        st.stop()

    try:
        if uploaded.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded)
        else:
            df = pd.read_csv(uploaded)

        df["asunto"] = st.session_state.asunto
        df["mensaje"] = st.session_state.mensaje + banner_html(st.session_state.banner)
        df["send_at"] = st.session_state.send_at
        df["estado"] = "PENDIENTE"
        df["reintentos"] = 0

        save_csv(df)

        st.success("Archivo cargado correctamente")

    except Exception as e:
        st.error(str(e))

# =========================
# VISTA PREVIA
# =========================
st.subheader("👁️ Vista previa")

st.markdown(
    st.session_state.get("mensaje","") + banner_html(st.session_state.get("banner")),
    unsafe_allow_html=True
)

# =========================
# TABLA
# =========================
st.subheader("📊 Correos cargados")

df = read_csv()

if not df.empty:
    st.dataframe(df)
else:
    st.info("No hay correos cargados")

# =========================
# ENVÍO
# =========================
if st.session_state.get("start_send"):
    st.success("Sistema de envío iniciado")
    launch_mailer()
