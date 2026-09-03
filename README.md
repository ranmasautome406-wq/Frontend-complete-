# Bhasha Shiksha Setu — Clean V2

SIH26042 prototype: AI-powered vernacular education.

## Local run

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`.

## Real AI
Set these backend environment variables:

`OPENAI_API_KEY=...`
`OPENAI_MODEL=gpt-5.6-luna`

Never put the API key in `frontend/script.js`.

## Render
Backend as a Python Web Service:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`

Render's Flask deployment documentation uses this build/start pattern. The backend binds to `0.0.0.0` when run directly. Keep the `backend` directory as the service root, or adjust paths accordingly.

## Core demo
1. Select language.
2. Ask AI Tutor by typing or microphone.
3. Receive answer and tap/click the answer to hear it.
4. Use Translate and Explain on the demo lesson.
5. Add quizzes/progress after the core API is verified.
