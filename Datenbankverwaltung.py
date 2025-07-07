import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from datetime import datetime
import pymysql

# Seitenkonfiguration
st.set_page_config(page_title="Datenbankverwaltung", page_icon="🎫", layout="wide")

# DB-Konfiguration
DB_USER = "root"
DB_PASSWORD = "Xyz1343!!!"
DB_HOST = "127.0.0.1"
DB_PORT = "3306"
DB_NAME = "ticketsystem02"

# SQLAlchemy Engine
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

inspector = inspect(engine)

# Hauptfunktion
def main():




    # Session-State initialisieren
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False


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


st.title("🛠️ Datenbankverwaltung")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📋 Anzeigen", "✏️ Bearbeiten", "➕ Einfügen", "❌ Löschen"])

# Hilfsfunktion: Spaltennamen einer Tabelle
def get_columns(table):
    try:
        return [col["name"] for col in inspector.get_columns(table)]
    except:
        return []


# 📋 Tab 1: Anzeigen

with tab1:
    st.subheader("Tabelle anzeigen")
    try:
        tabellen = inspector.get_table_names()
        table_choice = st.selectbox("Wähle eine Tabelle", tabellen)
        if st.button("🔄 Daten laden"):
            df = pd.read_sql(f"SELECT * FROM {table_choice}", con=engine)
            st.dataframe(df)
    except Exception as e:
        st.error("❌ Fehler beim Laden:")
        st.exception(e)

