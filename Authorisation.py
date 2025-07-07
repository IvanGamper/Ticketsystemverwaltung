import hashlib
import secrets
import time
from sqlalchemy import text
from datetime import datetime, timedelta
import string
import random
import pandas as pd
import streamlit as st

# Hilfsfunktion: Spaltentypen einer Tabelle
def get_column_types(table):
    from Main import inspector
    try:
        return {col["name"]: str(col["type"]) for col in inspector.get_columns(table)}
    except:
        return {}

# Hilfsfunktion: Durchsuchbare Spalten einer Tabelle ermitteln
def get_searchable_columns(table):
    try:
        column_types = get_column_types(table)
        searchable_columns = []

        for col, type_str in column_types.items():
            # Spaltentypen, die für die Suche geeignet sind
            if any(text_type in type_str.lower() for text_type in ['char', 'text', 'varchar', 'enum']):
                searchable_columns.append(col)
            # Numerische Typen sind auch durchsuchbar
            elif any(num_type in type_str.lower() for num_type in ['int', 'decimal', 'float', 'double']):
                searchable_columns.append(col)
            # Datum/Zeit-Typen sind auch durchsuchbar
            elif any(date_type in type_str.lower() for date_type in ['date', 'time', 'datetime', 'timestamp']):
                searchable_columns.append(col)

        return searchable_columns
    except Exception as e:
        st.error(f"Fehler beim Ermitteln der durchsuchbaren Spalten: {str(e)}")
        return []

# Hilfsfunktion: Tabelle durchsuchen
def search_table(table_name, search_term, search_columns=None, exact_match=False, case_sensitive=False):
    from Main import engine
    try:
        if not search_term:
            return pd.DataFrame()

        # Durchsuchbare Spalten ermitteln
        if search_columns is None:
            search_columns = get_searchable_columns(table_name)

        if not search_columns:
            st.warning(f"Keine durchsuchbaren Spalten in der Tabelle '{table_name}' gefunden.")
            return pd.DataFrame()

        # SQL-Abfrage erstellen
        conditions = []
        params = {}

        for i, col in enumerate(search_columns):
            param_name = f"search_term_{i}"

            if exact_match:
                # Exakte Übereinstimmung
                if case_sensitive:
                    conditions.append(f"{col} = :{param_name}")
                else:
                    conditions.append(f"LOWER({col}) = :{param_name}")
                    search_term = search_term.lower()

                params[param_name] = search_term
            else:
                # Teilweise Übereinstimmung
                if case_sensitive:
                    conditions.append(f"{col} LIKE :{param_name}")
                else:
                    conditions.append(f"LOWER({col}) LIKE :{param_name}")
                    search_term = search_term.lower()

                params[param_name] = f"%{search_term}%"

        # WHERE-Klausel erstellen
        where_clause = " OR ".join(conditions)

        # SQL-Abfrage ausführen
        query = text(f"SELECT * FROM {table_name} WHERE {where_clause}")

        with engine.connect() as conn:
            result = conn.execute(query, params)
            columns = result.keys()
            data = result.fetchall()

        # DataFrame erstellen
        df = pd.DataFrame(data, columns=columns)
        return df

    except Exception as e:
        st.error(f"Fehler bei der Suche: {str(e)}")
        return pd.DataFrame()

# Passwort-Hashing-Funktionen
def generate_salt():
    """Generiert einen zufälligen Salt für das Passwort-Hashing."""
    return secrets.token_hex(16)

def hash_password(password, salt):
    """Hasht ein Passwort mit dem angegebenen Salt."""
    salted_password = password + salt
    password_hash = hashlib.sha256(salted_password.encode()).hexdigest()
    return password_hash

def verify_password(password, stored_hash, salt):
    """Überprüft, ob das eingegebene Passwort korrekt ist."""
    calculated_hash = hash_password(password, salt)
    return calculated_hash == stored_hash

# Funktion zur Generierung eines temporären Passworts
def generate_temp_password(length=12):
    """Generiert ein zufälliges temporäres Passwort."""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    # Sicherstellen, dass mindestens ein Zeichen aus jeder Kategorie enthalten ist
    password = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*")
    ]
    # Restliche Zeichen zufällig auswählen
    password.extend(random.choice(characters) for _ in range(length - 4))
    # Mischen der Zeichen
    random.shuffle(password)
    return ''.join(password)

