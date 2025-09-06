import imaplib
import email
import Mail_Manager
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNT = os.getenv("RECEIVER_ID")
PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

COLLEGE_DOMAIN = "@iiitb.ac.in"


def fetch_and_process_emails():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, PASSWORD)
    mail.select("inbox")

    status, messages = mail.search(None, "UNSEEN")
    if status != "OK" or not messages[0]:
        return

    for num in messages[0].split():
        status, data = mail.fetch(num, "(RFC822)")
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        sender = msg["from"]
        subject = msg["subject"]

        if sender != os.getenv("SENDER_ID"):
            if COLLEGE_DOMAIN not in sender and COLLEGE_DOMAIN not in str(msg):
                continue

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get(
                    "Content-Disposition"
                ):
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")

        result = Mail_Manager.analyse_email_process_task(body)

        print(f"From: {sender}")
        print(f"Subject: {subject}")
        print(f"Response: {result['final_response']}\n")

        mail.store(num, "+FLAGS", "\\Seen")

    mail.close()
    mail.logout()


if __name__ == "__main__":
    fetch_and_process_emails()
    print("Done")
