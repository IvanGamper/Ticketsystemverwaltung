import streamlit as st
from sqlalchemy import create_engine, text, inspect
from Authorisation import (show_password_reset_page, show_password_change_page, show_login_page)
from Ticket import (get_columns)
from Datenbanken import (show_database_management)
import pandas as pd
from TicketShow import show_ticket_system
from fpdf import FPDF
from io import BytesIO

# DB-Konfiguration
DB_USER = "root"
DB_PASSWORD = "Xyz1343!!!"
DB_HOST = "127.0.0.1"
DB_PORT = "3306"
DB_NAME = "ticketsystemabkoo_copy"

# SQLAlchemy Engine
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

inspector = inspect(engine)

# Excel-Exportfunktion
def export_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# PDF-Exportfunktion
def export_to_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    col_width = 190 / len(df.columns)
    row_height = pdf.font_size + 2

    # Header
    for col in df.columns:
        pdf.cell(col_width, row_height, txt=str(col), border=1)
    pdf.ln(row_height)

    # Datenzeilen
    for i in range(len(df)):
        for item in df.iloc[i]:
            pdf.cell(col_width, row_height, txt=str(item), border=1)
        pdf.ln(row_height)

    pdf_bytes = pdf.output(dest='S').encode('latin1')  # latin1 = PDF-kompatibles Encoding
    return pdf_bytes

def export_section(engine):
    st.subheader("📤 Daten exportieren")

    # Tabellenname wählen
    tabellen = inspector.get_table_names()
    table_name = st.selectbox("Tabelle auswählen", tabellen)

    if st.button("Daten laden"):
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        st.dataframe(df)

        # Excel-Download
        excel_data = export_to_excel(df)
        st.download_button(
            label="⬇️ Als Excel herunterladen",
            data=excel_data,
            file_name=f"{table_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # PDF-Download
        pdf_data = export_to_pdf(df)
        st.download_button(
            label="⬇️ Als PDF herunterladen",
            data=pdf_data,
            file_name=f"{table_name}.pdf",
            mime="application/pdf"
        )

# Hilfsfunktion: Primärschlüssel einer Tabelle ermitteln
def get_primary_key(table):

    try:
        pk = inspector.get_pk_constraint(table)
        if pk and 'constrained_columns' in pk and pk['constrained_columns']:
            return pk['constrained_columns'][0]
        # Fallback: Suche nach Spalten mit 'id' im Namen
        columns = get_columns(table)
        for col in columns:
            if col.lower() == 'id':
                return col
        # Zweiter Fallback: Erste Spalte
        if columns:
            return columns[0]
        return None
    except:
        return None

def ensure_required_columns_exist():

    try:
        # Prüfen, ob die salt-Spalte bereits existiert
        mitarbeiter_columns = get_columns("mitarbeiter")

        # Salt-Spalte hinzufügen, falls nicht vorhanden
        if "salt" not in mitarbeiter_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mitarbeiter ADD COLUMN salt VARCHAR(64)"))

        # Reset-Token-Spalte hinzufügen, falls nicht vorhanden
        if "reset_token" not in mitarbeiter_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mitarbeiter ADD COLUMN reset_token VARCHAR(64)"))

        # Reset-Token-Expiry-Spalte hinzufügen, falls nicht vorhanden
        if "reset_token_expiry" not in mitarbeiter_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mitarbeiter ADD COLUMN reset_token_expiry DATETIME"))

        # Password-Change-Required-Spalte hinzufügen, falls nicht vorhanden
        if "password_change_required" not in mitarbeiter_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mitarbeiter ADD COLUMN password_change_required BOOLEAN DEFAULT FALSE"))

        return True
    except Exception as e:
        st.error(f"Fehler beim Überprüfen/Hinzufügen der erforderlichen Spalten: {str(e)}")
        return False

# Hauptfunktion
def main():
    # Seitenkonfiguration
    st.set_page_config(page_title="Ticketsystem mit Datenbankverwaltung", page_icon="🎫", layout="wide")

    # Sicherstellen, dass die erforderlichen Spalten existieren
    ensure_required_columns_exist()

    # Session-State initialisieren
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # Anmeldestatus prüfen
    if not st.session_state.logged_in:
        # Passwort-Wiederherstellung anzeigen, falls angefordert
        if "show_password_reset" in st.session_state and st.session_state.show_password_reset:
            show_password_reset_page()
        else:
            # Ansonsten Login-Seite anzeigen
            show_login_page()
    else:
        # Passwortänderung anzeigen, falls erforderlich
        if "password_change_required" in st.session_state and st.session_state.password_change_required and not st.session_state.get("password_changed", False):
            show_password_change_page()
        else:
            # Hauptanwendung anzeigen
            show_main_application()

    # Sidebar für Navigation und Datenbankinfo
    with st.sidebar:
        st.header("Datenbankübersicht")
        st.write(f"**Verbunden mit:** {DB_NAME} auf {DB_HOST}")

        # Tabellen anzeigen
        tabellen = inspector.get_table_names()
        with st.expander("Verfügbare Tabellen"):
            for table in tabellen:
                st.write(f"- {table}")

        # Datenbank-Schema anzeigen
        with st.expander("Datenbank-Schema"):
            for table_name in tabellen:
                st.write(f"**Tabelle: {table_name}**")
                columns = inspector.get_columns(table_name)
                for column in columns:
                    st.write(f"- {column['name']}")
                st.write("---")

# Hauptanwendung anzeigen
def show_main_application():


    # Seitenleiste mit Benutzerinformationen und Navigation
    with st.sidebar:

        st.write(f"Angemeldet als: **{st.session_state.username}**")

        # Abmelden-Button
        if st.button("Abmelden"):
            # Session-State zurücksetzen
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        # Modus wählen
        app_mode = st.radio(
            "Modus wählen:",
            ["Ticketsystem", "Datenbankverwaltung"],
            key="app_mode_selector"
        )

    # Hauptinhalt basierend auf dem gewählten Modus
    if app_mode == "Ticketsystem":
        show_ticket_system()
    else:  # app_mode == "Datenbankverwaltung"
        show_database_management()
        export_section(engine)




