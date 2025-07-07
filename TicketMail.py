from imap_tools import MailBox
import streamlit as st
import pandas as pd
from sqlalchemy import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def fetch_emails(email, password, imap_server="imap.gmail.com"):
    """
    Holt die letzten 5 E-Mails aus dem Posteingang
    """
    try:
        with MailBox(imap_server).login(email, password, initial_folder="INBOX") as mailbox:
            messages = mailbox.fetch(limit=10, reverse=True)
            emails = []
            for msg in messages:
                emails.append({
                    "Von": msg.from_,
                    "Betreff": msg.subject,
                    "Datum": msg.date.strftime("%d.%m.%Y %H:%M"),
                    "Nachricht": msg.text or msg.html,
                })
            return emails
    except Exception as e:
        return f"Fehler beim Abrufen der E-Mails: {str(e)}"

# E-Mail-Funktionen
def send_email(smtp_server, smtp_port, email, app_password, to_email, subject, body, use_ssl=True):
    """
    Sendet eine E-Mail über SMTP
    """
    try:
        # E-Mail-Nachricht erstellen
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = to_email
        msg['Subject'] = subject

        # Text zur E-Mail hinzufügen
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # SMTP-Verbindung aufbauen
        if use_ssl:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()  # TLS aktivieren
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)

        # Anmelden
        server.login(email, app_password)

        # E-Mail senden
        text = msg.as_string()
        server.sendmail(email, to_email, text)
        server.quit()

        return True, "E-Mail erfolgreich gesendet!"

    except Exception as e:
        return False, f"Fehler beim Senden der E-Mail: {str(e)}"

