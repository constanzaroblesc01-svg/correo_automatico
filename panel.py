import streamlit as st

# LOGIN SIMPLE
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



from pathlib import Path
import json
import subprocess
import sys
import os
from datetime import datetime

import pandas as pd
import streamlit as st

import base64

def banner_html(file):
    if file is None:
        return ""

    file.seek(0)  # 🔥 clave: reinicia el puntero

    data = base64.b64encode(file.read()).decode()

    return f"""
    <br><br>
    <img src="data:image/png;base64,{data}" style="max-width:600px;border-radius:10px;">
    """


BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "envios.csv"
LOG_FILE = BASE_DIR / "mailer.log"
CONFIG_FILE = BASE_DIR / "config.json"
MAILER_FILE = BASE_DIR / "enviar_correos.py"

COLUMNAS = [
    "id",
    "email",
    "nombre",
    "asunto",
    "mensaje",
    "send_at",
    "adjunto",
    "reintentos",
    "estado",
    "ultimo_error",
]

PROVEEDORES = {
    "Gmail": {"smtp_host": "smtp.gmail.com", "smtp_port": "587"},
    "Outlook / Hotmail": {"smtp_host": "smtp.office365.com", "smtp_port": "587"},
    "Microsoft 365": {"smtp_host": "smtp.office365.com", "smtp_port": "587"},
    "Otro": {"smtp_host": "", "smtp_port": "587"},
}


# =========================
# Datos
# =========================
def ensure_csv():
    if not CSV_FILE.exists():
        pd.DataFrame(columns=COLUMNAS).to_csv(CSV_FILE, index=False, encoding="utf-8-sig")


def read_input_file(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".xlsx":
        return pd.read_excel(uploaded_file, engine="openpyxl")

    if suffix == ".csv":
        try:
            return pd.read_csv(uploaded_file, encoding="utf-8-sig", sep=None, engine="python")
        except Exception:
            uploaded_file.seek(0)

        for sep in [",", ";", "\t"]:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding="utf-8-sig", sep=sep)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue

        raise ValueError("No se pudo leer el archivo CSV.")

    raise ValueError("Formato no soportado. Use Excel (.xlsx) o CSV.")


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    lower_to_original = {str(c).strip().lower(): c for c in df.columns}

    new_df = pd.DataFrame()
    for col in COLUMNAS:
        if col.lower() in lower_to_original:
            new_df[col] = df[lower_to_original[col.lower()]]
        else:
            new_df[col] = ""

    new_df = new_df[COLUMNAS].copy()
    new_df = new_df.dropna(how="all")

    for col in COLUMNAS:
        new_df[col] = new_df[col].fillna("").astype(str)

    new_df = new_df[
        ~(
            (new_df["email"].str.strip() == "") &
            (new_df["asunto"].str.strip() == "") &
            (new_df["mensaje"].str.strip() == "")
        )
    ].copy()

    if not new_df.empty:
        new_df["estado"] = new_df["estado"].replace("", "PENDIENTE").str.upper()
        new_df["reintentos"] = pd.to_numeric(new_df["reintentos"], errors="coerce").fillna(0).astype(int)

    return new_df


def save_csv(df: pd.DataFrame):
    df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")


def read_csv() -> pd.DataFrame:
    ensure_csv()
    df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")

    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS].copy()
    df = df.dropna(how="all")

    for col in COLUMNAS:
        df[col] = df[col].fillna("")

    df = df[
        ~(
            (df["email"].astype(str).str.strip() == "") &
            (df["asunto"].astype(str).str.strip() == "") &
            (df["mensaje"].astype(str).str.strip() == "")
        )
    ].copy()

    if not df.empty:
        df["estado"] = df["estado"].astype(str).replace("", "PENDIENTE").str.upper()
        df["reintentos"] = pd.to_numeric(df["reintentos"], errors="coerce").fillna(0).astype(int)

    return df


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def count_states(df: pd.DataFrame):
    estados = df["estado"].astype(str).str.upper().fillna("") if not df.empty else pd.Series(dtype=str)
    total = len(df)
    pendientes = int((estados == "PENDIENTE").sum()) if not df.empty else 0
    enviados = int((estados == "ENVIADO").sum()) if not df.empty else 0
    errores = int((estados == "ERROR").sum()) if not df.empty else 0
    return total, pendientes, enviados, errores


def launch_mailer():
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    return subprocess.Popen(
        [sys.executable, str(MAILER_FILE)],
        cwd=str(BASE_DIR),
        creationflags=creationflags
    )


