
import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime

# Annahme: Diese Module sind korrekt eingerichtet und verfügbar
from Authorisation import (generate_salt, hash_password, get_searchable_columns, search_table, get_column_types)
from Ticket import (create_ticket_relations, get_columns)

# ==============================================================================
# 2. HELPER & DATA LOGIC FUNCTIONS
# ==============================================================================

def get_delete_plan(table_name):
    """
    Erstellt einen kontextabhängigen Plan für den schrittweisen Löschvorgang.
    Gibt die Anzahl der Schritte und die Beschreibung für jeden Schritt zurück.
    """
    plans = {
        "ticket": [
            {"name": "Ticket-Kommentare", "query": "DELETE FROM ticket_kommentar WHERE ID_Ticket = :id"},
            {"name": "Ticket-Historie", "query": "DELETE FROM ticket_historie WHERE ID_Ticket = :id"},
            {"name": "Ticket-Mitarbeiter-Zuordnungen", "query": "DELETE FROM ticket_mitarbeiter WHERE ID_Ticket = :id"},
            {"name": "Ticket-Kategorie-Zuordnungen", "query": "DELETE FROM ticket_kategorie WHERE ID_Ticket = :id"},
            {"name": "Ticket", "query": "DELETE FROM ticket WHERE ID_Ticket = :id"}
        ],
        "mitarbeiter": [
            {"name": "Ticket-Mitarbeiter-Zuordnungen", "query": "DELETE FROM ticket_mitarbeiter WHERE ID_Mitarbeiter = :id"},
            {"name": "Ticket-Historie-Einträge", "query": "UPDATE ticket_historie SET Geändert_von = NULL WHERE Geändert_von = :id"},
            {"name": "Tickets", "query": "UPDATE ticket SET ID_Mitarbeiter = NULL WHERE ID_Mitarbeiter = :id"},
            {"name": "Kommentare", "query": "UPDATE ticket_kommentar SET Erstellt_von = NULL WHERE Erstellt_von = :id"},
            {"name": "Mitarbeiter", "query": "DELETE FROM mitarbeiter WHERE ID_Mitarbeiter = :id"}
        ],
        "kunde": [
            {"name": "Tickets", "query": "UPDATE ticket SET ID_Kunde = NULL WHERE ID_Kunde = :id"},
            {"name": "Kunde", "query": "DELETE FROM kunde WHERE ID_Kunde = :id"}
        ],
        "kategorie": [
            {"name": "Ticket-Kategorie-Zuordnungen", "query": "DELETE FROM ticket_kategorie WHERE ID_Kategorie = :id"},
            {"name": "Kategorie", "query": "DELETE FROM kategorie WHERE ID_Kategorie = :id"}
        ],
        "status": [
            {"name": "Tickets", "query": "UPDATE ticket SET ID_Status = NULL WHERE ID_Status = :id"},
            {"name": "Status", "query": "DELETE FROM status WHERE ID_Status = :id"}
        ],
        "rolle": [
            {"name": "Mitarbeiter", "query": "UPDATE mitarbeiter SET ID_Rolle = NULL WHERE ID_Rolle = :id"},
            {"name": "Rolle", "query": "DELETE FROM rolle WHERE ID_Rolle = :id"}
        ]
    }
    return plans.get(table_name, [{"name": table_name, "query": f"DELETE FROM {table_name} WHERE {{id_column}} = :id"}])

def execute_delete_step(engine, step_info, id_value, id_column):
    """Führt einen einzelnen, definierten Löschschritt aus."""
    try:
        with engine.begin() as conn:
            # Platzhalter für die ID-Spalte im generischen Fall ersetzen
            query_str = step_info['query'].format(id_column=id_column)
            conn.execute(text(query_str), {"id": id_value})
        return True
    except Exception as e:
        st.error(f"❌ Fehler beim Ausführen des Schritts '{step_info['name']}': {e}")
        if "foreign key constraint fails" in str(e).lower():
            st.error("**Fremdschlüssel-Constraint-Fehler!** Der Datensatz kann nicht gelöscht werden, da er noch von anderen Tabellen referenziert wird.")
        return False

