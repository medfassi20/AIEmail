from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import json
import os
import smtplib
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import imaplib
import email
from email.header import decode_header
import openai
from langdetect import detect  # Importer la bibliothèque de détection de langue

# Initialisation du client Forefront
# openai.api_key = "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"  # Remplacez par votre clé API Forefront

# Fonction pour détecter la langue du texte
def detect_language(text):
    try:
        return detect(text)
    except Exception as e:
        return "fr"  # Par défaut, on suppose que c'est du français si la détection échoue

# Fonction pour générer une réponse basée sur l'historique et la langue détectée
def generate_response(email_content, email_history):
    try:
        # Détecter la langue de l'email reçu
        language = detect_language(email_content)
        
        # Choisir le modèle linguistique adapté selon la langue détectée
        if language == "fr":
            system_message_content = (
                "Vous êtes un assistant qui aide à répondre aux emails. "
                "Générez une réponse en gardant le style, le format, et le ton déduit de l'historique des emails envoyés. "
                "Le contenu de la réponse doit être cohérent avec le contexte, sans question, et intégrer le nom de l'envoyeur du mail reçu dans la formule de politesse. "
                "Le message doit être signé par Mohammed Fassi Fehri."
            )
        elif language == "en":
            system_message_content = (
                "You are an assistant that helps in replying to emails. "
                "Generate a response while maintaining the style, format, and tone deduced from the history of sent emails. "
                "The content of the response should be coherent with the context, without questions, and include the sender's name from the received email in the closing. "
                "The message should be signed by Mohammed Fassi Fehri."
            )
        else:
            # Ajouter d'autres langues si nécessaire
            system_message_content = (
                "You are an assistant that helps in replying to emails. "
                "Generate a response while maintaining the style, format, and tone deduced from the history of sent emails. "
                "The content of the response should be coherent with the context, without questions, and include the sender's name from the received email in the closing. "
                "The message should be signed by Mohammed Fassi Fehri."
            )

        # Créer le message initial du système
        initial_message = {
            "role": "system",
            "content": system_message_content
        }

        # Message utilisateur contenant le contenu de l'email reçu
        user_message = {
            "role": "user",
            "content": email_content
        }

        # Inclure l'historique des emails envoyés
        history_message = {
            "role": "system",
            "content": email_history
        }

        # Utilisation d'OpenAI pour générer une réponse
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[initial_message, history_message, user_message],
            max_tokens=150
        )

        # Retourner la réponse générée
        return response['choices'][0]['message']['content']

    except Exception as e:
        return f"Une erreur est survenue: {e}"

# Fonction pour nettoyer le texte de l'email
def clean_text(text):
    clean = re.sub(r'[\/<>*\\]', '', text)
    return clean

# Fonction pour séparer l'email reçu et l'email envoyé
def split_email(email_body):
    def detect_end_of_email(lines):
        for i in range(len(lines)-1, -1, -1):
            if lines[i].strip() and not lines[i].strip().startswith('--'):
                return i + 1
        return len(lines)

    lines = email_body.split('\n')
    received_lines = []
    sent_lines = []
    in_received = True

    for line in lines:
        if re.match(r'^\s*(Le|On|From|De|Envoyé|Sent|Subject|Reply-To|Re:|Fwd:|>|\d{1,2}/\d{1,2}/\d{4}|[A-Za-z]+, \d{1,2} [A-Za-z]+ \d{4})', line):
            in_received = False
        if in_received:
            received_lines.append(line)
        else:
            sent_lines.append(line)

    received_email = '\n'.join(received_lines).strip()
    sent_email = '\n'.join(sent_lines).strip()

    end_of_received_email = detect_end_of_email(received_lines)
    received_email = '\n'.join(received_lines[:end_of_received_email]).strip()

    if received_email and sent_email and received_email.split()[-1] == sent_email.split()[0]:
        received_email = '\n'.join(received_email.split()[:-1])
        sent_email = '\n'.join(sent_email.split()[1:])

    return received_email, sent_email

