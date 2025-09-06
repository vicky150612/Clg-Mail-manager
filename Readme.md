# Email Reader & Analyzer

A Python script that connects to Gmail via IMAP, fetches unread emails, filters them by sender or domain, and analyzes the email body using a custom `Mail_Manager`.

---

## Features

- Connects securely to Gmail via IMAP.
- Fetches unread emails from the inbox.
- Filters emails by:
  - Specific sender (`SENDER_ID`), or
  - College domain (`@iiitb.ac.in`).
- Extracts plain-text body from emails.
- Sends the body to `Mail_Manager.manage_and_analyse_email` for analysis.
- Here mails are analysed and a google task is created if required.
- Marks emails as **read** after processing.
- Prints only the required details:
  - **From**
  - **Subject**
  - **Analysis result**

## Things to ensure

- College mail ID's have restrictions so analysis is not directly possible on it.
- You will have to enable autoforwading in outlook web. Choose a personal gmail id and forward all mails.
- Enable 2fa and create an app password.
- Make sure IMAP is enabled in your Gmail account settings.
- You may need to adjust `COLLEGE_DOMAIN` to match your institution’s domain.

---

## Requirements

- Python 3.8+
- Gmail account with **App Passwords** enabled

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root with the following values:

```env
GOOGLE_API_KEY = Gemini api key
RECEIVER_ID = Your personal mail to which mails are being forwaded to
SENDER_ID = Your College ID
GMAIL_APP_PASSWORD = Gmail app password
```

---

## Usage

Run the script:

```bash
python main.py
```

Example output:

```
From: prof@iiitb.ac.in
Subject: Assignment Submission
Analysis: Task created: Submit assignment before Friday
```

---
