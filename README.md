# Princess Evelyn Homepage

A small Flask site for `princessevelyn.com`, with a playful homepage, error pages,
dog and cat easter eggs, and public license hosting.

## Features

- Homepage with contact links and custom Comic Neue fonts
- `/dog` and `/cat` easter egg pages
- Custom 403, 404, and 500 error pages
- Security headers and allowed-host checking
- `/license/pel-1` route for Princess Evelyn's License

## Project Layout

```text
homepage/
├── app.py                         # Flask app and route handlers
├── wsgi.py                        # Gunicorn entry point
├── gunicorn.conf.py               # Gunicorn configuration
├── requirements.txt               # Python dependencies
├── LICENSE.md                     # Princess Evelyn's License
├── deploy/
│   ├── deploy.sh                  # Install and restart helper
│   ├── homepage.service           # systemd unit
│   └── princessevelyn.com         # nginx site config
├── static/
│   ├── PEL-1.md                   # Web-served license text
│   ├── robots.txt
│   ├── fonts/
│   └── img/
└── templates/
    ├── index.html
    ├── dog.html
    ├── cat.html
    ├── 403.html
    ├── 404.html
    └── 500.html
```

## Requirements

- Python 3.10+
- Flask
- Gunicorn for production serving
- `python-dotenv` for local `.env` loading
- nginx and systemd for the included deployment files

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Environment variables are loaded from `.env` at startup.

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_SECRET_KEY` | unset | Flask session signing key. Set this in production. |
| `ALLOWED_HOSTS` | `princessevelyn.com,www.princessevelyn.com,localhost,127.0.0.1` | Comma-separated hosts accepted by the app. |

The deployment unit expects the environment file at:

```text
/home/evelyn/homepage/.env
```

## Running Locally

```bash
flask --app app run --debug
```

Then visit:

```text
http://127.0.0.1:5000/
```

## Deployment

The repo includes a systemd unit and nginx config under `deploy/`.

The deployment helper installs dependencies, validates nginx, reloads services,
and restarts the homepage service:

```bash
./deploy/deploy.sh
```

The production service runs Gunicorn through `wsgi:app` using
`gunicorn.conf.py`.

## License

This project is licensed under Princess Evelyn's License. See
[LICENSE.md](LICENSE.md).