def get_logs():
    if not LOG_FILE.exists():
        return "Todavía no existe mailer.log"
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            return "".join(f.readlines()[-120:])
    except Exception as e:
        return f"No se pudieron leer los logs:\n{e}"


def build_template_df():
    return pd.DataFrame(
        [{
            "email": "cliente@correo.com"
        }],
        columns=["email"]
    )


def validate_before_send(df: pd.DataFrame) -> list:
    issues = []

    if df.empty:
        issues.append("No hay archivo cargado o no hay correos válidos en el archivo.")

    required_cfg = {
        "Proveedor": st.session_state.get("provider", ""),
        "Servidor SMTP": st.session_state.get("smtp_host", ""),
        "Puerto": st.session_state.get("smtp_port", ""),
        "Correo remitente": st.session_state.get("smtp_user", ""),
        "Clave": st.session_state.get("smtp_pass", ""),
        "Nombre visible": st.session_state.get("from_name", ""),
        "Email visible": st.session_state.get("from_email", ""),
    }

    for label, value in required_cfg.items():
        if not str(value).strip():
            issues.append(f"Falta completar: {label}.")

    provider = st.session_state.get("provider", "")
    smtp_host = st.session_state.get("smtp_host", "").strip().lower()

    if provider == "Gmail" and smtp_host != "smtp.gmail.com":
        issues.append("Si usa Gmail, el servidor SMTP debe ser smtp.gmail.com.")

    if provider in ["Outlook / Hotmail", "Microsoft 365"] and smtp_host != "smtp.office365.com":
        issues.append("Si usa Outlook o Microsoft 365, el servidor SMTP debe ser smtp.office365.com.")

    if not df.empty:
        invalid_dates = pd.to_datetime(df["send_at"], errors="coerce").isna().sum()
        if invalid_dates > 0:
            issues.append("Hay fechas inválidas en la columna send_at del archivo.")

        invalid_email = df["email"].astype(str).str.contains("@", na=False).sum()
        if invalid_email == 0:
            issues.append("No se detectaron correos válidos en la columna email.")

    return issues


# =========================
# Estado inicial
# =========================
st.set_page_config(
    page_title="Sistema de Correos Automáticos",
    page_icon="📨",
    layout="wide",
)

ensure_csv()
config = load_config()

if "mailer_proc" not in st.session_state:
    st.session_state.mailer_proc = None

if "provider" not in st.session_state:
    st.session_state.provider = config.get("provider", "Gmail")
if "smtp_host" not in st.session_state:
    st.session_state.smtp_host = config.get("smtp_host", PROVEEDORES[st.session_state.provider]["smtp_host"])
if "smtp_port" not in st.session_state:
    st.session_state.smtp_port = str(config.get("smtp_port", PROVEEDORES[st.session_state.provider]["smtp_port"]))
if "smtp_user" not in st.session_state:
    st.session_state.smtp_user = config.get("smtp_user", "")
if "smtp_pass" not in st.session_state:
    st.session_state.smtp_pass = config.get("smtp_pass", "")
if "from_name" not in st.session_state:
    st.session_state.from_name = config.get("from_name", "")
if "from_email" not in st.session_state:
    st.session_state.from_email = config.get("from_email", "")


def on_provider_change():
    provider = st.session_state.provider
    defaults = PROVEEDORES.get(provider, {"smtp_host": "", "smtp_port": "587"})
    st.session_state.smtp_host = defaults["smtp_host"]
    st.session_state.smtp_port = str(defaults["smtp_port"])


