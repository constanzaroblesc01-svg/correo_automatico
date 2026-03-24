import pandas as pd
import smtplib
import ssl
import time
import os
import json
from email.message import EmailMessage
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
CSV_FILE = os.path.join(BASE_DIR, "envios.csv")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

INTERVALO = 5  # segundos

# =========================
# CONFIG
# =========================
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# =========================
# EMAIL
# =========================
def enviar(row, config):
    msg = EmailMessage()
    msg["From"] = config["from_email"]
    msg["To"] = row["email"]
    msg["Subject"] = row["asunto"]

    html = f"""
    <html>
    <body style="font-family:Arial;">
    <p>{row['mensaje']}</p>
    """

    # imagen inline
    if row["adjunto"] and os.path.exists(row["adjunto"]):
        with open(row["adjunto"], "rb") as f:
            img_data = f.read()

        msg.add_related(img_data, maintype="image", subtype="png", cid="img1")

        html += '<br><img src="cid:img1" style="max-width:600px;">'

    html += "</body></html>"

    msg.set_content("Correo en HTML")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()

    with smtplib.SMTP(config["smtp_host"], int(config["smtp_port"])) as server:
        server.starttls(context=context)
        server.login(config["smtp_user"], config["smtp_pass"])
        server.send_message(msg)

# =========================
# LOOP
# =========================
def main():
    print("Mailer iniciado...")

    config = load_config()

    while True:
        df = pd.read_csv(CSV_FILE)

        pendientes = df[df["estado"] == "PENDIENTE"]

        if pendientes.empty:
            print("Todo enviado ✔")
            break

        for i, row in pendientes.iterrows():
            try:
                fecha_envio = datetime.strptime(row["send_at"], "%Y-%m-%d %H:%M")

                if datetime.now() >= fecha_envio:
                    enviar(row, config)
                    df.at[i, "estado"] = "ENVIADO"
                    df.to_csv(CSV_FILE, index=False)

                    print(f"Enviado a {row['email']}")
                    time.sleep(INTERVALO)

            except Exception as e:
                df.at[i, "estado"] = "ERROR"
                df.to_csv(CSV_FILE, index=False)
                print("Error:", e)

        time.sleep(10)

if __name__ == "__main__":
    main()