# Fonction pour extraire les composants de l'email
def extract_email_components(raw_email):
    msg = email.message_from_bytes(raw_email)
    msg_from = decode_header(msg["From"])[0][0]
    msg_subject = decode_header(msg["Subject"])[0][0]
    if isinstance(msg_from, bytes):
        msg_from = msg_from.decode(errors='ignore')
    if isinstance(msg_subject, bytes):
        msg_subject = msg_subject.decode(errors='ignore')

    msg_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if "attachment" not in content_disposition:
                if content_type == "text/plain":
                    try:
                        msg_body = part.get_payload(decode=True).decode(errors='ignore')
                    except Exception as e:
                        print(f"Erreur de déchiffrement: {str(e)}")
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            try:
                msg_body = msg.get_payload(decode=True).decode(errors='ignore')
            except Exception as e:
                print(f"Erreur de déchiffrement: {str(e)}")

    return msg_from, msg_subject, msg_body

# Fonction pour charger l'historique des emails envoyés
def load_email_history(filename="sent_emails.json"):
    if not os.path.exists(filename):
        return "Pas d'historique d'emails disponible."
    try:
        with open(filename, "r", encoding="utf-8") as file:
            email_history = json.load(file)
            return " ".join(email["body"] for email in email_history)
    except json.JSONDecodeError as e:
        return f"Erreur de déchiffrement JSON: {str(e)}"

# Classe pour gérer les réponses d'emails
class EmailResponder:
    def __init__(self):
        self.email_history = load_email_history()
        self.email_pairs = self.load_emails_from_file()

    def load_emails_from_file(self, filename="emails.json"):
        if not os.path.exists(filename):
            return []
        try:
            with open(filename, "r", encoding="utf-8") as file:
                json_emails = json.load(file)
                emails = [{"from": email["from"], "subject": email["subject"], "body": email["body"]} for email in json_emails]
            return emails
        except json.JSONDecodeError as e:
            raise Exception(f"Erreur de déchiffrement JSON: {str(e)}")

    def generate_response(self, email_content):
        return generate_response(email_content, self.email_history)

