#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> git pull"
git pull

echo "==> migrate"
python3 manage.py migrate

echo "==> collectstatic"
python3 manage.py collectstatic --noinput

echo "==> restart gunicorn"
sudo systemctl restart mobis-vlg
sudo systemctl status mobis-vlg --no-pager