# =========================
# Estilo
# =========================
st.markdown("""
<style>
.block-container {
    max-width: 1700px;
    padding-top: 1rem;
    padding-bottom: 2rem;
}

.stApp {
    background:
        radial-gradient(circle at 0% 0%, rgba(80,140,255,0.22) 0%, transparent 28%),
        radial-gradient(circle at 100% 0%, rgba(80,220,255,0.15) 0%, transparent 25%),
        linear-gradient(135deg, #0a1b33 0%, #10325b 18%, #e9f2fb 55%, #f8fbff 100%);
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(8,28,55,0.96) 0%, rgba(16,58,109,0.96) 100%);
    border-right: 1px solid rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] * {
    color: white !important;
}

.stButton > button,
.stDownloadButton > button {
    width: 100%;
    min-height: 56px;
    border-radius: 16px;
    border: none;
    font-weight: 700;
    font-size: 18px;
    color: white !important;
    background: linear-gradient(135deg, #2d79d1 0%, #1f5ea9 100%);
    box-shadow: 0 10px 20px rgba(18, 48, 86, 0.22);
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    color: white !important;
    background: linear-gradient(135deg, #246dc2 0%, #194f90 100%);
}

/* Hero glass */
.hero-shell {
    background: linear-gradient(135deg, rgba(255,255,255,0.18), rgba(255,255,255,0.08));
    backdrop-filter: blur(22px);
    -webkit-backdrop-filter: blur(22px);
    border: 1px solid rgba(255,255,255,0.22);
    border-radius: 30px;
    box-shadow: 0 14px 36px rgba(16, 39, 74, 0.18);
    overflow: hidden;
    margin-bottom: 22px;
}
.hero-core {
    background: linear-gradient(135deg, rgba(31,103,191,0.82), rgba(65,148,242,0.78));
    padding: 36px 42px;
}
.hero-greeting {
    color: #eaf5ff;
    font-size: 1.5rem;
    font-weight: 700;
}
.hero-title {
    color: white;
    font-size: 3.4rem;
    font-weight: 800;
    line-height: 1.02;
    margin-top: 8px;
}
.hero-sub {
    color: #eef7ff;
    font-size: 1.22rem;
    line-height: 1.7;
    margin-top: 14px;
    max-width: 1000px;
}

/* Cards */
.glass-card {
    background: rgba(255,255,255,0.76);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.55);
    border-radius: 26px;
    padding: 24px;
    box-shadow: 0 12px 28px rgba(16, 42, 76, 0.08);
}
.help-card {
    background: linear-gradient(135deg, rgba(235,245,255,0.95), rgba(224,239,255,0.88));
    border-left: 6px solid #2a74cd;
    border-radius: 18px;
    padding: 18px;
    color: #1b456d;
    font-size: 18px;
    line-height: 1.7;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.74);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.55);
    border-radius: 22px;
    padding: 12px 18px;
    box-shadow: 0 8px 18px rgba(16, 42, 76, 0.06);
}
div[data-testid="stMetricLabel"] {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #35587a !important;
}
div[data-testid="stMetricValue"] {
    font-size: 44px !important;
    font-weight: 800 !important;
    color: #14375a !important;
}

/* Inputs */
.stTextInput input,
.stTextArea textarea {
    border-radius: 14px !important;
    font-size: 17px !important;
    color: #173247 !important;
    background: rgba(255,255,255,0.94) !important;
}
div[data-baseweb="select"] > div {
    border-radius: 14px !important;
    font-size: 17px !important;
    color: #173247 !important;
    background: rgba(255,255,255,0.94) !important;
}

/* File uploader */
[data-testid="stFileUploader"] section {
    background: rgba(255,255,255,0.95) !important;
    border: 2px dashed rgba(122,160,210,0.65) !important;
    border-radius: 18px !important;
    padding: 14px !important;
}
[data-testid="stFileUploader"] section * {
    color: #173247 !important;
}
[data-testid="stFileUploader"] button {
    background: #eef5fd !important;
    color: #173247 !important;
    border-radius: 12px !important;
    border: 1px solid #bfd3e8 !important;
    font-weight: 700 !important;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.section-title {
    color: #173247;
    font-size: 1.9rem;
    font-weight: 800;
    margin-bottom: 12px;
}
.instructions p {
    font-size: 20px;
    line-height: 1.8;
    color: #244767;
}
.instructions strong {
    color: #173247;
}
</style>
""", unsafe_allow_html=True)

# =========================
# UI
# =========================
df = read_csv()
total, pendientes, enviados, errores = count_states(df)

hora = datetime.now().hour
saludo = "Buenos días" if hora < 12 else "Buenas tardes" if hora < 20 else "Buenas noches"
nombre_persona = st.session_state.from_name.strip() if st.session_state.from_name.strip() else "Bienvenida"

