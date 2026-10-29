from __future__ import annotations

import json
import logging
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import (
    BREVO_API_KEY,
    EMAIL_FROM_EMAIL,
    EMAIL_FROM_NAME,
    EMAIL_MODE,
    EMAIL_REPLY_TO,
    ORIGIN,
    PRODUCTION,
)

logger = logging.getLogger("scoutliq.email")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
MEMORY_OUTBOX: list[dict] = []


class EmailConfigurationError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    pass


def email_is_configured() -> bool:
    if EMAIL_MODE in {"memory", "console"}:
        return True
    if EMAIL_MODE == "brevo":
        return bool(BREVO_API_KEY and EMAIL_FROM_EMAIL)
    return False


def _masked_email(value: str) -> str:
    local, sep, domain = str(value or "").partition("@")
    if not sep:
        return "destinatário protegido"
    prefix = local[:2] if len(local) > 2 else local[:1]
    return f"{prefix}***@{domain}"


def _message(*, recipient: str, subject: str, heading: str, body: str, action_label: str, link: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((EMAIL_FROM_NAME or "ScoutLIQ", EMAIL_FROM_EMAIL or "noreply@orliq.local"))
    message["To"] = recipient
    if EMAIL_REPLY_TO:
        message["Reply-To"] = EMAIL_REPLY_TO
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    message.set_content(
        f"{heading}\n\n{body}\n\n{action_label}: {link}\n\n"
        "Se você não solicitou isso, ignore esta mensagem."
    )
    message.add_alternative(
        f"""
        <!doctype html>
        <html lang="pt-BR">
          <body style="margin:0;background:#0b0c10;color:#f3f4f6;" bgcolor="#0b0c10">
            <div style="max-width:560px;margin:0 auto;padding:40px 20px;">
              <div style="border:1px solid #2d3038;border-radius:16px;background:#111318;" bgcolor="#111318">
                <div style="padding:30px;">
                  <p style="margin:0 0 8px;color:#d35270;font-size:12px;font-weight:700;letter-spacing:1.8px;">SCOUTLIQ · ORLIQ</p>
                  <h1 style="margin:0 0 18px;font-size:25px;font-weight:600;color:#f5f6f8;">{escape(heading)}</h1>
                  <p style="margin:0 0 24px;color:#aeb4bf;line-height:1.65;">{escape(body)}</p>
                  <a href="{escape(link, quote=True)}" style="display:inline-block;padding:13px 18px;border-radius:8px;background:#b93151;color:#ffffff;text-decoration:none;font-weight:700;">{escape(action_label)}</a>
                  <p style="margin:25px 0 0;color:#727985;font-size:12px;line-height:1.55;">Se você não solicitou isso, ignore esta mensagem.</p>
                </div>
              </div>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )
    return message


def _send(message: EmailMessage, *, link: str, token: str) -> None:
    if EMAIL_MODE == "memory":
        MEMORY_OUTBOX.append(
            {
                "to": str(message["To"] or ""),
                "subject": str(message["Subject"] or ""),
                "link": link,
                "token": token,
            }
        )
        return
    if EMAIL_MODE == "console":
        logger.warning(
            "E-mail em modo de desenvolvimento | destinatário=%s | assunto=%s%s",
            _masked_email(str(message["To"] or "")),
            message["Subject"],
            f" | link={link}" if not PRODUCTION else "",
        )
        return
    if EMAIL_MODE != "brevo" or not email_is_configured():
        raise EmailConfigurationError("O envio de e-mail ainda não foi configurado.")

    recipient = str(message["To"] or "")
    body_html = message.get_body(preferencelist=("html",))
    body_text = message.get_body(preferencelist=("plain",))
    payload: dict = {
        "sender": {"name": EMAIL_FROM_NAME or "ScoutLIQ", "email": EMAIL_FROM_EMAIL},
        "to": [{"email": recipient}],
        "subject": str(message["Subject"] or "ScoutLIQ"),
    }
    if EMAIL_REPLY_TO:
        payload["replyTo"] = {"email": EMAIL_REPLY_TO}
    if body_html is not None:
        payload["htmlContent"] = body_html.get_content()
    elif body_text is not None:
        payload["textContent"] = body_text.get_content()

    request = Request(
        BREVO_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-key": BREVO_API_KEY,
            "User-Agent": "ScoutLIQ/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            status = int(response.getcode())
            response_body = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        logger.error("Brevo recusou e-mail | status=%s | resposta=%s", error.code, response_body[:300])
        raise EmailDeliveryError("O serviço de e-mail recusou o envio.") from error
    except (OSError, URLError, TimeoutError) as error:
        logger.error("Falha de conexão com a Brevo: %s", type(error).__name__)
        raise EmailDeliveryError("O serviço de e-mail não respondeu agora.") from error

    if not 200 <= status < 300:
        logger.error("Resposta inesperada da Brevo | status=%s | resposta=%s", status, response_body[:300])
        raise EmailDeliveryError("O serviço de e-mail não aceitou o envio.")
    logger.info("E-mail aceito pela Brevo | destinatário=%s", _masked_email(recipient))


def send_verification_email(email: str, display_name: str, token: str) -> None:
    fragment = urlencode({"verify_token": token})
    link = f"{ORIGIN}/#{fragment}"
    message = _message(
        recipient=email,
        subject="Confirme seu e-mail no ScoutLIQ",
        heading="Confirme seu e-mail",
        body=(
            f"Olá, {display_name}. Confirme este endereço para ativar sua conta no ScoutLIQ. "
            "O link expira em 24 horas."
        ),
        action_label="Confirmar e-mail",
        link=link,
    )
    _send(message, link=link, token=token)


def send_password_reset_email(email: str, display_name: str, token: str) -> None:
    fragment = urlencode({"reset_token": token})
    link = f"{ORIGIN}/#{fragment}"
    message = _message(
        recipient=email,
        subject="Redefinição de senha do ScoutLIQ",
        heading="Crie uma nova senha",
        body=(
            f"Olá, {display_name}. Recebemos um pedido para trocar sua senha. "
            "O link expira em uma hora e só pode ser usado uma vez."
        ),
        action_label="Redefinir senha",
        link=link,
    )
    _send(message, link=link, token=token)
