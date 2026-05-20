import smtplib
from email.mime.text import MIMEText
from app.core.config import settings


def send_email(to: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())


def send_budget_warning(to: str, spent: float, budget: float) -> None:
    pct = int((spent / budget) * 100)
    send_email(
        to=to,
        subject=f"⚠️ Budget Alert: You've used {pct}% of your monthly budget",
        body=f"""
        <h2>Budget Warning</h2>
        <p>You've spent <strong>${spent:,.2f}</strong> of your
        <strong>${budget:,.2f}</strong> monthly budget ({pct}%).</p>
        <p>You have <strong>${budget - spent:,.2f}</strong> remaining.</p>
        """,
    )


def send_budget_exceeded(to: str, spent: float, budget: float) -> None:
    over = spent - budget
    send_email(
        to=to,
        subject="🚨 Budget Exceeded: You've gone over your monthly budget",
        body=f"""
        <h2>Budget Exceeded</h2>
        <p>You've spent <strong>${spent:,.2f}</strong> against your
        <strong>${budget:,.2f}</strong> monthly budget.</p>
        <p>You are <strong>${over:,.2f}</strong> over budget.</p>
        """,
    )
