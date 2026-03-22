#!/bin/bash
# Start the R.E.A.C.T backend API and frontend dev server

echo "Starting R.E.A.C.T API server on http://localhost:8000 ..."
cd "$(dirname "$0")"
uvicorn api:app --reload --port 8000 &
API_PID=$!

echo "Starting frontend on http://localhost:3000 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

trap "kill $API_PID $FRONTEND_PID" EXIT
wait