# Authentifizierungsfunktion
def authenticate_user(username_or_email, password):

    from Main import engine
    try:
        # Kleine Verzögerung als Schutz vor Brute-Force-Angriffen
        time.sleep(0.5)

        # Benutzer in der Datenbank suchen
        query = text("""
        SELECT ID_Mitarbeiter, Name, Password_hash, salt, password_change_required, Rolle
        FROM mitarbeiter 
        WHERE Name = :username OR Email = :email
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"username": username_or_email, "email": username_or_email}).fetchone()

        if not result:
            return False, None, False

        user_id, name, stored_hash, salt, password_change_required, rolle = result

        # Falls kein Salt vorhanden ist (Altdaten), Passwort direkt vergleichen
        # und bei Erfolg ein Salt generieren und das Passwort hashen
        if not salt:
            if password == stored_hash:
                # Passwort ist korrekt, aber ungehasht - jetzt hashen und speichern
                new_salt = generate_salt()
                new_hash = hash_password(password, new_salt)

                # Datensatz aktualisieren
                update_query = text("""
                UPDATE mitarbeiter 
                SET Password_hash = :password_hash, salt = :salt 
                WHERE ID_Mitarbeiter = :user_id
                """)

                with engine.begin() as conn:
                    conn.execute(update_query, {
                        "password_hash": new_hash,
                        "salt": new_salt,
                        "user_id": user_id
                    })

                return True, user_id, password_change_required
            else:
                return False, None, False

        # Ansonsten mit Salt hashen und vergleichen
        if verify_password(password, stored_hash, salt):
            return True, user_id, password_change_required, rolle
        else:
            return False, None, False

    except Exception as e:
        st.error(f"Fehler bei der Authentifizierung: {str(e)}")
        return False, None, False

# Funktion zur Passwort-Wiederherstellung
def reset_password(email):
    from Main import engine
    try:
        # Benutzer in der Datenbank suchen
        query = text("""
        SELECT ID_Mitarbeiter, Name, Email 
        FROM mitarbeiter 
        WHERE Email = :email
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"email": email}).fetchone()

        if not result:
            return False, None, None

        user_id, name, user_email = result

        # Temporäres Passwort generieren
        temp_password = generate_temp_password()

        # Salt generieren und temporäres Passwort hashen
        salt = generate_salt()
        password_hash = hash_password(temp_password, salt)

        # Ablaufdatum für das temporäre Passwort (24 Stunden)
        expiry = datetime.now() + timedelta(hours=24)

        # Datensatz aktualisieren
        update_query = text("""
        UPDATE mitarbeiter 
        SET Password_hash = :password_hash, 
            salt = :salt, 
            reset_token = :reset_token, 
            reset_token_expiry = :expiry, 
            password_change_required = TRUE 
        WHERE ID_Mitarbeiter = :user_id
        """)

        with engine.begin() as conn:
            conn.execute(update_query, {
                "password_hash": password_hash,
                "salt": salt,
                "reset_token": secrets.token_hex(16),  # Zusätzlicher Token für Sicherheit
                "expiry": expiry,
                "user_id": user_id
            })

        return True, name, temp_password

    except Exception as e:
        st.error(f"Fehler bei der Passwort-Wiederherstellung: {str(e)}")
        return False, None, None

# Funktion zum Ändern des Passworts
def change_password(user_id, new_password):
    from Main import engine
    """Ändert das Passwort eines Benutzers."""
    try:
        # Salt generieren und neues Passwort hashen
        salt = generate_salt()
        password_hash = hash_password(new_password, salt)

        # Datensatz aktualisieren
        update_query = text("""
        UPDATE mitarbeiter 
        SET Password_hash = :password_hash, 
            salt = :salt, 
            reset_token = NULL, 
            reset_token_expiry = NULL, 
            password_change_required = FALSE 
        WHERE ID_Mitarbeiter = :user_id
        """)

        with engine.begin() as conn:
            conn.execute(update_query, {
                "password_hash": password_hash,
                "salt": salt,
                "user_id": user_id
            })

        return True

    except Exception as e:
        st.error(f"Fehler beim Ändern des Passworts: {str(e)}")
        return False