# -----------------------------
# ✏️ Tab 2: Bearbeiten (ohne Session State)
# -----------------------------
with tab2:
    st.subheader("Datensätze bearbeiten")
    try:
        tabellen = inspector.get_table_names()
        table_choice_edit = st.selectbox("Tabelle wählen (Bearbeiten)", tabellen, key="edit_table")

        spalten_edit = get_columns(table_choice_edit)

        if not spalten_edit:
            st.warning("Keine Spalten gefunden.")
        else:
            # Wähle eine Primärspalte für die Identifikation der Datensätze
            id_spalte_edit = st.selectbox("Primärspalte wählen (z. B. ID)", spalten_edit, key="edit_id_spalte")

            # Lade die Daten aus der Datenbank
            load_button = st.button("🔄 Daten zum Bearbeiten laden", key="load_edit_data")

            if load_button or 'edit_loaded' in st.query_params:
                # Setze URL-Parameter, um den Zustand zu speichern
                if load_button:
                    st.query_params['edit_loaded'] = 'true'
                    st.query_params['edit_table'] = table_choice_edit

                try:
                    # Lade die Daten
                    df_edit = pd.read_sql(f"SELECT * FROM {table_choice_edit}", con=engine)

                    if df_edit.empty:
                        st.info(f"Tabelle '{table_choice_edit}' enthält keine Daten.")
                        # Entferne URL-Parameter
                        if 'edit_loaded' in st.query_params:
                            st.query_params.pop('edit_loaded')
                        if 'edit_table' in st.query_params:
                            st.query_params.pop('edit_table')
                    else:
                        # Zeige die Daten als normale Tabelle an
                        st.dataframe(df_edit)

                        # Erstelle ein Auswahlfeld für den zu bearbeitenden Datensatz
                        record_ids = df_edit[id_spalte_edit].astype(str).tolist()
                        selected_id = st.selectbox("Datensatz zum Bearbeiten auswählen:", record_ids, key="select_record_id")

                        if selected_id:
                            # Finde den ausgewählten Datensatz
                            selected_record = df_edit[df_edit[id_spalte_edit].astype(str) == selected_id].iloc[0]

                            # Erstelle ein Formular für die Bearbeitung
                            with st.form(key=f"edit_form_{selected_id}"):
                                st.subheader(f"Datensatz mit {id_spalte_edit} = {selected_id} bearbeiten")

                                # Erstelle für jede Spalte ein Eingabefeld
                                edited_values = {}
                                for col in spalten_edit:
                                    # ID-Spalte nicht bearbeitbar machen
                                    if col == id_spalte_edit:
                                        st.text_input(f"{col}", value=selected_record[col], disabled=True, key=f"edit_{col}_{selected_id}")
                                        edited_values[col] = selected_record[col]
                                    # Datum/Zeit-Spalten als nicht bearbeitbar anzeigen
                                    elif 'date' in col.lower() or 'time' in col.lower() or 'erstellt' in col.lower():
                                        date_value = selected_record[col]
                                        if pd.notna(date_value):
                                            if isinstance(date_value, pd.Timestamp):
                                                date_value = date_value.strftime("%Y-%m-%d %H:%M:%S")
                                        st.text_input(f"{col}", value=date_value, disabled=True, key=f"edit_{col}_{selected_id}")
                                        edited_values[col] = selected_record[col]
                                    # Alle anderen Spalten bearbeitbar machen
                                    else:
                                        current_value = selected_record[col] if pd.notna(selected_record[col]) else ""
                                        new_value = st.text_input(f"{col}", value=current_value, key=f"edit_{col}_{selected_id}")
                                        edited_values[col] = new_value

                                # Speichern-Button im Formular
                                submit_button = st.form_submit_button("💾 Änderungen speichern")

                            # Wenn der Speichern-Button geklickt wurde
                            if submit_button:
                                try:
                                    # Erstelle ein Dictionary mit den zu aktualisierenden Werten
                                    update_values = {}
                                    for col in spalten_edit:
                                        if col != id_spalte_edit and not ('date' in col.lower() or 'time' in col.lower() or 'erstellt' in col.lower()):
                                            original_value = str(selected_record[col]) if pd.notna(selected_record[col]) else ""
                                            new_value = edited_values[col]

                                            if original_value != new_value:
                                                update_values[col] = new_value
                                                st.write(f"Änderung in Spalte {col}: '{original_value}' -> '{new_value}'")

                                    # Wenn Änderungen vorhanden sind, führe ein UPDATE durch
                                    if update_values:
                                        set_clause = ", ".join([f"{col} = :{col}" for col in update_values.keys()])
                                        query = text(f"UPDATE {table_choice_edit} SET {set_clause} WHERE {id_spalte_edit} = :id")

                                        # Füge die ID zum Dictionary hinzu
                                        update_values["id"] = selected_id

                                        with engine.begin() as conn:
                                            conn.execute(query, update_values)

                                        st.success(f"✅ Datensatz mit {id_spalte_edit} = {selected_id} erfolgreich aktualisiert!")

                                        # Lade die Seite neu, um die aktualisierten Daten anzuzeigen
                                        st.rerun()
                                    else:
                                        st.info("ℹ️ Keine Änderungen zum Speichern gefunden.")
                                except Exception as e:
                                    st.error(f"❌ Fehler beim Aktualisieren des Datensatzes:")
                                    st.exception(e)

                except Exception as e:
                    st.error("❌ Fehler beim Laden der Daten zum Bearbeiten:")
                    st.exception(e)
    except Exception as e:
        st.error("❌ Fehler bei der Tabellenauswahl für die Bearbeitung:")
        st.exception(e)

# -----------------------------
# ➕ Tab 3: Einfügen
# -----------------------------
with tab3:
    st.subheader("Datensatz einfügen")
    try:
        tabellen = inspector.get_table_names()
        table_choice = st.selectbox("Tabelle wählen (Einfügen)", tabellen, key="insert_table")
        spalten = get_columns(table_choice)

        with st.form(key="insert_form"):
            st.subheader(f"Neuen Datensatz in '{table_choice}' einfügen")

            inputs = {}
            for spalte in spalten:
                # Spezielle Behandlung für Datum/Zeit-Spalten
                if 'date' in spalte.lower() or 'time' in spalte.lower() or 'erstellt' in spalte.lower():
                    # Aktuelles Datum als Standardwert für Datum/Zeit-Spalten
                    default_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    inputs[spalte] = st.text_input(f"{spalte}", value=default_value, key=f"insert_{spalte}")
                else:
                    inputs[spalte] = st.text_input(f"{spalte}", key=f"insert_{spalte}")

            submit_insert = st.form_submit_button("💾 Einfügen")

        if submit_insert:
            try:
                with engine.begin() as conn:
                    placeholders = ", ".join([f":{col}" for col in spalten])
                    query = text(f"INSERT INTO {table_choice} ({', '.join(spalten)}) VALUES ({placeholders})")
                    conn.execute(query, {col: inputs[col] for col in spalten})
                st.success(f"✅ Datensatz in '{table_choice}' eingefügt!")
            except Exception as e:
                st.error("❌ Fehler beim Einfügen:")
                st.exception(e)
    except Exception as e:
        st.error("❌ Fehler bei der Tabellenauswahl:")
        st.exception(e)

