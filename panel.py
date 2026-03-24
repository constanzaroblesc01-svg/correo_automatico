import streamlit as st
from pathlib import Path
import pandas as pd
import subprocess
import sys
import json
import os

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "envios.csv"
CONFIG_FILE = BASE_DIR / "config.json"
MAILER_FILE = BASE_DIR / "enviar_correos.py"

COLUMNAS = [
    "email",
    "nombre",
    "asunto",
    "mensaje",
    "send_at",
    "adjunto",
    "estado",
]

# =========================
# CONFIG
# =========================
def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_config():
    if CONFIG_FILE.exists():
        return json.load(open(CONFIG_FILE, "r"))
    return {}

# =========================
# CSV
# =========================
def save_csv(df):
    df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")

def read_csv():
    if not CSV_FILE.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(CSV_FILE)

# =========================
# UI
# =========================
st.title("📨 Sistema de Envío de Correos")

config = load_config()

smtp_user = st.text_input("Correo", value=config.get("smtp_user", ""))
smtp_pass = st.text_input("Clave", type="password", value=config.get("smtp_pass", ""))

if st.button("Guardar configuración"):
    save_config({
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
        "from_name": smtp_user,
        "from_email": smtp_user,
    })
    st.success("Guardado")

st.divider()

asunto = st.text_input("Asunto")
mensaje = st.text_area("Mensaje")
fecha = st.text_input("Fecha envío (YYYY-MM-DD HH:MM)")

archivo = st.file_uploader("Subir Excel/CSV", type=["xlsx", "csv"])
imagen = st.file_uploader("Imagen opcional", type=["png", "jpg", "jpeg"])

if st.button("Cargar correos"):
    if archivo is None:
        st.error("Sube archivo")
    else:
        if archivo.name.endswith(".xlsx"):
            df = pd.read_excel(archivo)
        else:
            df = pd.read_csv(archivo)

        df["asunto"] = asunto
        df["mensaje"] = mensaje
        df["send_at"] = fecha
        df["estado"] = "PENDIENTE"

        if imagen:
            path_img = BASE_DIR / "imagen.png"
            with open(path_img, "wb") as f:
                f.write(imagen.getbuffer())
            df["adjunto"] = str(path_img)
        else:
            df["adjunto"] = ""

        save_csv(df)
        st.success("Correos cargados")

st.divider()

if st.button("🚀 Iniciar envío"):
    subprocess.Popen([sys.executable, str(MAILER_FILE)])
    st.success("Mailer iniciado")

if st.button("🛑 Detener"):
    st.warning("Cerrar consola manualmente")
