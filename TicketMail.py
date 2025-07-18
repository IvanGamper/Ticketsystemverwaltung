from imap_tools import MailBox
import streamlit as st
import pandas as pd
from sqlalchemy import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Assuming 'engine' is imported from 'Main.py' or defined globally in the main application
# from Main import engine
# For standalone execution, you might need to define a dummy engine or connect to a test DB


# Ticket-Status und Prioritäten
TICKET_STATUS = ["offen", "in bearbeitung", "erledigt"]
TICKET_PRIORITIES = ["niedrig", "mittel", "hoch"]


def initialize_session_state():
    """
    Initialisiert alle Session State Variablen für die Anwendung.
    """
    # Consolidate session state initialization
    defaults = {
        "employees": [], # Fallback, will be overwritten by DB if successful
        "email_config": {
            "email": "kolobok1329@googlemail.com",
            "password": "dqrmtejgeuxmzqtn",
            "imap_server": "imap.gmail.com",
            "email_limit": 10
        },
        "smtp_config": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "use_ssl": True,
            "sender_email": "",
            "app_password": ""
        },
        "ticket_filters": {
            "status_filter": TICKET_STATUS.copy(),
            "priority_filter": TICKET_PRIORITIES.copy(),
            "employee_filter": []
        },
        "fetched_emails": [],
        "selected_emails_for_conversion": [],
        "selected_employee_for_assignment": None,
        "selected_ticket_for_email": None,
        "email_content": {
            "recipient_email": "",
            "email_subject": "",
            "email_body": ""
        }
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Load employees from DB if not already loaded or if it's still the default fallback
    if not st.session_state.employees:
        try:
            from Main import engine # Import engine here to avoid circular dependency if Main imports this file
            with engine.connect() as conn:
                st.info("✅ Verbindung zur Datenbank erfolgreich.")
                result = conn.execute(text("SELECT ID_Mitarbeiter AS id, Name AS name, Email AS email FROM mitarbeiter"))
                rows = result.fetchall()
                if not rows:
                    st.warning("⚠️ Keine Mitarbeiter in der Tabelle gefunden.")
                else:
                    st.success(f"✅ {len(rows)} Mitarbeiter geladen.")
                st.session_state.employees = [dict(row._mapping) for row in rows]
        except Exception as e:
            st.error(f"❌ Fehler beim Laden der Mitarbeiter: {e}")
            import traceback
            st.text(traceback.format_exc())
            # Keep default employees if DB load fails


@st.cache_resource
def get_database_engine():
    """
    Caches the database engine to prevent re-creation on every rerun.
    """
    from Main import engine
    return engine


def fetch_emails(email, password, imap_server="imap.gmail.com", limit=10):
    """
    Holt E-Mails über IMAP ab, ohne sie zu löschen.
    """
    try:
        with MailBox(imap_server).login(email, password, initial_folder="INBOX") as mailbox:
            messages = mailbox.fetch(limit=limit, reverse=True)
            emails = []
            for msg in messages:
                emails.append({
                    "Von": msg.from_,
                    "Betreff": msg.subject,
                    "Datum": msg.date.strftime("%d.%m.%Y %H:%M"),
                    "Nachricht": msg.text or msg.html,
                    "Message-ID": msg.uid,  # Eindeutige ID für die E-Mail
                })
            return emails
    except Exception as e:
        st.error(f"Fehler beim Abrufen der E-Mails: {str(e)}")
        return [] # Return empty list on error for consistent type


