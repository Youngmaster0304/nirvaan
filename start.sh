#!/bin/bash
cd backend_v2
pip install --upgrade pip && pip install -r requirements.txt
python -c "from seed_indian import seed; seed()"
cd ..
exec uvicorn backend_v2.app.main:app --host 0.0.0.0 --port $PORT
