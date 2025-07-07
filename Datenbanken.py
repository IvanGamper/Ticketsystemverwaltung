import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime
from Authorisation import (generate_salt, hash_password, get_searchable_columns, search_table, get_column_types)
from Ticket import (create_ticket_relations, get_columns)

# Verbesserte Löschfunktion mit schrittweiser Bestätigung
def step_by_step_delete_function(table_choice_delete, id_spalte_delete, selected_id_to_delete):

    from Main import engine

    # Initialisierung der Session-State-Variablen für den schrittweisen Löschvorgang
    if "delete_step" not in st.session_state:
        st.session_state.delete_step = 0

    if "delete_steps_total" not in st.session_state:
        st.session_state.delete_steps_total = 1  # Standardwert, wird später aktualisiert

    if "delete_steps_info" not in st.session_state:
        st.session_state.delete_steps_info = []  # Liste mit Informationen zu jedem Schritt

    # Bestimme die Anzahl und Art der Löschschritte basierend auf der Tabelle
    if st.session_state.delete_step == 0:
        if table_choice_delete == "ticket":
            st.session_state.delete_steps_total = 5
            st.session_state.delete_steps_info = [
                {"name": "Ticket-Kommentare", "description": "Löscht alle Kommentare zu diesem Ticket"},
                {"name": "Ticket-Historie", "description": "Löscht alle Historieneinträge zu diesem Ticket"},
                {"name": "Ticket-Mitarbeiter-Zuordnungen", "description": "Löscht alle Mitarbeiterzuordnungen zu diesem Ticket"},
                {"name": "Ticket-Kategorie-Zuordnungen", "description": "Löscht alle Kategoriezuordnungen zu diesem Ticket"},
                {"name": "Ticket", "description": "Löscht das Ticket selbst"}
            ]
        elif table_choice_delete == "mitarbeiter":
            st.session_state.delete_steps_total = 5
            st.session_state.delete_steps_info = [
                {"name": "Ticket-Mitarbeiter-Zuordnungen", "description": "Löscht alle Zuordnungen dieses Mitarbeiters zu Tickets"},
                {"name": "Ticket-Historie-Einträge", "description": "Setzt Mitarbeiter-Referenzen in der Historie auf NULL"},
                {"name": "Tickets", "description": "Setzt Mitarbeiter-Referenzen in Tickets auf NULL"},
                {"name": "Kommentare", "description": "Setzt Mitarbeiter-Referenzen in Kommentaren auf NULL"},
                {"name": "Mitarbeiter", "description": "Löscht den Mitarbeiter selbst"}
            ]
        elif table_choice_delete == "kunde":
            st.session_state.delete_steps_total = 2
            st.session_state.delete_steps_info = [
                {"name": "Tickets", "description": "Setzt Kunden-Referenzen in Tickets auf NULL"},
                {"name": "Kunde", "description": "Löscht den Kunden selbst"}
            ]
        elif table_choice_delete == "kategorie":
            st.session_state.delete_steps_total = 2
            st.session_state.delete_steps_info = [
                {"name": "Ticket-Kategorie-Zuordnungen", "description": "Löscht alle Zuordnungen dieser Kategorie zu Tickets"},
                {"name": "Kategorie", "description": "Löscht die Kategorie selbst"}
            ]
        elif table_choice_delete == "status":
            st.session_state.delete_steps_total = 2
            st.session_state.delete_steps_info = [
                {"name": "Tickets", "description": "Setzt Status-Referenzen in Tickets auf NULL"},
                {"name": "Status", "description": "Löscht den Status selbst"}
            ]
        elif table_choice_delete == "rolle":
            st.session_state.delete_steps_total = 2
            st.session_state.delete_steps_info = [
                {"name": "Mitarbeiter", "description": "Setzt Rollen-Referenzen bei Mitarbeitern auf NULL"},
                {"name": "Rolle", "description": "Löscht die Rolle selbst"}
            ]
        else:
            # Für andere Tabellen nur ein Schritt
            st.session_state.delete_steps_total = 1
            st.session_state.delete_steps_info = [
                {"name": table_choice_delete, "description": f"Löscht den Datensatz aus {table_choice_delete}"}
            ]

    # Fortschrittsanzeige
    progress_percentage = (st.session_state.delete_step / st.session_state.delete_steps_total) * 100
    st.progress(progress_percentage / 100)
    st.write(f"Schritt {st.session_state.delete_step + 1} von {st.session_state.delete_steps_total}")

    # Wenn alle Schritte abgeschlossen sind, zurücksetzen und Erfolg melden
    if st.session_state.delete_step >= st.session_state.delete_steps_total:
        st.success(f"✅ Alle Löschschritte für {table_choice_delete} mit ID {selected_id_to_delete} wurden erfolgreich abgeschlossen!")

        # Daten neu laden
        df_delete = pd.read_sql(f"SELECT * FROM {table_choice_delete}", con=engine)
        st.write("Aktualisierte Tabellendaten:")
        st.dataframe(df_delete)

        # Session-State zurücksetzen
        st.session_state.delete_step = 0
        return True

    # Aktuellen Schritt anzeigen
    current_step_info = st.session_state.delete_steps_info[st.session_state.delete_step]
    st.subheader(f"Schritt {st.session_state.delete_step + 1}: {current_step_info['name']}")
    st.info(current_step_info['description'])

    # Bestätigungsdialog für den aktuellen Schritt
    st.warning(f"⚠️ Möchten Sie diesen Schritt ausführen? Diese Aktion kann nicht rückgängig gemacht werden!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Ja, ausführen", key=f"confirm_step_{st.session_state.delete_step}"):
            # Führe den aktuellen Löschschritt aus
            success = execute_delete_step(
                table_choice_delete,
                id_spalte_delete,
                selected_id_to_delete,
                st.session_state.delete_step
            )

            if success:
                st.success(f"✅ Schritt {st.session_state.delete_step + 1} erfolgreich ausgeführt!")
                # Zum nächsten Schritt
                st.session_state.delete_step += 1
                st.rerun()
            else:
                st.error("❌ Fehler beim Ausführen des Schritts!")
                # Schritt nicht erhöhen, damit der Benutzer es erneut versuchen kann

    with col2:
        if st.button("❌ Überspringen", key=f"skip_step_{st.session_state.delete_step}"):
            st.info(f"Schritt {st.session_state.delete_step + 1} übersprungen.")
            # Zum nächsten Schritt ohne Ausführung
            st.session_state.delete_step += 1
            st.rerun()

    # Option zum Abbrechen des gesamten Löschvorgangs
    if st.button("🛑 Gesamten Löschvorgang abbrechen", key="cancel_all_delete"):
        st.warning("Löschvorgang abgebrochen.")
        # Session-State zurücksetzen
        st.session_state.delete_step = 0
        return False

    return None  # Noch nicht abgeschlossen

