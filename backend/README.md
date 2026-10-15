# CivicSense API

## Run locally

From the project root, install the API dependencies and start the server:

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

## Designate a complaint reviewer

Create the reviewer’s account through the registration page first. Find that account’s ID in the local database, then restart the API with that ID configured:

```powershell
python -c "import sqlite3; print(sqlite3.connect(r'backend\civicsense.sqlite3').execute('SELECT id FROM users WHERE email = ?', ('reviewer@example.com',)).fetchone()[0])"
$env:CIVICSENSE_ADMIN_USER_ID = "<account-id-from-the-query>"
python -m uvicorn app.main:app --app-dir backend --reload
```

Only the configured account can access `/admin` and triage reports. Admins can assign a category and department, set priority and a response target, approve reports, decline them with a reason, and mark approved reports resolved.

## Community features

Signed-in residents can browse and filter community reports, view their status timelines, add updates, and support reports. Report owners receive in-app notifications about status changes and community updates. The community map uses OpenStreetMap tiles and only plots reports whose submitters explicitly chose to share their location; location sharing is optional. No email service or geocoder is configured.

Residents can view their own submissions and review status at `/my-reports`. A declined report includes the reviewer’s reason, and resolved reports are surfaced in the community feed.