# -----------------------------
# ❌ Tab 4: Löschen (Überarbeitete Version)
# -----------------------------
with tab4:
    st.subheader("Datensatz löschen")
    try:
        tabellen = inspector.get_table_names()
        table_choice_delete = st.selectbox("Tabelle wählen (Löschen)", tabellen, key="delete_table")
        spalten_delete = get_columns(table_choice_delete)

        if not spalten_delete:
            st.warning("Keine Spalten gefunden.")
        else:
            # Wähle eine Primärspalte für die Identifikation der Datensätze
            id_spalte_delete = st.selectbox("Primärspalte wählen (z. B. ID)", spalten_delete, key="delete_id_spalte")

            # Lade die Daten aus der Datenbank
            if st.button("🔄 Daten zum Löschen laden", key="load_delete_data"):
                try:
                    # Lade die Daten
                    df_delete = pd.read_sql(f"SELECT * FROM {table_choice_delete}", con=engine)

                    if df_delete.empty:
                        st.info(f"Tabelle '{table_choice_delete}' enthält keine Daten.")
                    else:
                        # Zeige die Daten als normale Tabelle an
                        st.dataframe(df_delete)

                        # Erstelle ein Auswahlfeld für den zu löschenden Datensatz
                        record_ids = df_delete[id_spalte_delete].astype(str).tolist()

                        # Zeige die Auswahl und den Lösch-Button außerhalb eines Formulars an
                        selected_id_to_delete = st.selectbox("Datensatz zum Löschen auswählen:", record_ids, key="select_record_to_delete")

                        # Bestätigungsdialog
                        st.warning(f"⚠️ Sind Sie sicher, dass Sie den Datensatz mit {id_spalte_delete} = {selected_id_to_delete} löschen möchten?")

                        # Lösch-Button außerhalb des Formulars
                        if st.button("🗑️ Datensatz löschen", key="delete_record_button"):
                            try:
                                # Debug-Ausgabe
                                st.write(f"Versuche, Datensatz mit {id_spalte_delete} = {selected_id_to_delete} zu löschen...")

                                # Führe das DELETE-Statement aus
                                with engine.begin() as conn:
                                    result = conn.execute(
                                        text(f"DELETE FROM {table_choice_delete} WHERE {id_spalte_delete} = :id"),
                                        {"id": selected_id_to_delete}
                                    )

                                    # Prüfe, ob Zeilen betroffen waren
                                    if result.rowcount > 0:
                                        st.success(f"✅ Datensatz mit {id_spalte_delete} = {selected_id_to_delete} erfolgreich gelöscht!")
                                    else:
                                        st.warning(f"⚠️ Kein Datensatz mit {id_spalte_delete} = {selected_id_to_delete} gefunden oder gelöscht.")

                                # Lade die Daten neu, um die Änderung anzuzeigen
                                df_delete = pd.read_sql(f"SELECT * FROM {table_choice_delete}", con=engine)
                                st.dataframe(df_delete)

                            except Exception as e:
                                st.error(f"❌ Fehler beim Löschen des Datensatzes:")
                                st.exception(e)

                except Exception as e:
                    st.error("❌ Fehler beim Laden der Daten zum Löschen:")
                    st.exception(e)
    except Exception as e:
        st.error("❌ Fehler bei der Tabellenauswahl für das Löschen:")
        st.exception(e)

if __name__ == "__main__":
    main()