import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from deep_translator import GoogleTranslator
from gtts import gTTS

from app.core.config import settings


def translate_text(text: str, target_lang: str = "en") -> str:
    if not text or not text.strip():
        return text
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    translated = []
    for c in chunks:
        try:
            translated.append(GoogleTranslator(source="auto", target=target_lang).translate(c))
        except Exception:
            translated.append(c)
    return " ".join(translated)


def generate_voice_summary(summary_text: str, document_id: int, lang: str = "en") -> Path:
    out_path = settings.REPORT_DIR / f"summary_doc{document_id}_{lang}.mp3"
    tts = gTTS(text=summary_text[:3000], lang=lang)
    tts.save(str(out_path))
    return out_path


def send_email_report(
    recipient_email: str,
    subject: str,
    body: str,
    attachment_path: Path,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    use_tls: bool = True,
) -> bool:
    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(attachment_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={attachment_path.name}")
    msg.attach(part)

    context = ssl.create_default_context()
    if use_tls:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient_email, msg.as_string())
    else:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient_email, msg.as_string())
    return True