# Passwort-Wiederherstellungsseite anzeigen
def show_password_reset_page():
    from Main import engine
    st.title("🔑 Passwort zurücksetzen")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.image("https://img.icons8.com/color/96/000000/password-reset.png", width=100)

    with col2:
        st.markdown("### Passwort zurücksetzen")
        st.markdown("Geben Sie Ihre E-Mail-Adresse ein, um Ihr Passwort zurückzusetzen.")

    with st.form("password_reset_form"):
        email = st.text_input("E-Mail-Adresse")
        submit = st.form_submit_button("Passwort zurücksetzen")

    if submit:
        if not email:
            st.error("Bitte geben Sie Ihre E-Mail-Adresse ein.")
        else:
            success, name, temp_password = reset_password(email)
            if success:
                st.success("Passwort erfolgreich zurückgesetzt!")
                st.info(f"""
                Hallo {name},
                
                Ihr temporäres Passwort lautet: **{temp_password}**
                
                Bitte melden Sie sich mit diesem Passwort an und ändern Sie es sofort.
                Das temporäre Passwort ist 24 Stunden gültig.
                """)

                # Link zur Login-Seite
                if st.button("Zurück zur Anmeldung"):
                    st.session_state.show_password_reset = False
                    st.rerun()
            else:
                st.error("E-Mail-Adresse nicht gefunden.")

    # Link zur Login-Seite
    st.markdown("---")
    if st.button("Abbrechen"):
        st.session_state.show_password_reset = False
        st.rerun()

# Passwortänderungsseite anzeigen
def show_password_change_page():
    from Main import engine
    st.title("🔐 Passwort ändern")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.image("https://img.icons8.com/color/96/000000/password.png", width=100)

    with col2:
        st.markdown("### Passwort ändern")
        st.markdown("Bitte ändern Sie Ihr temporäres Passwort.")

    with st.form("password_change_form"):
        new_password = st.text_input("Neues Passwort", type="password")
        confirm_password = st.text_input("Passwort bestätigen", type="password")
        submit = st.form_submit_button("Passwort ändern")

    if submit:
        if not new_password or not confirm_password:
            st.error("Bitte füllen Sie alle Felder aus.")
        elif new_password != confirm_password:
            st.error("Die Passwörter stimmen nicht überein.")
        elif len(new_password) < 8:
            st.error("Das Passwort muss mindestens 8 Zeichen lang sein.")
        else:
            success = change_password(st.session_state.user_id, new_password)
            if success:
                st.success("Passwort erfolgreich geändert!")
                st.session_state.password_changed = True
                time.sleep(1)  # Kurze Verzögerung, damit die Erfolgsmeldung sichtbar ist
                st.rerun()
            else:
                st.error("Fehler beim Ändern des Passworts.")

# Login-Seite anzeigen
def show_login_page():
    from Main import engine
    st.title("🔐 Login")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.image("https://img.icons8.com/color/96/000000/password.png", width=100)

    with col2:
        st.markdown("### Bitte melden Sie sich an")
        st.markdown("Geben Sie Ihre Zugangsdaten ein, um das Ticketsystem zu nutzen.")

    with st.form("login_form"):
        username = st.text_input("Benutzername oder E-Mail")
        password = st.text_input("Passwort", type="password")
        submit = st.form_submit_button("Anmelden")

    if submit:
        if not username or not password:
            st.error("Bitte geben Sie Benutzername und Passwort ein.")
        else:
            success, user_id, password_change_required, rolle = authenticate_user(username, password)
            if success:
                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.password_change_required = password_change_required
                st.session_state.user_role = rolle

                # Benutzername für die Anzeige speichern
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT Name FROM mitarbeiter WHERE ID_Mitarbeiter = :user_id"),
                                          {"user_id": user_id}).fetchone()
                    if result:
                        st.session_state.username = result[0]

                st.success("Login erfolgreich!")
                time.sleep(1)  # Kurze Verzögerung, damit die Erfolgsmeldung sichtbar ist
                st.rerun()
            else:
                st.error("Ungültiger Benutzername oder Passwort.")

    # Link zur Passwort-Wiederherstellung
    st.markdown("---")
    if st.button("Passwort vergessen?"):
        st.session_state.show_password_reset = True
        st.rerun()