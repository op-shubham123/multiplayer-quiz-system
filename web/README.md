# QuizVerse Web — Browser Multiplayer Edition

A responsive React/Vite web frontend and FastAPI WebSocket backend for the **existing QuizVerse project**. The original desktop `server.py` / `client.py` still work; the web version is separate.

## Features

- Create a private room and share a **six-character code**
- Join with a nickname from a phone, laptop, or another browser
- Up to **30 players per room**, multiple independent rooms
- Real-time synchronized questions and countdowns
- **20 included questions** (reuses the repository's `questions.json`)
- One answer per player per question; **10 points per correct answer**
- Instant answer reveal, explanation, live leaderboard, and chat
- Host-only Start, Next/Reveal, Stop, Reset/Play again, and Reload controls
- Reconnect after a page refresh (session token saved in session storage)
- Answers remain hidden from players until the round ends

## Directory layout

```text
multiplayer-quiz-system/
  quiz_core.py          <-- existing, shared quiz rules
  questions.json        <-- existing, shared question bank
  server.py             <-- existing desktop TCP server
  client.py             <-- existing Tkinter client
  web/
    backend/
      app.py            <-- FastAPI + WebSockets
      requirements.txt
      tests/test_web.py
    frontend/
      package.json      <-- React + Vite
      index.html
      src/App.jsx
      src/styles.css
      .env.example
```

**Important:** Keep `web` inside the existing repository folder alongside `quiz_core.py` and `questions.json`. The backend imports these two existing files. Do not deploy the old TCP server for the web version.

## Run locally on Windows (VS Code)

**Requirements:** Python 3.10+ and Node.js 20+.

1. In VS Code, choose **File → Open Folder** and open `multiplayer-quiz-system` (the folder containing `quiz_core.py`).
2. Open **Terminal → New Terminal**. Install backend dependencies from the **repository root**:

   ```powershell
   py -m pip install -r web/backend/requirements.txt
   ```

3. In the same terminal, start the **web backend** (not `server.py`):

   ```powershell
   py -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000 --reload
   ```

4. Open `http://127.0.0.1:8000/health`. You should see `{"status":"ok","mode":"websocket-multiplayer",...}`.
5. Open a **second** VS Code terminal, still at the repository root:

   ```powershell
   cd web/frontend
   npm install
   npm run dev
   ```

6. Open **http://localhost:5173**. Enter your nickname and click **Create my room**.
7. Copy the six-character room code. In a second browser/incognito window open **http://localhost:5173**, select **Join a room**, and enter a different nickname plus the code.
8. In the host window, click **Start game**. Answer questions, use chat, and watch the leaderboard.

**Windows shortcut:** After the initial setup, you can double-click `start_web_backend.bat` and `start_web_frontend.bat` from the repository root instead of typing the commands each time. They launch two separate windows.

The default frontend API address is `http://localhost:8000`, so a local `.env` file is optional. If your backend runs elsewhere, create `web/frontend/.env` with:

```dotenv
VITE_API_URL=http://localhost:8000
```

Restart `npm run dev` after changing `.env`.

### Run from two devices on the same Wi-Fi (optional)

For local LAN testing, run Uvicorn with `--host 0.0.0.0`, set `VITE_API_URL=http://YOUR_LAPTOP_IP:8000`, and add `http://YOUR_LAPTOP_IP:5173` to `CORS_ORIGINS`. Your laptop firewall must allow ports 5173 and 8000. On another device, visit `http://YOUR_LAPTOP_IP:5173`. Do not expose the local development server directly to the public internet.

## Deploy to GitHub, Render, and Vercel

### A. Upload the web folder to the existing GitHub repository

Copy the `web` folder into your existing local `multiplayer-quiz-system` Git repository. From the repository root:

```powershell
git status
git add web
git commit -m "Add QuizVerse browser multiplayer version"
git push origin main
```

Do not create a second repository unless you specifically want one. The old desktop version remains in the same repository.

### B. Deploy backend on Render

1. Go to **https://dashboard.render.com** and create a **New → Web Service**.
2. Connect the GitHub repository `op-shubham123/multiplayer-quiz-system`.
3. Set **Root Directory** to **blank / repository root** (important).
4. Select **Python** as the runtime.
5. Set **Build Command**:

   ```bash
   pip install -r web/backend/requirements.txt
   ```

6. Set **Start Command**:

   ```bash
   uvicorn web.backend.app:app --host 0.0.0.0 --port $PORT
   ```

7. Deploy with **one worker and one instance**. This demo stores room state in server memory, so multiple instances do not share rooms.
8. Open `https://YOUR-RENDER-URL.onrender.com/health` and check for `"status":"ok"`.

After creating your Vercel deployment, return to Render → **Environment** and add:

| Key | Value |
| --- | --- |
| `CORS_ORIGINS` | `https://YOUR-VERCEL-URL.vercel.app,http://localhost:5173,http://127.0.0.1:5173` |

Use your **exact** Vercel URL (no trailing slash). This controls both HTTP CORS and allowed browser WebSocket origins. Save and redeploy/restart Render.

### C. Deploy frontend on Vercel

1. Go to **https://vercel.com/new**, import the **same GitHub repository**.
2. Set **Root Directory** to **`web/frontend`**.
3. Framework preset: **Vite**.
4. Build Command: `npm run build` (default).
5. Output Directory: `dist` (default).
6. Under **Environment Variables**, create:

   | Key | Value |
   | --- | --- |
   | `VITE_API_URL` | `https://YOUR-RENDER-URL.onrender.com` |

   Select **Production** (and Preview if you use preview URLs). Use **plain text / config**, not a secret, because Vite exposes `VITE_` values in the browser bundle by design.
7. Deploy or redeploy after adding the environment variable.
8. Open your Vercel URL, create a room, and connect another browser using the same link.

**Do not use `ws://` in `VITE_API_URL`.** Set an `https://` backend URL; the app automatically converts it to secure `wss://` for WebSocket connections.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not reach the server` | Check Render `/health`, and `VITE_API_URL` in Vercel; redeploy after changing it |
| `Origin not allowed` or WebSocket closes immediately | Set `CORS_ORIGINS` on Render to the **exact** Vercel frontend URL; restart Render |
| `Room not found` after a restart | Expected: rooms are stored in memory; create a new room |
| `ModuleNotFoundError: quiz_core` | Render Root Directory must be **blank**, and `quiz_core.py` must be at the repository root |
| `Cannot find package react` | Run `npm install` in `web/frontend` |
| `Port 8000 already in use` | Stop another FastAPI server, or choose a different port and update `VITE_API_URL` |
| First connection takes a while | The hosting service may be waking up after inactivity |
| One person sees an old disconnected player | Reopen the original browser tab to reconnect or use a new nickname; idle rooms expire after one hour with no connected players |

## Protocol and security notes

- Room creation: `POST /api/rooms` → `{room_code, host_token}`.
- Room information: `GET /api/rooms/{room_code}`.
- WebSocket: `/ws/{room_code}`; first message `{"type":"join","name":"Alice"}`. Host additionally supplies the `host_token` once.
- Other messages: `answer`, `chat`, `host_action`, `leave`, `ping`.
- Each player receives a private session token and their own answer status; the host's key and correct answers are not broadcast during questions.
- Room codes are for casual private games, **not secure access control**. This is a portfolio/demo app, not a production anti-cheat or identity platform.
- Server state is **in memory**, not in a database. A restart clears all rooms and scores. Run **one Uvicorn worker**; for scale-out, use Redis and shared state.
- WebSocket browser origins are checked against `CORS_ORIGINS`. Public HTTPS frontends require WSS (handled automatically).
- Keep host tokens and session tokens private. Do not commit real `.env` files.

## Tests

From the repository root:

```powershell
py -m pip install pytest httpx
py -m pytest -q web/backend/tests/test_web.py
py -m unittest discover -s tests -v
```

## Edit the questions

Modify the existing root `questions.json`, then restart the backend or click **Reload questions** in a lobby/finished game. Each question needs `prompt`, four `options`, a `correct_index` from 0 to 3, and optional `explanation`.