def send_email(smtp_server, smtp_port, email, app_password, to_email, subject, body, use_ssl=True):
    """
    Sendet eine E-Mail über SMTP.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = email
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = None
        if use_ssl:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)

        server.login(email, app_password)
        server.sendmail(email, to_email, msg.as_string())
        server.quit()

        return True, "E-Mail erfolgreich gesendet!"

    except Exception as e:
        return False, f"Fehler beim Senden der E-Mail: {str(e)}"


def create_ticket_from_email(email_data, user_id=1, assigned_employee_id=None, priority="mittel"):
    """
    Erstellt ein Ticket aus einer E-Mail mit Mitarbeiterzuweisung.
    """
    engine = get_database_engine()

    try:
        title = email_data["Betreff"][:100]
        description = email_data["Nachricht"]
        customer_email = email_data["Von"]

        with engine.begin() as conn:
            # Check if customer exists and get ID, or insert new customer
            result = conn.execute(
                text("SELECT ID_Kunde FROM kunde WHERE Email = :email"),
                {"email": customer_email}
            )
            row = result.fetchone()

            kunde_id = None
            if row:
                kunde_id = row[0]
            else:
                # Insert new customer and get their ID
                conn.execute(text("""
                    INSERT INTO kunde (Name, Email)
                    VALUES (:name, :email)
                """), {
                    "name": customer_email.split("@")[0],  # Derive name from email
                    "email": customer_email
                })
                # Fetch the newly created customer's ID
                result = conn.execute(
                    text("SELECT ID_Kunde FROM kunde WHERE Email = :email"),
                    {"email": customer_email}
                )
                kunde_id = result.fetchone()[0]

            # Create ticket with extended fields
            conn.execute(text("""
                INSERT INTO ticket (Titel, Beschreibung, Erstellt_am, ID_Kunde, ID_Status, Priorität, ID_Mitarbeiter)
                VALUES (:title, :description, CURRENT_TIMESTAMP, :kunde_id, :id_status, :priority, :assigned_to)
            """), {
                "title": title,
                "description": description,
                "kunde_id": kunde_id,
                "id_status": 1,
                "priority": priority,
                "assigned_to": assigned_employee_id
            })

        employee_name = "Nicht zugewiesen"
        if assigned_employee_id:
            employee = next((emp for emp in st.session_state.employees if emp["id"] == assigned_employee_id), None)
            if employee:
                employee_name = employee["name"]

        return True, f"✅ Ticket aus E-Mail von {customer_email} erstellt und an {employee_name} zugewiesen."

    except Exception as e:
        st.error(f"Fehler beim Erstellen des Tickets: {str(e)}")
        import traceback
        st.text(traceback.format_exc())
        return False, f"Fehler beim Erstellen des Tickets: {str(e)}"


def show_email_inbox_tab():
    """
    Verbesserte E-Mail-Inbox mit interaktiver Tabelle und Ticketkonvertierung.
    """
    st.subheader("📥 E-Mail empfangen")
    auto_convert_new_emails_to_tickets()

    initialize_session_state()

    if "user_id" not in st.session_state or not st.session_state["user_id"]:
        st.warning("Benutzer nicht angemeldet. Bitte zuerst einloggen.")
        return

    st.markdown("### E-Mail-Konfiguration")
    col1, col2 = st.columns(2)

    with col1:
        email = st.text_input(
            "E-Mail-Adresse (IMAP-fähig)",
            value=st.session_state.email_config["email"],
            key="email_input"
        )
        imap_server = st.text_input(
            "IMAP-Server",
            value=st.session_state.email_config["imap_server"],
            help="z.B. imap.gmail.com für Gmail",
            key="imap_server_input"
        )

    with col2:
        password = st.text_input(
            "App-Passwort",
            type="password",
            value=st.session_state.email_config["password"],
            key="password_input"
        )
        email_limit = st.number_input(
            "Anzahl E-Mails",
            min_value=1,
            max_value=50,
            value=st.session_state.email_config["email_limit"],
            key="email_limit_input"
        )

    st.session_state.email_config.update({
        "email": email,
        "password": password,
        "imap_server": imap_server,
        "email_limit": email_limit
    })

    if st.button("📬 E-Mails abrufen"):
        if not email or not password:
            st.error("Bitte E-Mail-Adresse und Passwort eingeben.")
        else:
            with st.spinner("E-Mails werden abgerufen..."):
                emails = fetch_emails(email, password, imap_server, limit=email_limit)

            if not emails:
                st.info("Keine E-Mails gefunden oder Fehler beim Abrufen.")
            else:
                st.session_state.fetched_emails = emails
                st.success(f"{len(emails)} E-Mails erfolgreich abgerufen!")

    if st.session_state.fetched_emails:
        st.markdown("---")
        st.markdown("### 📧 Abgerufene E-Mails")

        emails_df = pd.DataFrame(st.session_state.fetched_emails)
        emails_df.insert(0, "Auswählen", False)

        selected_emails = st.data_editor(
            emails_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Auswählen": st.column_config.CheckboxColumn("Auswählen", width="small"),
                "Von": st.column_config.TextColumn("Absender", width="medium"),
                "Betreff": st.column_config.TextColumn("Betreff", width="large"),
                "Datum": st.column_config.TextColumn("Datum", width="small"),
                "Nachricht": st.column_config.TextColumn("Nachricht", width="large"),
            },
            disabled=["Von", "Betreff", "Datum", "Nachricht", "Message-ID"],
            key="email_table"
        )

        st.session_state.selected_emails_for_conversion = selected_emails[selected_emails["Auswählen"] == True].drop(columns=["Auswählen"]).to_dict("records")

        st.markdown("---")
        st.markdown("### 🎫 E-Mails in Tickets umwandeln")

        col1, col2 = st.columns(2)

        with col1:
            employee_options = ["Nicht zuweisen"] + [f"{emp["name"]} ({emp["email"]})" for emp in st.session_state.employees]
            selected_employee_option = st.selectbox(
                "Mitarbeiter zuweisen:",
                options=employee_options,
                index=0 if st.session_state.selected_employee_for_assignment is None else (
                    employee_options.index(st.session_state.selected_employee_for_assignment)
                    if st.session_state.selected_employee_for_assignment in employee_options else 0
                ),
                help="Wählen Sie einen Mitarbeiter aus, dem die neuen Tickets zugewiesen werden sollen.",
                key="employee_assignment_select"
            )

            priorities = ["niedrig", "mittel", "hoch"]
            selected_priority = st.selectbox(
                "Priorität für neue Tickets:",
                options=priorities,
                index=1,  # "mittel" als Standard
                key="ticket_priority_select"
            )

            assigned_employee_id = None
            if selected_employee_option != "Nicht zuweisen":
                employee_name = selected_employee_option.split(" (")[0]
                employee = next((emp for emp in st.session_state.employees if emp["name"] == employee_name), None)
                if employee:
                    assigned_employee_id = employee["id"]

            st.session_state.selected_employee_for_assignment = selected_employee_option
            st.session_state.selected_ticket_priority = selected_priority

        with col2:
            if st.button("🔄 Alle E-Mails auswählen"):
                emails_df.loc[:, "Auswählen"] = True
                st.session_state.fetched_emails = emails_df.drop(columns=["Auswählen"]).to_dict("records")
                st.rerun()

            if st.button("❌ Auswahl aufheben"):
                emails_df.loc[:, "Auswählen"] = False
                st.session_state.fetched_emails = emails_df.drop(columns=["Auswählen"]).to_dict("records")
                st.rerun()

        if st.button("🎫 Ausgewählte E-Mails in Tickets umwandeln", type="primary"):
            user_id = st.session_state.get("user_id")
            emails_to_convert = st.session_state.selected_emails_for_conversion

            if not emails_to_convert:
                st.warning("Keine E-Mails zum Konvertieren ausgewählt.")
            else:
                created = 0
                failed = 0
                messages = []

                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, email_data in enumerate(emails_to_convert):
                    status_text.text(f"Verarbeite E-Mail {i+1} von {len(emails_to_convert)}...")
                    progress_bar.progress((i + 1) / len(emails_to_convert))

                    success, msg = create_ticket_from_email(
                        email_data,
                        user_id=user_id,
                        assigned_employee_id=assigned_employee_id,
                        priority=st.session_state.selected_ticket_priority
                    )

                    messages.append(msg)
                    if success:
                        created += 1
                    else:
                        failed += 1

                progress_bar.empty()
                status_text.empty()

                if created > 0:
                    st.success(f"✅ {created} Tickets erfolgreich erstellt!")
                if failed > 0:
                    st.error(f"❌ {failed} Tickets konnten nicht erstellt werden.")

                with st.expander("📋 Detaillierte Ergebnisse"):
                    for msg in messages:
                        if "✅" in msg:
                            st.success(msg)
                        else:
                            st.error(msg)

        st.markdown("---")
        st.markdown("### 📄 E-Mail-Details")

        if emails_df is not None and len(emails_df) > 0:
            selected_index = st.selectbox(
                "E-Mail zur Detailansicht auswählen:",
                options=range(len(emails_df)),
                format_func=lambda x: f"{emails_df.iloc[x]["Betreff"]} ({emails_df.iloc[x]["Von"]})",
                key="email_detail_select"
            )

            if selected_index is not None:
                selected_email = emails_df.iloc[selected_index]

                with st.expander("📧 E-Mail-Inhalt", expanded=True):
                    st.markdown(f"**Von:** {selected_email["Von"]}")
                    st.markdown(f"**Betreff:** {selected_email["Betreff"]}")
                    st.markdown(f"**Datum:** {selected_email["Datum"]}")
                    st.markdown("**Nachricht:**")
                    st.text_area("", value=selected_email["Nachricht"], height=200, disabled=True, key="email_content_display")


@st.cache_data(ttl=600) # Cache for 10 minutes
def get_tickets_df():
    engine = get_database_engine()
    ticket_query = """
    SELECT 
        t.ID_Ticket,
        t.Titel,
        t.Beschreibung,
        s.name as Status,
        t.Priorität,
        t.Erstellt_am,
        k.Name as Kunde,
        k.Email as Kunde_Email,
        CASE 
            WHEN t.ID_Mitarbeiter IS NOT NULL THEN 
                (SELECT Name FROM mitarbeiter WHERE ID_Mitarbeiter = t.ID_Mitarbeiter)
            ELSE 'Nicht zugewiesen'
        END as Zugewiesen_an
    FROM ticket t
    LEFT JOIN kunde k ON t.ID_Kunde = k.ID_Kunde
    LEFT JOIN status s on t.ID_Status = s.ID_Status
    ORDER BY t.ID_Ticket DESC
    """
    with engine.connect() as conn:
        result = conn.execute(text(ticket_query))
        tickets_df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return tickets_df


def show_ticket_management():
    """
    Erweiterte Ticketverwaltung mit Status und Prioritäten.
    """
    st.subheader("🎫 Ticket-Verwaltung")

    initialize_session_state()

    try:
        tickets_df = get_tickets_df()

        if tickets_df.empty:
            st.info("Keine Tickets vorhanden.")
            return

        employee_names = tickets_df["Zugewiesen_an"].unique().tolist()
        if not st.session_state.ticket_filters["employee_filter"]:
            st.session_state.ticket_filters["employee_filter"] = employee_names

        st.markdown("### 🔍 Filter")
        col1, col2, col3 = st.columns(3)

        with col1:
            status_filter = st.multiselect(
                "Status:",
                options=TICKET_STATUS,
                default=st.session_state.ticket_filters["status_filter"],
                key="status_filter_select"
            )

        with col2:
            priority_filter = st.multiselect(
                "Priorität:",
                options=TICKET_PRIORITIES,
                default=st.session_state.ticket_filters["priority_filter"],
                key="priority_filter_select"
            )

        with col3:
            employee_filter = st.multiselect(
                "Zugewiesen an:",
                options=employee_names,
                default=st.session_state.ticket_filters["employee_filter"],
                key="employee_filter_select"
            )

        st.session_state.ticket_filters.update({
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "employee_filter": employee_filter
        })

        filtered_tickets = tickets_df[
            (tickets_df["Status"].isin(status_filter)) &
            (tickets_df["Prioritaet"].isin(priority_filter)) &
            (tickets_df["Zugewiesen_an"].isin(employee_filter))
            ]

        st.markdown("### 📋 Tickets")

        if not filtered_tickets.empty:
            column_config = {
                "ID_Ticket": st.column_config.NumberColumn("Ticket-ID", width="small"),
                "Titel": st.column_config.TextColumn("Titel", width="large"),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=TICKET_STATUS,
                    width="medium"
                ),
                "Prioritaet": st.column_config.SelectboxColumn(
                    "Priorität",
                    options=TICKET_PRIORITIES,
                    width="medium"
                ),
                "Kunde": st.column_config.TextColumn("Kunde", width="medium"),
                "Zugewiesen_an": st.column_config.TextColumn("Zugewiesen an", width="medium"),
                "Erstellt_am": st.column_config.DatetimeColumn("Erstellt am", width="medium"),
            }

            edited_tickets = st.data_editor(
                filtered_tickets[["ID_Ticket", "Titel", "Status", "Prioritaet", "Kunde", "Zugewiesen_an", "Erstellt_am"]],
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
                disabled=["ID_Ticket", "Titel", "Kunde", "Zugewiesen_an", "Erstellt_am"],
                key="ticket_table"
            )

            if st.button("💾 Änderungen speichern"):
                try:
                    engine = get_database_engine()
                    with engine.begin() as conn:
                        for index, row in edited_tickets.iterrows():
                            ticket_id = row["ID_Ticket"]
                            new_status = row["Status"]
                            new_priority = row["Prioritaet"]

                            conn.execute(text("""
                                UPDATE ticket 
                                SET Status = :status, Prioritaet = :priority
                                WHERE ID_Ticket = :ticket_id
                            """), {
                                "status": new_status,
                                "priority": new_priority,
                                "ticket_id": ticket_id
                            })

                    st.success("Änderungen erfolgreich gespeichert!")
                    get_tickets_df.clear() # Clear cache to refetch updated data
                    st.rerun()

                except Exception as e:
                    st.error(f"Fehler beim Speichern: {str(e)}")

        else:
            st.info("Keine Tickets entsprechen den ausgewählten Filtern.")

    except Exception as e:
        st.error(f"Fehler beim Laden der Tickets: {str(e)}")
        import traceback
        st.text(traceback.format_exc())


def show_employee_management():
    """
    Einfache Mitarbeiterverwaltung (da keine Liste vorhanden ist).
    """
    st.subheader("👥 Mitarbeiter-Verwaltung")

    initialize_session_state()

    st.info("📝 **Hinweis:** Da keine Mitarbeiterliste vorhanden ist, werden Standardmitarbeiter verwendet.")

    st.markdown("### 📋 Aktuelle Mitarbeiter")

    employees_df = pd.DataFrame(st.session_state.employees)

    st.data_editor(
        employees_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "name": st.column_config.TextColumn("Name", width="medium"),
            "email": st.column_config.TextColumn("E-Mail", width="large"),
        },
        disabled=True,
        key="employee_table"
    )

    st.markdown("---")
    st.markdown("### ➕ Neuen Mitarbeiter hinzufügen")

    with st.form("add_employee"):
        col1, col2 = st.columns(2)

        with col1:
            new_name = st.text_input("Name")

        with col2:
            new_email = st.text_input("E-Mail")

        submitted = st.form_submit_button("Mitarbeiter hinzufügen")

        if submitted:
            if new_name and new_email:
                # Add new employee to DB and then update session state
                try:
                    engine = get_database_engine()
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO mitarbeiter (Name, Email)
                            VALUES (:name, :email)
                        """), {"name": new_name, "email": new_email})
                    st.success(f"Mitarbeiter {new_name} erfolgreich hinzugefügt!")
                    # Re-initialize session state to fetch updated employee list from DB
                    initialize_session_state()
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Hinzufügen des Mitarbeiters zur Datenbank: {str(e)}")
                    import traceback
                    st.text(traceback.format_exc())
            else:
                st.error("Bitte Name und E-Mail eingeben.")


