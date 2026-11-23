# QuizVerse Web: Deployment checklist

## 1. GitHub

From the local `multiplayer-quiz-system` repository root, after copying the new `web` folder:

```powershell
git add web start_web_backend.bat start_web_frontend.bat
git commit -m "Add QuizVerse browser version"
git push origin main
```

## 2. Render (backend)

- **Repository:** `op-shubham123/multiplayer-quiz-system`
- **Service type:** Web Service
- **Root Directory:** leave blank
- **Runtime:** Python
- **Build Command:** `pip install -r web/backend/requirements.txt`
- **Start Command:** `uvicorn web.backend.app:app --host 0.0.0.0 --port $PORT`
- **Workers/instances:** 1
- **Test:** `https://YOUR-RENDER-URL.onrender.com/health`

After Vercel deployment, add Render environment variable:

```text
CORS_ORIGINS=https://YOUR-VERCEL-URL.vercel.app,http://localhost:5173,http://127.0.0.1:5173
```

Save and redeploy/restart Render.

## 3. Vercel (frontend)

- **Repository:** the same GitHub repository
- **Root Directory:** `web/frontend`
- **Framework:** Vite
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Environment variable (Config/Plain Text):** `VITE_API_URL=https://YOUR-RENDER-URL.onrender.com`

Redeploy after setting the environment variable.

## 4. Verify

1. Open the Vercel site in a browser.
2. Enter a nickname and click **Create my room**.
3. Open the site in an incognito window or on a second device.
4. Join using a different nickname and the same room code.
5. In the host window, click **Start game**.
6. Confirm both players receive the same question, scores update, and chat works.

**Note:** Rooms are temporary. They disappear when the backend restarts. For reliable persistence or multiple backend instances, add a database/Redis in a future upgrade.