# Classe principale de l'application
class ChatBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chatbot Application")
        self.previous_messages = []
        self.discussions = []
        self.archived_discussions = []
        self.current_discussion = None

        # Boucle d'authentification jusqu'à ce qu'elle soit réussie ou que l'utilisateur annule
        while True:
            login_dialog = LoginDialog(root)
            self.email = login_dialog.email
            self.password = login_dialog.password

            if not self.email or not self.password:
                messagebox.showerror("Erreur", "Email et mot de passe requis.")
                return

            self.smtp_server = "smtp.gmail.com"  # Remplacez par votre serveur SMTP
            self.smtp_port = 587  # Remplacez par le port SMTP approprié
            self.smtp_user = self.email  # Utiliser l'email entré par l'utilisateur
            self.smtp_password = self.password  # Utiliser le mot de passe entré par l'utilisateur
            self.to_address = None
            self.subject = None
            self.body = None

            # Tenter de récupérer les emails
            self.emails = self.get_emails(self.email, self.password)
            
            # Si l'authentification réussit, sortir de la boucle
            if self.emails:
                break
            
            # Si l'authentification échoue, demander à l'utilisateur de réessayer
            retry = messagebox.askretrycancel("Erreur d'authentification", "Email ou mot de passe incorrect. Voulez-vous réessayer ?")
            if not retry:
                return

        # Si on arrive ici, l'authentification a réussi et on peut continuer l'initialisation
        self.save_emails_to_file(self.emails)  # Sauvegarder les emails une fois chargés

        self.setup_ui()
        self.display_emails_in_ui()

        if not self.emails:
            messagebox.showerror("Erreur", "Impossible de récupérer les emails.")
            return

        self.email_responder = EmailResponder()

    def setup_ui(self):
        self.frame_left = tk.Frame(self.root, width=200, bg='lightgrey')
        self.frame_left.pack(side='left', fill='y')

        self.frame_right = tk.Frame(self.root)
        self.frame_right.pack(side='right', expand=True, fill='both')

        self.email_listbox = tk.Listbox(self.frame_left)
        self.email_listbox.pack(fill='both', expand=True)
        self.email_listbox.bind('<<ListboxSelect>>', self.on_select_email)

        self.received_email_label = tk.Label(self.frame_right, text="Email reçu:")
        self.received_email_label.pack(padx=10, pady=5, anchor='w')

        self.email_content_box = scrolledtext.ScrolledText(self.frame_right, width=60, height=10, state='disabled', cursor='sb_v_double_arrow')
        self.email_content_box.pack(fill='both', expand=True)

        self.sent_email_label = tk.Label(self.frame_right, text="Email envoyé:")
        self.sent_email_label.pack(padx=10, pady=5, anchor='w')

        self.sent_email_box = scrolledtext.ScrolledText(self.frame_right, width=60, height=10, state='disabled', cursor='sb_v_double_arrow')
        self.sent_email_box.pack(fill='both', expand=True)

        self.message_label = tk.Label(self.frame_right, text="Réponse générée:")
        self.message_label.pack(padx=10, pady=5, anchor='w')

        self.message_entry = scrolledtext.ScrolledText(self.frame_right, width=80, height=5, cursor='sb_v_double_arrow')
        self.message_entry.pack(fill='both', expand=True)

        self.generate_button = tk.Button(self.frame_right, text="Générer Réponse", command=self.generate_response)
        self.generate_button.pack(padx=10, pady=5)

        self.send_button = tk.Button(self.frame_right, text="Envoyer", command=self.send_message)
        self.send_button.pack(padx=10, pady=5)

    def display_emails_in_ui(self):
        self.email_listbox.delete(0, tk.END)
        for email in self.emails:
            self.email_listbox.insert(tk.END, email[1])

    def on_select_email(self, event):
        selected_index = self.email_listbox.curselection()
        if selected_index:
            index = selected_index[0]
            selected_email = self.emails[index]
            self.email_content_box.config(state='normal')
            self.email_content_box.delete(1.0, tk.END)
            cleaned_message = clean_text(selected_email[2])
            received_email, sent_email = split_email(cleaned_message)
            self.email_content_box.insert(tk.END, f"{received_email}")
            self.email_content_box.config(state='disabled')

            self.sent_email_box.config(state='normal')
            self.sent_email_box.delete(1.0, tk.END)
            self.sent_email_box.insert(tk.END, sent_email)
            self.sent_email_box.config(state='disabled')

            self.message_entry.config(state='normal')
            self.message_entry.delete(1.0, tk.END)
            self.message_entry.config(state='disabled')

    def generate_response(self):
        selected_index = self.email_listbox.curselection()
        if selected_index:
            index = selected_index[0]
            selected_email = self.emails[index]
            
            self.to_address = selected_email[0]  # Adresse email du destinataire
            self.subject = "Réponse à: " + selected_email[1]  # Sujet de l'email
            
            # Générer la réponse en utilisant l'historique
            final_response = self.email_responder.generate_response(selected_email[2]).strip()  # Applique strip ici

            # Afficher la réponse générée dans la zone de texte
            self.message_entry.config(state='normal')
            self.message_entry.delete(1.0, tk.END)
            self.message_entry.insert(tk.END, final_response)
            self.message_entry.config(state='normal')  # Permettre de générer et afficher à nouveau

    def send_message(self):
        try:
            if self.to_address and self.subject:
                # Récupérer le texte modifié par l'utilisateur avant l'envoi
                self.body = self.message_entry.get("1.0", tk.END).strip()  # Utilise strip pour nettoyer le texte final

                if not self.body:
                    messagebox.showerror("Erreur", "Le corps du message ne peut pas être vide.")
                    return
                
                # Essayer d'envoyer l'email
                result = self._send_email(self.smtp_server, self.smtp_port, self.smtp_user, self.smtp_password, self.to_address, self.subject, self.body)
                messagebox.showinfo("Résultat", result)
            else:
                messagebox.showerror("Erreur", "Les détails de l'email ne sont pas complets.")
        except Exception as e:
            # Gérer les erreurs potentielles et informer l'utilisateur
            messagebox.showerror("Erreur lors de l'envoi de l'email", f"Une erreur est survenue : {str(e)}")

    def _send_email(self, smtp_server, smtp_port, smtp_user, smtp_password, to_address, subject, body):
        try:
            if isinstance(body, str):
                body = body.encode('utf-8').decode('utf-8')
            #Création du message    
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to_address
            msg['Subject'] = subject

            # Attacher le corps du message en texte brut
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Connexion au serveur SMTP
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()  # Sécuriser la connexion
            server.login(smtp_user, smtp_password)  # Authentification

            # Envoi de l'email
            server.sendmail(smtp_user, to_address, msg.as_string())

            # Fermeture de la connexion
            server.quit()

            return "Email envoyé avec succès !"
        except Exception as e:
            return f"Erreur lors de l'envoi de l'email : {str(e)}"

    def get_emails(self, email_user, email_pass, imap_server='imap.gmail.com', max_emails=300):
        try:
            # Essayer de se connecter au serveur IMAP
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_user, email_pass)
            mail.select("inbox")

            # Si la connexion réussit, récupérer les emails
            status, messages = mail.search(None, "ALL")
            if status != "OK":
                raise Exception("Impossible de récupérer les emails")

            email_list = messages[0].split()
            email_list.reverse()
            email_messages = []

            for msg_num in email_list[:max_emails]:
                status, msg_data = mail.fetch(msg_num, "(RFC822)")
                if status != "OK":
                    raise Exception(f"Impossible de récupérer l'email numéro {msg_num}")

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg_from, msg_subject, msg_body = extract_email_components(response_part[1])
                        email_messages.append((msg_from, msg_subject, msg_body))

            mail.close()
            mail.logout()
            return email_messages

        except imaplib.IMAP4.error:
            # Gérer les erreurs d'authentification
            messagebox.showerror("Erreur d'authentification", "Email ou mot de passe incorrect. Veuillez vérifier vos informations et réessayer.")
            return []  # Retourne une liste vide pour arrêter le processus de récupération des emails
        except Exception as e:
            messagebox.showerror("Erreur", f"Une erreur s'est produite : {str(e)}")
            return []

    def save_emails_to_file(self, emails, filename="emails.json"):
        with open(filename, "w", encoding="utf-8") as file:
            json_emails = [{"from": email[0], "subject": email[1], "body": email[2]} for email in emails]
            json.dump(json_emails, file, ensure_ascii=False, indent=4)

    def load_emails_from_file(self, filename="emails.json"):
        if not os.path.exists(filename):
            return []
        try:
            with open(filename, "r", encoding="utf-8") as file:
                json_emails = json.load(file)
                emails = [(email["from"], email["subject"], email["body"]) for email in json_emails]
            return emails
        except json.JSONDecodeError as e:
            messagebox.showerror("Erreur", f"Erreur de déchiffrement JSON: {str(e)}")
            return []

class LoginDialog(simpledialog.Dialog):
    def body(self, master):
        self.email = None
        self.password = None

        tk.Label(master, text="Email:").grid(row=0)
        tk.Label(master, text="Mot de passe:").grid(row=1)

        self.email_entry = tk.Entry(master)
        self.password_entry = tk.Entry(master, show="*")

        self.email_entry.grid(row=0, column=1)
        self.password_entry.grid(row=1, column=1)

        return self.email_entry

    def apply(self):
        self.email = self.email_entry.get()
        self.password = self.password_entry.get()

    def buttonbox(self):
        """Removes the cancel button."""
        box = tk.Frame(self)
        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        box.pack()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatBotApp(root)
    root.mainloop()