import streamlit as st
from sqlalchemy import text
import time

def create_ticket_relations(ticket_id, ID_Mitarbeiter, kategorie_id=1):
    from Main import engine
    try:
        with engine.begin() as conn:
            # Eintrag in ticket_mitarbeiter
            if ID_Mitarbeiter:
                # Prüfen, ob der Eintrag bereits existiert
                check_query = text("SELECT COUNT(*) FROM ticket_mitarbeiter WHERE ID_Ticket = :ticket_id AND ID_Mitarbeiter = :ID_Mitarbeiter")
                result = conn.execute(check_query, {"ticket_id": ticket_id, "ID_Mitarbeiter": ID_Mitarbeiter}).scalar()

                if result == 0:  # Eintrag existiert noch nicht
                    insert_query = text("INSERT INTO ticket_mitarbeiter (ID_Ticket, ID_Mitarbeiter, Rolle_im_Ticket) VALUES (:ticket_id, :ID_Mitarbeiter, 'Hauptverantwortlicher')")
                    conn.execute(insert_query, {"ticket_id": ticket_id, "ID_Mitarbeiter": ID_Mitarbeiter})

            # Eintrag in ticket_kategorie
            if kategorie_id:
                # Prüfen, ob die Kategorie existiert
                check_kategorie = text("SELECT COUNT(*) FROM kategorie WHERE ID_Kategorie = :kategorie_id")
                kategorie_exists = conn.execute(check_kategorie, {"kategorie_id": kategorie_id}).scalar()

                if kategorie_exists > 0:
                    # Prüfen, ob der Eintrag bereits existiert
                    check_query = text("SELECT COUNT(*) FROM ticket_kategorie WHERE ID_Ticket = :ticket_id AND ID_Kategorie = :kategorie_id")
                    result = conn.execute(check_query, {"ticket_id": ticket_id, "kategorie_id": kategorie_id}).scalar()

                    if result == 0:  # Eintrag existiert noch nicht
                        insert_query = text("INSERT INTO ticket_kategorie (ID_Ticket, ID_Kategorie) VALUES (:ticket_id, :kategorie_id)")
                        conn.execute(insert_query, {"ticket_id": ticket_id, "kategorie_id": kategorie_id})

        return True
    except Exception as e:
        st.error(f"Fehler beim Erstellen der Ticket-Beziehungen: {str(e)}")
        return False

# Diese Funktion fügt einen Lösch-Button zum Ticket-Details-Bereich hinzu
def add_ticket_delete_button(ticket_id):

    from Main import engine

    """
    Fügt einen Lösch-Button für ein Ticket hinzu und implementiert die Löschlogik.

    Args:
        ticket_id: Die ID des zu löschenden Tickets
    """
    # Lösch-Button mit Warnfarbe
    col1, col2 = st.columns([3, 1])
    with col2:
        delete_button = st.button("🗑️ Ticket löschen", type="primary", use_container_width=True, key=f"delete_ticket_{ticket_id}")

    # Wenn der Lösch-Button geklickt wurde
    if delete_button:
        # Bestätigungsdialog anzeigen
        st.warning(f"Sind Sie sicher, dass Sie Ticket #{ticket_id} löschen möchten? Diese Aktion kann nicht rückgängig gemacht werden!")

        col1, col2 = st.columns([1, 1])
        with col1:
            confirm_delete = st.button("✅ Ja, Ticket löschen", type="primary", key=f"confirm_delete_{ticket_id}")
        with col2:
            cancel_delete = st.button("❌ Nein, abbrechen", key=f"cancel_delete_{ticket_id}")

        if confirm_delete:
            try:
                # Ticket löschen - die abhängigen Datensätze werden durch ON DELETE CASCADE automatisch gelöscht
                with engine.begin() as conn:
                    delete_query = text("""
                        DELETE FROM ticket 
                        WHERE ID_Ticket = :ticket_id
                    """)
                    result = conn.execute(delete_query, {"ticket_id": ticket_id})

                    if result.rowcount > 0:
                        st.success(f"✅ Ticket #{ticket_id} wurde erfolgreich gelöscht!")

                        # Session-State zurücksetzen
                        if "selected_ticket_id" in st.session_state and st.session_state.selected_ticket_id == ticket_id:
                            st.session_state.selected_ticket_id = None

                        # Kurze Verzögerung für bessere Benutzererfahrung
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Ticket #{ticket_id} konnte nicht gelöscht werden.")

            except Exception as e:
                st.error(f"❌ Fehler beim Löschen des Tickets: {str(e)}")

                # Detaillierte Fehlermeldung für Fremdschlüssel-Probleme
                error_str = str(e)
                if "foreign key constraint fails" in error_str.lower():
                    st.error("""
                    **Fremdschlüssel-Constraint-Fehler erkannt!**
                    
                    Das Ticket kann nicht gelöscht werden, da es noch von anderen Tabellen referenziert wird.
                    Bitte stellen Sie sicher, dass die ON DELETE CASCADE-Optionen in der Datenbank korrekt konfiguriert sind.
                    """)

        elif cancel_delete:
            st.info("Löschvorgang abgebrochen.")

# Hilfsfunktion: Spaltennamen einer Tabelle
def get_columns(table):

    from Main import engine, inspector

    try:
        return [col["name"] for col in inspector.get_columns(table)]
    except:
        return []

#Hilfsfunktion Historie
def log_ticket_change(ticket_id, feldname, alter_wert, neuer_wert, mitarbeiter_id):

    from Main import engine

    # Typkonvertierung für den Vergleich
    alter_wert_str = str(alter_wert) if alter_wert is not None else ""
    neuer_wert_str = str(neuer_wert) if neuer_wert is not None else ""

    # Nur speichern, wenn sich die Werte tatsächlich unterscheiden
    if alter_wert_str.strip() == neuer_wert_str.strip():
        return  # Nur Änderungen speichern

    # Kürzere Transaktion mit Wiederholungslogik
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            insert_query = text("""
                INSERT INTO ticket_historie (ID_Ticket, Feldname, Alter_Wert, Neuer_Wert, Geändert_von, Geändert_am)
                VALUES (:ticket_id, :feldname, :alter_wert, :neuer_wert, :geändert_von, NOW())
            """)

            with engine.begin() as conn:
                conn.execute(insert_query, {
                    "ticket_id": ticket_id,
                    "feldname": feldname,
                    "alter_wert": alter_wert_str,
                    "neuer_wert": neuer_wert_str,
                    "geändert_von": mitarbeiter_id
                })

            # Wenn erfolgreich, Schleife beenden
            return True

        except Exception as e:
            # Nur bei Lock-Timeout-Fehlern wiederholen
            if "Lock wait timeout exceeded" in str(e) and retry_count < max_retries - 1:
                retry_count += 1
                time.sleep(0.5)  # Kurze Pause vor dem nächsten Versuch
            else:
                # Bei anderen Fehlern oder zu vielen Versuchen, Fehler protokollieren
                print(f"FEHLER: Historien-Eintrag konnte nicht gespeichert werden: {str(e)}")
                # Fehler weitergeben
                raise