def render_insert_form(engine, table_name, columns):
    """Rendert ein Formular zur Eingabe eines einzelnen Datensatzes."""
    with st.form(key=f"insert_form_{table_name}"):
        st.subheader(f"Neuen Datensatz in '{table_name}' einfügen")
        inputs = {}
        for col in columns:
            is_datetime = 'date' in col.lower() or 'time' in col.lower() or 'erstellt' in col.lower()
            is_password = 'password' in col.lower() and table_name == 'mitarbeiter'

            if is_datetime:
                inputs[col] = st.text_input(f"{col}", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), key=f"insert_{col}")
            elif is_password:
                inputs[col] = st.text_input(f"{col}", type="password", key=f"insert_{col}")
            else:
                inputs[col] = st.text_input(f"{col}", key=f"insert_{col}")

        if st.form_submit_button("💾 Einfügen"):
            # Logik zum Einfügen...
            pass # Die Logik wird in der Hauptfunktion behandelt, um den Zustand sauber zu halten

# ==============================================================================
# 3. UI COMPONENTS
# ==============================================================================

def show_step_by_step_delete_ui(engine, table_name, id_column, id_value):
    """Zeigt die UI für den schrittweisen Löschvorgang an."""
    # Initialisierung des Löschplans
    if "delete_plan" not in st.session_state:
        st.session_state.delete_plan = get_delete_plan(table_name)
        st.session_state.delete_step = 0

    plan = st.session_state.delete_plan
    step_index = st.session_state.delete_step
    total_steps = len(plan)

    # Fortschrittsanzeige
    st.progress((step_index / total_steps))
    st.info(f"Lösche '{table_name}' mit ID {id_value} - Schritt {step_index + 1} von {total_steps}")

    # Abbruchbedingung: Alle Schritte abgeschlossen
    if step_index >= total_steps:
        st.success(f"✅ Alle Löschschritte erfolgreich abgeschlossen!")
        # Reset state
        for key in ["delete_plan", "delete_step", "delete_state"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
        return

    current_step_info = plan[step_index]
    st.subheader(f"Schritt {step_index + 1}: {current_step_info['name']}")
    st.warning(f"⚠️ Möchten Sie diesen Schritt ausführen? Diese Aktion kann nicht rückgängig gemacht werden!")

    col1, col2, col3 = st.columns([2, 2, 3])
    if col1.button("✅ Ja, ausführen", key=f"confirm_step_{step_index}"):
        if execute_delete_step(engine, current_step_info, id_value, id_column):
            st.session_state.delete_step += 1
            st.rerun()

    if col2.button("❌ Überspringen", key=f"skip_step_{step_index}"):
        st.session_state.delete_step += 1
        st.rerun()

    if col3.button("🛑 Gesamten Löschvorgang abbrechen", key="cancel_all_delete"):
        for key in ["delete_plan", "delete_step", "delete_state"]:
            if key in st.session_state:
                del st.session_state[key]
        st.warning("Löschvorgang abgebrochen.")
        st.rerun()

def show_view_tab(engine, inspector):
    """Rendert den 'Anzeigen'-Tab mit Tabellenauswahl und Suche."""
    st.subheader("Tabelle anzeigen")
    try:
        tabellen = inspector.get_table_names()
        table_choice = st.selectbox("Wähle eine Tabelle", tabellen, key="view_table")

        # Suchfunktion für die ausgewählte Tabelle
        st.subheader("🔍 Tabellensuche")

        # Durchsuchbare Spalten ermitteln
        searchable_columns = get_searchable_columns(table_choice)

        # Suchoptionen
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            search_term = st.text_input("Suchbegriff eingeben", placeholder="Suchbegriff...", key=f"search_term_{table_choice}")

        with col2:
            # Mehrfachauswahl für Spalten
            selected_columns = st.multiselect(
                "Zu durchsuchende Spalten (leer = alle)",
                options=searchable_columns,
                key=f"search_columns_{table_choice}"
            )

        with col3:
            # Erweiterte Suchoptionen
            exact_match = st.checkbox("Exakte Übereinstimmung", key=f"exact_match_{table_choice}")
            case_sensitive = st.checkbox("Groß-/Kleinschreibung beachten", key=f"case_sensitive_{table_choice}")

        # Suchbutton
        search_clicked = st.button("Suchen", key=f"search_button_{table_choice}")

        # Daten laden - entweder Suchergebnisse oder alle Daten
        if search_clicked and search_term:
            # Suche durchführen
            results = search_table(
                table_name=table_choice,
                search_term=search_term,
                search_columns=selected_columns if selected_columns else None,
                exact_match=exact_match,
                case_sensitive=case_sensitive
            )

            # Ergebnisse anzeigen
            if results.empty:
                st.warning(f"Keine Ergebnisse für '{search_term}' gefunden.")
                # Alle Daten anzeigen als Fallback
                df = pd.read_sql(f"SELECT * FROM {table_choice}", con=engine)
                st.write("Stattdessen werden alle Daten angezeigt:")
            else:
                st.success(f"{len(results)} Ergebnisse gefunden.")
                df = results
        else:
            # Alle Daten anzeigen
            df = pd.read_sql(f"SELECT * FROM {table_choice}", con=engine)

        # Daten anzeigen
        st.dataframe(df, use_container_width=True)

        # Button zum Zurücksetzen der Suche
        if search_clicked and search_term:
            if st.button("Suche zurücksetzen", key=f"reset_search_{table_choice}"):
                st.rerun()

        # Optional: In Session speichern für andere Tabs
        st.session_state["last_viewed_table"] = table_choice
        st.session_state["last_viewed_df"] = df.copy()

    except Exception as e:
        st.error("❌ Fehler beim Laden:")
        st.exception(e)


def show_edit_tab(engine, inspector):
    """Rendert den 'Bearbeiten'-Tab mit dem interaktiven Data Editor."""
    st.subheader("Datensätze bearbeiten (interaktiv)")
    try:
        tabellen = inspector.get_table_names()
        table_choice_edit = st.selectbox("Tabelle wählen (Bearbeiten)", tabellen, key="edit_table_editor")
        spalten = get_columns(table_choice_edit)
        id_spalte = st.selectbox("Primärschlüsselspalte", spalten, key="primary_column_editor")

        if "original_df" not in st.session_state:
            st.session_state.original_df = pd.DataFrame()
        if "edited_df" not in st.session_state:
            st.session_state.edited_df = pd.DataFrame()

        if st.button("🔄 Daten laden (Editiermodus)"):
            df = pd.read_sql(f"SELECT * FROM {table_choice_edit}", con=engine)
            st.session_state.original_df = df.copy()
            st.session_state.edited_df = df.copy()

        if not st.session_state.original_df.empty:
            st.markdown("✏️ **Daten bearbeiten – Änderungen werden erst nach dem Speichern übernommen.**")
            st.session_state.edited_df = st.data_editor(
                st.session_state.edited_df,
                use_container_width=True,
                num_rows="fixed",
                key="editable_df"
            )

            if st.button("💾 Änderungen speichern"):
                df = st.session_state.original_df
                edited_df = st.session_state.edited_df
                delta = df.compare(edited_df, keep_shape=True, keep_equal=True)
                rows_to_update = delta.dropna(how="all").index.tolist()

                if not rows_to_update:
                    st.info("Keine Änderungen erkannt.")
                else:
                    try:
                        with engine.begin() as conn:
                            for idx in rows_to_update:
                                row = edited_df.loc[idx]
                                original_row = df.loc[idx]

                                update_fields = {}
                                for col in spalten:
                                    if row[col] != original_row[col]:
                                        update_fields[col] = row[col]

                                if update_fields:
                                    set_clause = ", ".join([f"{col} = :{col}" for col in update_fields])
                                    query = text(
                                        f"UPDATE {table_choice_edit} SET {set_clause} WHERE {id_spalte} = :id_value"
                                    )
                                    update_fields["id_value"] = row[id_spalte]
                                    conn.execute(query, update_fields)

                        st.success("✅ Änderungen erfolgreich gespeichert.")
                        # Daten neu laden
                        df = pd.read_sql(f"SELECT * FROM {table_choice_edit}", con=engine)
                        st.session_state.original_df = df.copy()
                        st.session_state.edited_df = df.copy()
                        st.rerun()

                    except Exception as e:
                        st.error("❌ Fehler beim Speichern:")
                        st.exception(e)

    except Exception as e:
        st.error("❌ Fehler beim Bearbeiten der Daten:")
        st.exception(e)

def show_insert_tab(engine, inspector):
    """Rendert den 'Einfügen'-Tab für einzelne und mehrere Datensätze."""
    st.subheader("Datensatz einfügen")
    # Tabs für einzelne und mehrfache Einfügung
    insert_tab1, insert_tab2 = st.tabs(["Einzelner Datensatz", "Mehrere Datensätze"])

    try:
        tabellen = inspector.get_table_names()
        table_choice = st.selectbox("Tabelle wählen (Einfügen)", tabellen, key="insert_table")
        spalten = get_columns(table_choice)
        spalten_typen = get_column_types(table_choice)

        # Tab für einzelnen Datensatz
        with insert_tab1:
            with st.form(key="insert_form_single"):
                st.subheader(f"Neuen Datensatz in '{table_choice}' einfügen")

                inputs = {}
                for spalte in spalten:
                    # Spezielle Behandlung für Datum/Zeit-Spalten
                    if 'date' in spalte.lower() or 'time' in spalte.lower() or 'erstellt' in spalte.lower():
                        # Aktuelles Datum als Standardwert für Datum/Zeit-Spalten
                        default_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        inputs[spalte] = st.text_input(f"{spalte}", value=default_value, key=f"insert_{spalte}")
                    # Spezielle Behandlung für Passwort-Spalten
                    elif 'password' in spalte.lower() and table_choice.lower() == 'mitarbeiter':
                        password = st.text_input(f"{spalte}", type="password", key=f"insert_{spalte}")
                        # Salt wird automatisch generiert und das Passwort gehasht
                        inputs[spalte] = password  # Wird später verarbeitet
                    else:
                        inputs[spalte] = st.text_input(f"{spalte}", key=f"insert_{spalte}")

                submit_insert = st.form_submit_button("💾 Einfügen")

            if submit_insert:
                try:
                    # Spezielle Behandlung für Mitarbeiter-Tabelle mit Passwort-Hashing
                    if table_choice.lower() == 'mitarbeiter' and 'Password_hash' in spalten:
                        # Salt generieren und Passwort hashen
                        salt = generate_salt()
                        password = inputs.get('Password_hash', '')
                        password_hash = hash_password(password, salt)

                        # Werte aktualisieren
                        inputs['Password_hash'] = password_hash
                        inputs['salt'] = salt

                    with engine.begin() as conn:
                        # Nur Spalten einfügen, für die Werte vorhanden sind
                        valid_spalten = [col for col in spalten if inputs.get(col)]
                        placeholders = ", ".join([f":{col}" for col in valid_spalten])
                        query = text(f"INSERT INTO {table_choice} ({', '.join(valid_spalten)}) VALUES ({placeholders})")
                        result = conn.execute(query, {col: inputs[col] for col in valid_spalten})

                        # Wenn es sich um ein Ticket handelt, automatische Beziehungen erstellen
                        if table_choice == "ticket":
                            ticket_id = result.lastrowid
                            ID_Mitarbeiter = inputs.get("ID_Mitarbeiter")

                            # Standard-Kategorie (ID 1) verwenden
                            create_ticket_relations(ticket_id, ID_Mitarbeiter, 1)

                    st.success(f"✅ Datensatz in '{table_choice}' eingefügt!")
                except Exception as e:
                    st.error("❌ Fehler beim Einfügen:")
                    st.exception(e)

        # Tab für mehrere Datensätze
        with insert_tab2:
            st.subheader(f"Mehrere Datensätze in '{table_choice}' einfügen")

            # Initialisiere leeren DataFrame für die Eingabe, wenn noch nicht vorhanden
            if "multi_insert_df" not in st.session_state or st.session_state.get("last_multi_insert_table") != table_choice:
                # Erstelle leeren DataFrame mit den Spalten der Tabelle
                empty_df = pd.DataFrame(columns=spalten)

                # Füge eine leere Zeile hinzu
                empty_row = {col: "" for col in spalten}
                # Spezielle Behandlung für Datum/Zeit-Spalten
                for col in spalten:
                    if 'date' in col.lower() or 'time' in col.lower() or 'erstellt' in col.lower():
                        empty_row[col] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                empty_df = pd.concat([empty_df, pd.DataFrame([empty_row])], ignore_index=True)

                st.session_state["multi_insert_df"] = empty_df
                st.session_state["last_multi_insert_table"] = table_choice

            # Zeige Hinweis
            st.info("Fügen Sie Zeilen hinzu und bearbeiten Sie die Daten. Klicken Sie dann auf 'Speichern'.")

            # Daten-Editor für mehrere Zeilen
            edited_df = st.data_editor(
                st.session_state["multi_insert_df"],
                use_container_width=True,
                num_rows="dynamic",
                key="multi_insert_editor"
            )

            # Speichern-Button
            if st.button("💾 Alle Datensätze einfügen"):
                if edited_df.empty or edited_df.iloc[0].isnull().all():
                    st.warning("Keine Daten zum Einfügen vorhanden.")
                else:
                    try:
                        success_count = 0
                        error_count = 0

                        with engine.begin() as conn:
                            for _, row in edited_df.iterrows():
                                # Leere Zeilen überspringen
                                if row.isnull().all():
                                    continue

                                # Nur Spalten einfügen, für die Werte vorhanden sind
                                valid_spalten = [col for col in spalten if pd.notna(row[col]) and row[col] != ""]
                                if not valid_spalten:
                                    continue

                                try:
                                    # Spezielle Behandlung für Mitarbeiter-Tabelle mit Passwort-Hashing
                                    values = {}
                                    for col in valid_spalten:
                                        values[col] = row[col]

                                    if table_choice.lower() == 'mitarbeiter' and 'Password_hash' in valid_spalten:
                                        # Salt generieren und Passwort hashen
                                        salt = generate_salt()
                                        password = values.get('Password_hash', '')
                                        password_hash = hash_password(password, salt)

                                        # Werte aktualisieren
                                        values['Password_hash'] = password_hash
                                        values['salt'] = salt
                                        if 'salt' not in valid_spalten:
                                            valid_spalten.append('salt')

                                    placeholders = ", ".join([f":{col}" for col in valid_spalten])
                                    query = text(f"INSERT INTO {table_choice} ({', '.join(valid_spalten)}) VALUES ({placeholders})")
                                    result = conn.execute(query, values)

                                    # Wenn es sich um ein Ticket handelt, automatische Beziehungen erstellen
                                    if table_choice == "ticket":
                                        ticket_id = result.lastrowid
                                        ID_Mitarbeiter = values.get("ID_Mitarbeiter")

                                        # Standard-Kategorie (ID 1) verwenden
                                        create_ticket_relations(ticket_id, ID_Mitarbeiter, 1)

                                    success_count += 1
                                except Exception as e:
                                    error_count += 1
                                    st.error(f"Fehler beim Einfügen von Zeile {_+1}: {str(e)}")

                        if success_count > 0:
                            st.success(f"✅ {success_count} Datensätze erfolgreich eingefügt!")
                            # Leeren DataFrame für neue Eingaben erstellen
                            empty_df = pd.DataFrame(columns=spalten)
                            empty_row = {col: "" for col in spalten}
                            # Spezielle Behandlung für Datum/Zeit-Spalten
                            for col in spalten:
                                if 'date' in col.lower() or 'time' in col.lower() or 'erstellt' in col.lower():
                                    empty_row[col] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            empty_df = pd.concat([empty_df, pd.DataFrame([empty_row])], ignore_index=True)
                            st.session_state["multi_insert_df"] = empty_df
                            st.rerun()

                        if error_count > 0:
                            st.warning(f"⚠️ {error_count} Datensätze konnten nicht eingefügt werden.")

                    except Exception as e:
                        st.error(f"❌ Fehler beim Einfügen der Datensätze: {str(e)}")

    except Exception as e:
        st.error("❌ Fehler beim Einfügen:")
        st.exception(e)

def show_delete_tab(engine, inspector):
    """Rendert den 'Löschen'-Tab und steuert den Löschprozess."""
    st.subheader("Datensatz löschen")

    # Initialisierung des Zustands
    if "delete_state" not in st.session_state:
        st.session_state.delete_state = "initial"  # initial, confirm, step_by_step

    # Wenn im schrittweisen Modus, zeige nur die entsprechende UI
    if st.session_state.delete_state == "step_by_step":
        show_step_by_step_delete_ui(
            engine,
            st.session_state.delete_table,
            st.session_state.delete_id_column,
            st.session_state.delete_id_value
        )
        return

    # Auswahl der Tabelle und des Datensatzes
    table_names = inspector.get_table_names()
    table_choice = st.selectbox("Tabelle wählen (Löschen)", table_names, key="delete_table_select")

    if st.button("Daten zum Löschen laden", key="load_delete_data"):
        st.session_state.delete_df = pd.read_sql(f"SELECT * FROM {table_choice}", con=engine)
        st.session_state.delete_table = table_choice
        st.session_state.delete_state = "select_id"
        st.rerun()

    if st.session_state.get("delete_state") in ["select_id", "confirm"]:
        df = st.session_state.get("delete_df", pd.DataFrame())
        if df.empty:
            st.info("Bitte zuerst Daten laden.")
            return

        st.dataframe(df, use_container_width=True)
        id_columns = get_columns(st.session_state.delete_table)
        id_column = st.selectbox("Primärschlüsselspalte", id_columns, key="pk_select_delete")

        id_value = st.selectbox(f"Datensatz zum Löschen auswählen ({id_column})", df[id_column].tolist())

        if st.button("🗑️ Datensatz löschen", key="delete_button"):
            st.session_state.delete_id_column = id_column
            st.session_state.delete_id_value = id_value
            st.session_state.delete_state = "confirm"
            st.rerun()

    if st.session_state.delete_state == "confirm":
        st.warning(f"⚠️ Sind Sie sicher, dass Sie den Datensatz mit {st.session_state.delete_id_column} = {st.session_state.delete_id_value} löschen möchten?")
        col1, col2 = st.columns(2)
        if col1.button("✅ Ja, schrittweise löschen"):
            st.session_state.delete_state = "step_by_step"
            st.rerun()
        if col2.button("❌ Abbrechen"):
            st.session_state.delete_state = "initial"
            st.rerun()

# ==============================================================================
# 4. MAIN APPLICATION CONTROLLER
# ==============================================================================

def show_database_management():
    """
    Hauptfunktion, die die UI für die Datenbankverwaltung aufbaut und steuert.
    """
    from Main import engine, inspector  # Import nur hier

    if st.session_state.get("user_role") != "admin":
        st.error("🚫 Zugriff verweigert – nur für Administratoren.")
        st.stop()

    st.title("🛠️ Datenbankverwaltung (Refactored)")

    tab_map = {
        "📋 Anzeigen": show_view_tab,
        "✏️ Bearbeiten": show_edit_tab,
        "➕ Einfügen": show_insert_tab,
        "❌ Löschen": show_delete_tab,
    }

    tabs = st.tabs(list(tab_map.keys()))

    for i, tab_func in enumerate(tab_map.values()):
        with tabs[i]:
            # Übergebe engine und inspector an die jeweilige Tab-Funktion
            tab_func(engine, inspector)

