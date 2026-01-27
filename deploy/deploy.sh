#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/evelyn/homepage"
VENV="$APP_DIR/.venv"

cd "$APP_DIR"

"$VENV/bin/pip" install --upgrade pip wheel --quiet
if [[ -f requirements.txt ]]; then
  "$VENV/bin/pip" install -r requirements.txt --quiet
elif [[ -f pyproject.toml ]]; then
  "$VENV/bin/pip" install . --quiet
fi

sudo nginx -t
sudo systemctl reload nginx
sudo systemctl daemon-reload

sudo systemctl enable --now homepage
sudo systemctl restart homepage
