import json
import logging
import os
import smtplib
import ssl
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "envios.csv"
LOG_FILE = BASE_DIR / "mailer.log"
CONFIG_FILE = BASE_DIR / "config.json"

CHECK_INTERVAL_SECONDS = 20
RATE_LIMIT_SECONDS = 3
MAX_RETRIES = 3
RETRY_MINUTES = 10

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("No existe config.json. Debe guardar la configuración desde la aplicación.")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    required = ["smtp_host", "smtp_port", "smtp_user", "smtp_pass", "from_name", "from_email"]
    for key in required:
        if not str(config.get(key, "")).strip():
            raise ValueError(f"Falta completar la configuración: {key}")

    return config


def ensure_csv() -> None:
    if not CSV_FILE.exists():
        df = pd.DataFrame(columns=COLUMNAS)
        df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")


def read_jobs() -> pd.DataFrame:
    ensure_csv()
    df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")

    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS].copy()
    df = df.dropna(how="all")

    for col in COLUMNAS:
        df[col] = df[col].fillna("")

    # eliminar filas realmente vacías
    df = df[
        ~(
            (df["email"].astype(str).str.strip() == "") &
            (df["asunto"].astype(str).str.strip() == "") &
            (df["mensaje"].astype(str).str.strip() == "")
        )
    ].copy()

    if df.empty:
        return df

    df["estado"] = df["estado"].astype(str).replace("", "PENDIENTE").str.upper()
    df["reintentos"] = pd.to_numeric(df["reintentos"], errors="coerce").fillna(0).astype(int)

    # parseo robusto de fecha/hora
    df["send_at_dt"] = pd.to_datetime(df["send_at"], errors="coerce")

    invalidas = df["send_at_dt"].isna()
    if invalidas.any():
        for idx in df[invalidas].index:
            logging.error("Fila %s invalida: fecha/hora inválida -> %s", idx + 2, df.at[idx, "send_at"])
        df = df[~invalidas].copy()

    return df


def save_jobs(df: pd.DataFrame) -> None:
    df_to_save = df.copy()

    if "send_at_dt" in df_to_save.columns:
        df_to_save["send_at"] = df_to_save["send_at_dt"].dt.strftime("%Y-%m-%d %H:%M")
        df_to_save = df_to_save.drop(columns=["send_at_dt"])

    df_to_save = df_to_save[COLUMNAS]
    df_to_save.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")


def render_template(text: str, nombre: str, email: str) -> str:
    text = str(text)
    return text.replace("{{nombre}}", str(nombre or "")).replace("{{email}}", str(email or ""))


def build_message(row: pd.Series, config: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f'{config["from_name"]} <{config["from_email"]}>'
    msg["To"] = str(row["email"]).strip()
    msg["Subject"] = render_template(row["asunto"], row["nombre"], row["email"])

    body = render_template(row["mensaje"], row["nombre"], row["email"])
    msg.set_content(body)

    adjunto = str(row["adjunto"]).strip()
    if adjunto:
        if not os.path.exists(adjunto):
            raise FileNotFoundError(f"Adjunto no encontrado: {adjunto}")
        with open(adjunto, "rb") as f:
            data = f.read()
        filename = os.path.basename(adjunto)
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=filename,
        )

    return msg


def smtp_send(row: pd.Series, config: dict) -> None:
    msg = build_message(row, config)
    context = ssl.create_default_context()

    with smtplib.SMTP(config["smtp_host"], int(config["smtp_port"]), timeout=60) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(config["smtp_user"], config["smtp_pass"])
        server.send_message(msg)


def process_due_jobs() -> None:
    config = load_config()
    df = read_jobs()

    if df.empty:
        logging.info("No hay correos válidos para procesar.")
        return

    now = datetime.now()

    due_mask = (df["estado"] == "PENDIENTE") & (df["send_at_dt"] <= now)
    due_df = df[due_mask].sort_values("send_at_dt").copy()

    if due_df.empty:
        logging.info("No hay correos pendientes para enviar ahora.")
        return

    logging.info("Pendientes listos para enviar: %s", len(due_df))
    sent_count = 0

    for idx, row in due_df.iterrows():
        try:
            logging.info(
                "Enviando a %s | asunto=%s | programado=%s",
                row["email"],
                row["asunto"],
                row["send_at_dt"],
            )
            smtp_send(row, config)
            df.at[idx, "estado"] = "ENVIADO"
            df.at[idx, "ultimo_error"] = ""
            sent_count += 1
            time.sleep(RATE_LIMIT_SECONDS)

        except Exception as e:
            retries = int(df.at[idx, "reintentos"]) + 1
            df.at[idx, "reintentos"] = retries
            df.at[idx, "ultimo_error"] = str(e)[:500]

            if retries >= MAX_RETRIES:
                df.at[idx, "estado"] = "ERROR"
                logging.error("Fallo definitivo para %s: %s", row["email"], e)
            else:
                df.at[idx, "send_at_dt"] = datetime.now() + timedelta(minutes=RETRY_MINUTES)
                logging.warning(
                    "Fallo temporal para %s. Reintento %s/%s en %s min. Error: %s",
                    row["email"],
                    retries,
                    MAX_RETRIES,
                    RETRY_MINUTES,
                    e,
                )

    save_jobs(df)
    logging.info("Archivo actualizado. Enviados en este ciclo: %s", sent_count)


def main() -> None:
    ensure_csv()
    logging.info("MAILER NUEVO EJECUTANDO")
    logging.info("Iniciando mailer programado...")
    logging.info("CSV_FILE=%s", CSV_FILE)

    while True:
        try:
            process_due_jobs()
        except Exception as e:
            logging.exception("Error general del proceso: %s", e)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()