def show_email_tab():

    from Main import engine
    from Ticket import log_ticket_change

    """
    Zeigt das EMAIL-Tab mit E-Mail-Versendungsfunktionalität an
    """
    st.subheader("📧 E-Mail versenden")

    # E-Mail-Konfiguration
    st.markdown("### E-Mail-Konfiguration")

    col1, col2 = st.columns(2)

    with col1:
        smtp_server = st.text_input("SMTP-Server", value="smtp.gmail.com", help="z.B. smtp.gmail.com für Gmail")
        smtp_port = st.number_input("SMTP-Port", value=587, min_value=1, max_value=65535, help="587 für TLS, 465 für SSL")
        use_ssl = st.checkbox("TLS verwenden", value=True, help="Für Gmail sollte TLS aktiviert sein")

    with col2:
        sender_email = st.text_input("Absender E-Mail", help="Ihre E-Mail-Adresse")
        app_password = st.text_input("App-Passwort", type="password", help="App-spezifisches Passwort (nicht Ihr normales Passwort)")

    st.markdown("---")

    # E-Mail-Inhalt
    st.markdown("### E-Mail-Inhalt")

    # Ticket-Auswahl für E-Mail-Kontext
    try:
        ticket_query = """
        SELECT t.ID_Ticket, t.Titel, k.Name as Kunde, k.Email as Kunde_Email
        FROM ticket t
        LEFT JOIN kunde k ON t.ID_Kunde = k.ID_Kunde
        ORDER BY t.ID_Ticket DESC
        """
        with engine.connect() as conn:
            result = conn.execute(text(ticket_query))
            tickets_df = pd.DataFrame(result.fetchall(), columns=result.keys())
    except Exception as e:
        st.error(f"Fehler beim Laden der Tickets: {str(e)}")
        tickets_df = pd.DataFrame()

    # Ticket-Auswahl
    if not tickets_df.empty:
        st.markdown("#### Ticket-bezogene E-Mail (optional)")

        ticket_options = ["Keine Ticket-Auswahl"] + [f"#{row['ID_Ticket']} - {row['Titel']} ({row['Kunde']})" for _, row in tickets_df.iterrows()]
        selected_ticket_option = st.selectbox("Ticket auswählen (optional):", options=ticket_options)

        selected_ticket_data = None
        if selected_ticket_option != "Keine Ticket-Auswahl":
            ticket_id = int(selected_ticket_option.split("#")[1].split(" - ")[0])
            selected_ticket_data = tickets_df[tickets_df['ID_Ticket'] == ticket_id].iloc[0]

    # E-Mail-Formular
    col1, col2 = st.columns(2)

    with col1:
        # Empfänger vorausfüllen, wenn Ticket ausgewählt
        default_recipient = ""
        if 'selected_ticket_data' in locals() and selected_ticket_data is not None and selected_ticket_data['Kunde_Email']:
            default_recipient = selected_ticket_data['Kunde_Email']

        recipient_email = st.text_input("Empfänger E-Mail", value=default_recipient)

    with col2:
        # Betreff vorausfüllen, wenn Ticket ausgewählt
        default_subject = ""
        if 'selected_ticket_data' in locals() and selected_ticket_data is not None:
            default_subject = f"Ticket #{selected_ticket_data['ID_Ticket']}: {selected_ticket_data['Titel']}"

        email_subject = st.text_input("Betreff", value=default_subject)

    # E-Mail-Text
    default_body = ""
    if 'selected_ticket_data' in locals() and selected_ticket_data is not None:
        default_body = f"""Sehr geehrte Damen und Herren,

bezugnehmend auf Ihr Ticket #{selected_ticket_data['ID_Ticket']} "{selected_ticket_data['Titel']}" möchten wir Sie über den aktuellen Status informieren.

[Hier können Sie Ihre Nachricht eingeben]

Mit freundlichen Grüßen
Ihr Support-Team"""

    email_body = st.text_area("E-Mail-Text", value=default_body, height=200)

    # Vorschau
    if st.checkbox("E-Mail-Vorschau anzeigen"):
        st.markdown("### Vorschau")
        st.markdown(f"**Von:** {sender_email}")
        st.markdown(f"**An:** {recipient_email}")
        st.markdown(f"**Betreff:** {email_subject}")
        st.markdown("**Nachricht:**")
        st.text(email_body)

    st.markdown("---")

    # Senden-Button
    if st.button("📧 E-Mail senden", type="primary"):
        # Validierung
        if not sender_email:
            st.error("Bitte geben Sie eine Absender-E-Mail-Adresse ein.")
        elif not app_password:
            st.error("Bitte geben Sie ein App-Passwort ein.")
        elif not recipient_email:
            st.error("Bitte geben Sie eine Empfänger-E-Mail-Adresse ein.")
        elif not email_subject:
            st.error("Bitte geben Sie einen Betreff ein.")
        elif not email_body:
            st.error("Bitte geben Sie einen E-Mail-Text ein.")
        else:
            # E-Mail senden
            with st.spinner("E-Mail wird gesendet..."):
                success, message = send_email(
                    smtp_server=smtp_server,
                    smtp_port=smtp_port,
                    email=sender_email,
                    app_password=app_password,
                    to_email=recipient_email,
                    subject=email_subject,
                    body=email_body,
                    use_ssl=use_ssl
                )

            if success:
                st.success(message)

                # E-Mail-Versendung in Ticket-Historie protokollieren (falls Ticket ausgewählt)
                if 'selected_ticket_data' in locals() and selected_ticket_data is not None:
                    try:
                        log_ticket_change(
                            selected_ticket_data['ID_Ticket'],
                            "E-Mail gesendet",
                            "",
                            f"E-Mail an {recipient_email} mit Betreff '{email_subject}' gesendet",
                            st.session_state.user_id
                        )
                        st.info("E-Mail-Versendung wurde in der Ticket-Historie protokolliert.")
                    except Exception as e:
                        st.warning(f"E-Mail wurde gesendet, aber Protokollierung in Ticket-Historie fehlgeschlagen: {str(e)}")

            else:
                st.error(message)

    # Hilfe-Bereich
    with st.expander("ℹ️ Hilfe zur E-Mail-Konfiguration"):
        st.markdown("""
        ### Gmail-Konfiguration:
        - **SMTP-Server:** smtp.gmail.com
        - **Port:** 587 (mit TLS)
        - **App-Passwort:** Sie benötigen ein App-spezifisches Passwort, nicht Ihr normales Gmail-Passwort
        
        ### App-Passwort erstellen (Gmail):
        1. Gehen Sie zu Ihrem Google-Konto
        2. Wählen Sie "Sicherheit"
        3. Aktivieren Sie die 2-Faktor-Authentifizierung (falls noch nicht aktiviert)
        4. Wählen Sie "App-Passwörter"
        5. Erstellen Sie ein neues App-Passwort für "Mail"
        6. Verwenden Sie dieses 16-stellige Passwort hier
        
        ### Andere E-Mail-Anbieter:
        - **Outlook/Hotmail:** smtp-mail.outlook.com, Port 587
        - **Yahoo:** smtp.mail.yahoo.com, Port 587
        - Konsultieren Sie die Dokumentation Ihres E-Mail-Anbieters für spezifische Einstellungen
        """)

def show_email_inbox_tab():
    st.subheader("📥 E-Mail empfangen")

    col1, col2 = st.columns(2)
    with col1:
        email = st.text_input("E-Mail-Adresse (IMAP-fähig)")
    with col2:
        password = st.text_input("App-Passwort", type="password")

    imap_server = st.text_input("IMAP-Server", value="imap.gmail.com", help="z.B. imap.gmail.com für Gmail")

    if st.button("📬 E-Mails abrufen"):
        with st.spinner("E-Mails werden abgerufen..."):
            emails = fetch_emails(email, password, imap_server)
        if isinstance(emails, str):  # Fehlertext
            st.error(emails)
        else:
            if not emails:
                st.info("Keine E-Mails gefunden.")
            for i, mail in enumerate(emails, 1):
                with st.expander(f"{i}. {mail['Betreff']} ({mail['Datum']})"):
                    st.markdown(f"**Von:** {mail['Von']}")
                    st.markdown("---")
                    st.text(mail['Nachricht'])