# Funktion zum Ausführen eines einzelnen Löschschritts
def execute_delete_step(table_choice_delete, id_spalte_delete, selected_id_to_delete, step):
    """
    Führt einen einzelnen Löschschritt aus.

    Args:
        table_choice_delete: Name der Tabelle
        id_spalte_delete: Name der ID-Spalte
        selected_id_to_delete: Wert der ID des zu löschenden Datensatzes
        step: Aktueller Schritt im Löschvorgang

    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    from Main import engine

    try:
        with engine.begin() as conn:
            # Ticket-Löschschritte
            if table_choice_delete == "ticket":
                if step == 0:  # Ticket-Kommentare
                    query = text("""
                        DELETE FROM ticket_kommentar 
                        WHERE ID_Ticket = :ticket_id
                    """)
                    conn.execute(query, {"ticket_id": selected_id_to_delete})
                elif step == 1:  # Ticket-Historie
                    query = text("""
                        DELETE FROM ticket_historie 
                        WHERE ID_Ticket = :ticket_id
                    """)
                    conn.execute(query, {"ticket_id": selected_id_to_delete})
                elif step == 2:  # Ticket-Mitarbeiter-Zuordnungen
                    query = text("""
                        DELETE FROM ticket_mitarbeiter 
                        WHERE ID_Ticket = :ticket_id
                    """)
                    conn.execute(query, {"ticket_id": selected_id_to_delete})
                elif step == 3:  # Ticket-Kategorie-Zuordnungen
                    query = text("""
                        DELETE FROM ticket_kategorie 
                        WHERE ID_Ticket = :ticket_id
                    """)
                    conn.execute(query, {"ticket_id": selected_id_to_delete})
                elif step == 4:  # Ticket selbst
                    query = text("""
                        DELETE FROM ticket 
                        WHERE ID_Ticket = :ticket_id
                    """)
                    conn.execute(query, {"ticket_id": selected_id_to_delete})

            # Mitarbeiter-Löschschritte
            elif table_choice_delete == "mitarbeiter":
                if step == 0:  # Ticket-Mitarbeiter-Zuordnungen
                    query = text("""
                        DELETE FROM ticket_mitarbeiter 
                        WHERE ID_Mitarbeiter = :mitarbeiter_id
                    """)
                    conn.execute(query, {"mitarbeiter_id": selected_id_to_delete})
                elif step == 1:  # Ticket-Historie-Einträge
                    query = text("""
                        UPDATE ticket_historie 
                        SET Geändert_von = NULL
                        WHERE Geändert_von = :mitarbeiter_id
                    """)
                    conn.execute(query, {"mitarbeiter_id": selected_id_to_delete})
                elif step == 2:  # Tickets
                    query = text("""
                        UPDATE ticket 
                        SET ID_Mitarbeiter = NULL
                        WHERE ID_Mitarbeiter = :mitarbeiter_id
                    """)
                    conn.execute(query, {"mitarbeiter_id": selected_id_to_delete})
                elif step == 3:  # Kommentare
                    query = text("""
                        UPDATE ticket_kommentar 
                        SET ID_Mitarbeiter = NULL
                        WHERE ID_Mitarbeiter = :mitarbeiter_id
                    """)
                    conn.execute(query, {"mitarbeiter_id": selected_id_to_delete})
                elif step == 4:  # Mitarbeiter selbst
                    query = text("""
                        DELETE FROM mitarbeiter 
                        WHERE ID_Mitarbeiter = :mitarbeiter_id
                    """)
                    conn.execute(query, {"mitarbeiter_id": selected_id_to_delete})

            # Kunden-Löschschritte
            elif table_choice_delete == "kunde":
                if step == 0:  # Tickets
                    query = text("""
                        UPDATE ticket 
                        SET ID_Kunde = NULL
                        WHERE ID_Kunde = :kunde_id
                    """)
                    conn.execute(query, {"kunde_id": selected_id_to_delete})
                elif step == 1:  # Kunde selbst
                    query = text("""
                        DELETE FROM kunde 
                        WHERE ID_Kunde = :kunde_id
                    """)
                    conn.execute(query, {"kunde_id": selected_id_to_delete})

            # Kategorie-Löschschritte
            elif table_choice_delete == "kategorie":
                if step == 0:  # Ticket-Kategorie-Zuordnungen
                    query = text("""
                        DELETE FROM ticket_kategorie 
                        WHERE ID_Kategorie = :kategorie_id
                    """)
                    conn.execute(query, {"kategorie_id": selected_id_to_delete})
                elif step == 1:  # Kategorie selbst
                    query = text("""
                        DELETE FROM kategorie 
                        WHERE ID_Kategorie = :kategorie_id
                    """)
                    conn.execute(query, {"kategorie_id": selected_id_to_delete})

            # Status-Löschschritte
            elif table_choice_delete == "status":
                if step == 0:  # Tickets
                    query = text("""
                        UPDATE ticket 
                        SET ID_Status = NULL
                        WHERE ID_Status = :status_id
                    """)
                    conn.execute(query, {"status_id": selected_id_to_delete})
                elif step == 1:  # Status selbst
                    query = text("""
                        DELETE FROM status 
                        WHERE ID_Status = :status_id
                    """)
                    conn.execute(query, {"status_id": selected_id_to_delete})

            # Rollen-Löschschritte
            elif table_choice_delete == "rolle":
                if step == 0:  # Mitarbeiter
                    query = text("""
                        UPDATE mitarbeiter 
                        SET ID_Rolle = NULL
                        WHERE ID_Rolle = :rolle_id
                    """)
                    conn.execute(query, {"rolle_id": selected_id_to_delete})
                elif step == 1:  # Rolle selbst
                    query = text("""
                        DELETE FROM rolle 
                        WHERE ID_Rolle = :rolle_id
                    """)
                    conn.execute(query, {"rolle_id": selected_id_to_delete})

            # Für andere Tabellen einfacher Löschvorgang
            else:
                query = text(f"DELETE FROM {table_choice_delete} WHERE {id_spalte_delete} = :value")
                conn.execute(query, {"value": selected_id_to_delete})

        return True

    except Exception as e:
        st.error(f"❌ Fehler beim Ausführen des Schritts: {str(e)}")

        # Detaillierte Fehlermeldung für Fremdschlüsselprobleme
        error_str = str(e)
        if "foreign key constraint fails" in error_str.lower():
            st.error("""
            **Fremdschlüssel-Constraint-Fehler erkannt!**
            
            Der Datensatz kann nicht gelöscht werden, da er noch von anderen Tabellen referenziert wird.
            Bitte überprüfen Sie alle abhängigen Tabellen.
            """)

            # Versuche, die betroffene Tabelle zu identifizieren
            if "CONSTRAINT" in error_str and "FOREIGN KEY" in error_str:
                st.error(f"""
                Fehlerdetails: {error_str}
                """)

        return False

# Datenbankverwaltung anzeigen
def show_database_management():
    from Main import engine, inspector

    if st.session_state.get("user_role") != "admin":
        st.error("🚫 Zugriff verweigert – nur für Administratoren.")
        st.stop()

    st.title("🛠️ Datenbankverwaltung")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Anzeigen", "✏️ Bearbeiten", "➕ Einfügen", "❌ Löschen"])

    # -----------------------------
    # 📋 Tab 1: Anzeigen
    # -----------------------------
    with tab1:
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

    # -----------------------------
    # ✏️ Tab 2: Bearbeiten
    # -----------------------------
    with tab2:
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

    # -----------------------------
    # ➕ Tab 3: Einfügen
    # -----------------------------
    with tab3:
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

    # -----------------------------
    # ❌ Tab 4: Löschen
    # -----------------------------
    with tab4:
        st.subheader("Datensatz löschen")

        # Session-State für den Löschvorgang initialisieren
        if "delete_state" not in st.session_state:
            st.session_state.delete_state = "initial"  # Mögliche Zustände: initial, confirm, executing, step_by_step

        if "delete_table" not in st.session_state:
            st.session_state.delete_table = None

        if "delete_id_column" not in st.session_state:
            st.session_state.delete_id_column = None

        if "delete_id_value" not in st.session_state:
            st.session_state.delete_id_value = None

        if "delete_df" not in st.session_state:
            st.session_state.delete_df = pd.DataFrame()

        try:
            # Wenn wir uns im schrittweisen Löschmodus befinden, zeige nur den schrittweisen Löschprozess an
            if st.session_state.delete_state == "step_by_step":
                # Zeige Informationen zum aktuellen Datensatz
                st.info(f"Schrittweise Löschung für {st.session_state.delete_table} mit ID {st.session_state.delete_id_value}")

                # Führe die schrittweise Löschung durch
                result = step_by_step_delete_function(
                    st.session_state.delete_table,
                    st.session_state.delete_id_column,
                    st.session_state.delete_id_value
                )

                # Wenn die Löschung abgeschlossen oder abgebrochen wurde, zurück zum Ausgangszustand
                if result is not None:  # True = abgeschlossen, False = abgebrochen
                    st.session_state.delete_state = "initial"
                    # Daten neu laden
                    df_delete = pd.read_sql(f"SELECT * FROM {st.session_state.delete_table}", con=engine)
                    st.session_state.delete_df = df_delete
                    st.rerun()

                # Button zum Zurückkehren zur Tabellenauswahl
                if st.button("🔙 Zurück zur Tabellenauswahl"):
                    st.session_state.delete_state = "initial"
                    # Session-State für schrittweise Löschung zurücksetzen
                    if "delete_step" in st.session_state:
                        del st.session_state.delete_step
                    if "delete_steps_total" in st.session_state:
                        del st.session_state.delete_steps_total
                    if "delete_steps_info" in st.session_state:
                        del st.session_state.delete_steps_info
                    st.rerun()

            # Normaler Löschmodus (Auswahl und Bestätigung)
            else:
                tabellen = inspector.get_table_names()
                table_choice_delete = st.selectbox("Tabelle wählen (Löschen)", tabellen, key="delete_table_select")
                spalten_delete = get_columns(table_choice_delete)
                id_spalte_delete = st.selectbox("Primärschlüsselspalte", spalten_delete, key="primary_column_delete_select")

                # Daten laden Button
                if st.button("🔄 Daten zum Löschen laden", key="load_delete_data"):
                    df_delete = pd.read_sql(f"SELECT * FROM {table_choice_delete}", con=engine)
                    st.session_state.delete_df = df_delete
                    st.session_state.delete_table = table_choice_delete
                    st.session_state.delete_id_column = id_spalte_delete
                    st.session_state.delete_state = "initial"
                    st.rerun()

                # Wenn Daten geladen wurden, zeige sie an
                if not st.session_state.delete_df.empty:
                    st.dataframe(st.session_state.delete_df, use_container_width=True)

                    # Nur wenn wir nicht im Bestätigungsmodus sind, zeige die Auswahlfelder
                    if st.session_state.delete_state == "initial":
                        # ID zum Löschen auswählen
                        selected_id_to_delete = st.selectbox(
                            f"Datensatz zum Löschen auswählen ({st.session_state.delete_id_column})",
                            st.session_state.delete_df[st.session_state.delete_id_column].tolist(),
                            key="delete_id_select"
                        )

                        # Lösch-Button
                        if st.button("🗑️ Datensatz löschen", key="delete_record_button"):
                            # Werte speichern und in den Bestätigungsmodus wechseln
                            st.session_state.delete_id_value = selected_id_to_delete
                            st.session_state.delete_state = "confirm"
                            st.rerun()

                    # Bestätigungsdialog anzeigen
                    elif st.session_state.delete_state == "confirm":
                        st.warning(f"⚠️ Sind Sie sicher, dass Sie den Datensatz mit {st.session_state.delete_id_column} = {st.session_state.delete_id_value} löschen möchten?")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("✅ Ja, schrittweise löschen", key="confirm_step_by_step_delete"):
                                st.session_state.delete_state = "step_by_step"
                                # Session-State für schrittweise Löschung initialisieren
                                st.session_state.delete_step = 0
                                st.rerun()

                        with col2:
                            if st.button("❌ Abbrechen", key="cancel_delete_button"):
                                st.session_state.delete_state = "initial"
                                st.rerun()
                else:
                    st.info("Bitte laden Sie zuerst Daten zum Löschen.")

        except Exception as e:
            st.error("❌ Fehler beim Laden der Daten zum Löschen:")
            st.exception(e)
            # Zurück zum Ausgangszustand nach Fehler
            st.session_state.delete_state = "initial"

