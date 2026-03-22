#!/bin/bash
# Start the R.E.A.C.T backend API and frontend dev server

# ── MongoDB Atlas (required for persistent zone memory) ───────────────────────
# Set MONGO_URI to your Atlas connection string before running, e.g.:
#   export MONGO_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
if [ -z "$MONGO_URI" ]; then
  echo "⚠  MONGO_URI not set — zone memory will be disabled."
  echo "   Set it with: export MONGO_URI=\"mongodb+srv://...\""
fi

echo "Starting R.E.A.C.T API server on http://localhost:8000 ..."
cd "$(dirname "$0")"
uvicorn api:app --reload --port 8000 &
API_PID=$!

echo "Starting frontend on http://localhost:3000 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

trap "kill $API_PID $FRONTEND_PID" EXIT
wait