def show_email_tab():
    """
    Ursprüngliche E-Mail-Versendung mit State-Preservation.
    """
    st.subheader("📧 E-Mail versenden")

    initialize_session_state()

    st.markdown("### E-Mail-Konfiguration")

    col1, col2 = st.columns(2)

    with col1:
        smtp_server = st.text_input(
            "SMTP-Server",
            value=st.session_state.smtp_config["smtp_server"],
            help="z.B. smtp.gmail.com für Gmail",
            key="smtp_server_input"
        )
        smtp_port = st.number_input(
            "SMTP-Port",
            value=st.session_state.smtp_config["smtp_port"],
            min_value=1,
            max_value=65535,
            help="587 für TLS, 465 für SSL",
            key="smtp_port_input"
        )
        use_ssl = st.checkbox(
            "TLS verwenden",
            value=st.session_state.smtp_config["use_ssl"],
            help="Für Gmail sollte TLS aktiviert sein",
            key="use_ssl_checkbox"
        )

    with col2:
        sender_email = st.text_input(
            "Absender E-Mail",
            value=st.session_state.smtp_config["sender_email"],
            help="Ihre E-Mail-Adresse",
            key="sender_email_input"
        )
        app_password = st.text_input(
            "App-Passwort",
            type="password",
            value=st.session_state.smtp_config["app_password"],
            help="App-spezifisches Passwort (nicht Ihr normales Passwort)",
            key="app_password_input"
        )

    st.session_state.smtp_config.update({
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "use_ssl": use_ssl,
        "sender_email": sender_email,
        "app_password": app_password
    })

    st.markdown("---")

    st.markdown("### E-Mail-Inhalt")

    try:
        tickets_df = get_tickets_df()
    except Exception as e:
        st.error(f"Fehler beim Laden der Tickets: {str(e)}")
        tickets_df = pd.DataFrame()

    selected_ticket_data = None
    if not tickets_df.empty:
        st.markdown("#### Ticket-bezogene E-Mail (optional)")

        ticket_options = ["Keine Ticket-Auswahl"] + [f"#{row["ID_Ticket"]} - {row["Titel"]} ({row["Kunde"]})" for _, row in tickets_df.iterrows()]

        current_index = 0
        if st.session_state.selected_ticket_for_email and st.session_state.selected_ticket_for_email in ticket_options:
            current_index = ticket_options.index(st.session_state.selected_ticket_for_email)

        selected_ticket_option = st.selectbox(
            "Ticket auswählen (optional):",
            options=ticket_options,
            index=current_index,
            key="ticket_selection_for_email"
        )

        st.session_state.selected_ticket_for_email = selected_ticket_option

        if selected_ticket_option != "Keine Ticket-Auswahl":
            ticket_id = int(selected_ticket_option.split("#")[1].split(" - ")[0])
            selected_ticket_data = tickets_df[tickets_df["ID_Ticket"] == ticket_id].iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        default_recipient = st.session_state.email_content["recipient_email"]
        if selected_ticket_data is not None and selected_ticket_data["Kunde_Email"]:
            default_recipient = selected_ticket_data["Kunde_Email"]

        recipient_email = st.text_input(
            "Empfänger E-Mail",
            value=default_recipient,
            key="recipient_email_input"
        )

    with col2:
        default_subject = st.session_state.email_content["email_subject"]
        if selected_ticket_data is not None:
            default_subject = f"Ticket #{selected_ticket_data["ID_Ticket"]}: {selected_ticket_data["Titel"]}"

        email_subject = st.text_input(
            "Betreff",
            value=default_subject,
            key="email_subject_input"
        )

    default_body = st.session_state.email_content["email_body"]
    if selected_ticket_data is not None and not default_body:
        default_body = f"""Sehr geehrte Damen und Herren,\n\nbezugnehmend auf Ihr Ticket #{selected_ticket_data["ID_Ticket"]} "{selected_ticket_data["Titel"]}" möchten wir Sie über den aktuellen Status informieren.\n\n[Hier können Sie Ihre Nachricht eingeben]\n\nMit freundlichen Grüßen\nIhr Support-Team"""

    email_body = st.text_area(
        "E-Mail-Text",
        value=default_body,
        height=200,
        key="email_body_input"
    )

    st.session_state.email_content.update({
        "recipient_email": recipient_email,
        "email_subject": email_subject,
        "email_body": email_body
    })

    if st.checkbox("E-Mail-Vorschau anzeigen"):
        st.markdown("### Vorschau")
        st.markdown(f"**Von:** {sender_email}")
        st.markdown(f"**An:** {recipient_email}")
        st.markdown(f"**Betreff:** {email_subject}")
        st.markdown("**Nachricht:**")
        st.text(email_body)

    st.markdown("---")

    if st.button("📧 E-Mail senden", type="primary"):
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

                if selected_ticket_data is not None:
                    try:
                        from Ticket import log_ticket_change # Import here to avoid circular dependency
                        log_ticket_change(
                            selected_ticket_data["ID_Ticket"],
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
def auto_convert_new_emails_to_tickets():
    """
    Automatisch neue E-Mails abrufen und in Tickets umwandeln.
    Nur E-Mails, die noch nicht verarbeitet wurden (basierend auf Message-ID).
    """
    st.info("🔄 Automatischer Ticket-Erstellungsprozess gestartet...")

    config = st.session_state.email_config
    emails = fetch_emails(
        config["email"],
        config["password"],
        config["imap_server"],
        limit=config["email_limit"]
    )

    if not emails:
        st.info("Keine neuen E-Mails gefunden.")
        return

    engine = get_database_engine()
    new_tickets = 0
    skipped = 0
    errors = 0

    with engine.begin() as conn:
        for email in emails:
            msg_id = email.get("Message-ID")

            # Prüfen, ob Ticket mit dieser E-Mail bereits existiert (z.B. Message-ID speichern)
            result = conn.execute(text("""
                SELECT COUNT(*) FROM ticket_email_log WHERE message_id = :msg_id
            """), {"msg_id": msg_id})
            already_exists = result.scalar()

            if already_exists:
                skipped += 1
                continue

            # Ticket erstellen
            success, message = create_ticket_from_email(
                email_data=email,
                user_id=st.session_state.get("user_id", 1),
                assigned_employee_id=None,  # Oder Logik zur automatischen Zuweisung
                priority="mittel"           # Oder dynamisch z. B. basierend auf Betreff analysieren
            )

            if success:
                new_tickets += 1
                # Nachricht als verarbeitet markieren
                conn.execute(text("""
                    INSERT INTO ticket_email_log (message_id, erstellt_am)
                    VALUES (:msg_id, CURRENT_TIMESTAMP)
                """), {"msg_id": msg_id})
            else:
                errors += 1
                st.warning(message)

    st.success(f"🎫 {new_tickets} neue Tickets erstellt.")
    if skipped:
        st.info(f"🔁 {skipped} E-Mails wurden übersprungen (bereits verarbeitet).")
    if errors:
        st.error(f"⚠️ {errors} Fehler bei der Ticket-Erstellung.")
