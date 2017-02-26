#!/bin/sh -e

# sync database to latest migration
FLASK_APP=app.py flask db upgrade

# start service discovery task in the background
if [ "$SERVICE_URL" != "" ]; then
    python -c "from microflack_common.container import register; register()" &
fi

# run web server
exec gunicorn -b 0.0.0.0:5000 --access-logfile - --error-logfile - app:app