st.markdown(f"""
<div class="hero-shell">
    <div class="hero-core">
        <div class="hero-greeting">{saludo}, {nombre_persona}</div>
        <div class="hero-title">📨 Herramienta de Correos Automáticos</div>
        <div class="hero-sub">
            Cargue su archivo, configure su correo y use los botones del lado izquierdo para enviar sus correos de forma automática y segura.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Total", total)
with m2:
    st.metric("Pendientes", pendientes)
with m3:
    st.metric("Enviados", enviados)
with m4:
    st.metric("Errores", errores)

issues = validate_before_send(df)

with st.sidebar:
    st.markdown("## Opciones principales")

    uploaded = st.file_uploader(
        "Seleccione su archivo Excel o CSV",
        type=["xlsx", "csv"],
        help="Puede cargar un archivo Excel (.xlsx) o CSV.",
        key="sidebar_file_uploader"
    )

    if uploaded is not None:
        try:
            df_raw = read_input_file(uploaded)
            df_norm = normalize_dataframe(df_raw)
    
            if st.session_state.get("asunto_global"):
               df_norm["asunto"] = st.session_state.get("asunto_global")
            if st.session_state.get("mensaje_global"):
                df_norm["mensaje"] = st.session_state.get("mensaje_global") + banner_html(st.session_state.get("banner_file"))

            if st.session_state.get("send_at_global"):
                df_norm["send_at"] = st.session_state.get("send_at_global")
            
            df_norm["estado"] = "PENDIENTE"
                
            if df_norm.empty:
                st.warning("El archivo no contiene datos válidos.")
            else:
                save_csv(df_norm)
                st.success("Archivo cargado correctamente.")
                st.rerun()
    
        except Exception as e:
            st.error(f"No se pudo cargar el archivo: {e}")

    plantilla_df = build_template_df()
    plantilla_path = BASE_DIR / "plantilla_envios.xlsx"
    plantilla_df.to_excel(plantilla_path, index=False)

    with open(plantilla_path, "rb") as f:
        st.download_button(
            "Descargar plantilla",
            data=f,
            file_name="plantilla_envios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    if st.button("Guardar configuración", use_container_width=True):
        missing = [
            st.session_state.smtp_host,
            st.session_state.smtp_port,
            st.session_state.smtp_user,
            st.session_state.smtp_pass,
            st.session_state.from_name,
            st.session_state.from_email,
        ]
        if any(not str(x).strip() for x in missing):
            st.warning("Complete todos los campos de configuración.")
        else:
            save_config({
                "provider": st.session_state.provider,
                "smtp_host": st.session_state.smtp_host.strip(),
                "smtp_port": str(st.session_state.smtp_port).strip(),
                "smtp_user": st.session_state.smtp_user.strip(),
                "smtp_pass": st.session_state.smtp_pass.strip(),
                "from_name": st.session_state.from_name.strip(),
                "from_email": st.session_state.from_email.strip(),
            })
            st.success("Configuración guardada correctamente.")
            st.rerun()

    enviar_disabled = len(issues) > 0
    if st.button("Enviar correos", use_container_width=True, disabled=enviar_disabled):
        try:
            if st.session_state.mailer_proc is None or st.session_state.mailer_proc.poll() is not None:
                st.session_state.mailer_proc = launch_mailer()
                st.success("Sistema de envío iniciado.")
            else:
                st.info("El sistema ya está en ejecución.")
        except Exception as e:
            st.error(f"No se pudo iniciar el sistema: {e}")

    if st.button("Detener envíos", use_container_width=True):
        if st.session_state.mailer_proc is not None and st.session_state.mailer_proc.poll() is None:
            st.session_state.mailer_proc.terminate()
            st.success("Sistema de envío detenido.")
        else:
            st.info("No hay envío activo.")

    if st.button("Vaciar registros", use_container_width=True):
        save_csv(pd.DataFrame(columns=COLUMNAS))
        st.success("Registros eliminados.")
        st.rerun()

    if st.button("Actualizar", use_container_width=True):
        st.rerun()

    st.markdown("---")
    st.markdown("### Estado del sistema")
    if st.session_state.mailer_proc is not None and st.session_state.mailer_proc.poll() is None:
        st.success("Enviando")
    else:
        st.info("Detenido")

tabs = st.tabs(["Configuración", "Correos", "Instrucciones", "Registros", "Correo Específico"])
with tabs[0]:

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Configuración del correo remitente</div>', unsafe_allow_html=True)

    st.selectbox(
        "Proveedor de correo",
        list(PROVEEDORES.keys()),
        key="provider",
        on_change=on_provider_change
    )

    c1, c2 = st.columns(2)

    with c1:
        st.text_input("Servidor SMTP", key="smtp_host")
        st.text_input("Correo remitente", key="smtp_user")
        st.text_input("Nombre visible", key="from_name")

    with c2:
        st.text_input("Puerto", key="smtp_port")
        st.text_input("Clave", key="smtp_pass", type="password")
        st.text_input("Email visible", key="from_email")

    st.markdown('</div>', unsafe_allow_html=True)
with tabs[1]:
with tabs[1]:

    # -------------------------
    # TABLA
    # -------------------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Correos cargados</div>', unsafe_allow_html=True)

    f1, f2 = st.columns([1, 2])

    with f1:
        filtro = st.selectbox("Filtrar por estado", ["TODOS", "PENDIENTE", "ENVIADO", "ERROR"])

    with f2:
        texto = st.text_input("Buscar por nombre, correo o asunto")

    vista = df.copy()

    if filtro != "TODOS":
        vista = vista[vista["estado"].astype(str).str.upper() == filtro]

    if texto.strip():
        t = texto.strip().lower()
        mask = (
            vista["email"].astype(str).str.lower().str.contains(t, na=False) |
            vista["nombre"].astype(str).str.lower().str.contains(t, na=False) |
            vista["asunto"].astype(str).str.lower().str.contains(t, na=False)
        )
        vista = vista[mask]

    columnas = ["id", "nombre", "email", "asunto", "send_at", "estado"]
    columnas_existentes = [c for c in columnas if c in vista.columns]

    tabla = vista[columnas_existentes].copy()

    if tabla.empty:
        st.warning("No hay datos para mostrar")
    else:
        nombres = ["ID", "Nombre", "Correo destino", "Asunto", "Programado para", "Estado"]
        tabla.columns = nombres[:len(tabla.columns)]
        st.dataframe(tabla, use_container_width=True, height=430)

    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------
    # CONTENIDO
    # -------------------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Contenido del correo</div>', unsafe_allow_html=True)

    st.session_state.asunto_global = st.text_input("Asunto del correo")
    st.session_state.mensaje_global = st.text_area("Mensaje del correo", height=220)

    col_fecha, col_hora = st.columns(2)

    with col_fecha:
        fecha_envio = st.date_input("Fecha de envío")

    with col_hora:
        hora_envio = st.time_input("Hora de envío")

    st.session_state.send_at_global = f"{fecha_envio} {hora_envio.strftime('%H:%M')}"

    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------
    # BANNER
    # -------------------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Firma / Banner</div>', unsafe_allow_html=True)

    st.session_state.banner_file = st.file_uploader(
        "Subir banner del correo",
        type=["png", "jpg", "jpeg"]
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------
    # VISTA PREVIA
    # -------------------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Vista previa del correo</div>', unsafe_allow_html=True)

    firma = banner_html(st.session_state.get("banner_file"))

    st.markdown(
        st.session_state.get("mensaje_global", "") + firma,
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


    
with tabs[2]:
    st.markdown('<div class="glass-card instructions">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Instrucciones paso a paso</div>', unsafe_allow_html=True)
    st.markdown("""
<p><strong>Paso 1.</strong> En el menú del lado izquierdo, haga clic en <strong>Descargar plantilla</strong>.</p>
<p><strong>Paso 2.</strong> Abra el archivo Excel y escriba los correos que quiere enviar.</p>
<p><strong>Paso 3.</strong> Guarde el archivo Excel.</p>
<p><strong>Paso 4.</strong> En el menú del lado izquierdo, haga clic en <strong>Cargar archivo Excel o CSV</strong> y seleccione su archivo.</p>
<p><strong>Paso 5.</strong> Abra la pestaña <strong>Configuración</strong>.</p>
<p><strong>Paso 6.</strong> Elija su proveedor de correo.</p>
<p><strong>Paso 7.</strong> Escriba su correo y su clave.</p>
<p><strong>Paso 8.</strong> Haga clic en <strong>Guardar configuración</strong>.</p>
<p><strong>Paso 9.</strong> Mire la sección <strong>Revisión antes de enviar</strong>.</p>
<p><strong>Paso 10.</strong> Si todo está correcto, haga clic en <strong>Enviar correos</strong>.</p>
<p><strong>Si usa Gmail:</strong> use la clave especial de 16 caracteres de Google.</p>
<p><strong>Si usa Outlook o Microsoft:</strong> use la contraseña normal de esa cuenta.</p>
""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[3]:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Registros del sistema</div>', unsafe_allow_html=True)
    st.text_area("Logs", value=get_logs(), height=520)

    st.markdown('</div>', unsafe_allow_html=True)

with tabs[4]:

    st.subheader("Detalle del correo")

    vista = df.copy()

    if not vista.empty:

        idx = st.selectbox(
            "Seleccione un registro para ver el detalle",
            vista.index,
            format_func=lambda x: f"{vista.loc[x, 'nombre']} - {vista.loc[x, 'email']}",
            key="detalle_select_registro"
        )

        row = vista.loc[idx]

        d1, d2 = st.columns([2, 1])

        with d1:
            st.text_area("Mensaje", value=str(row.get("mensaje", "")), height=220)
            st.text_area("Último error", value=str(row.get("ultimo_error", "")), height=140)

        with d2:
            st.text_input("Adjunto", value=str(row.get("adjunto", "")))
            st.text_input("Reintentos", value=str(row.get("reintentos", "")))
            st.text_input("Estado", value=str(row.get("estado", "")))

    else:
        st.info("No hay registros para mostrar.")
