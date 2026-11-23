# Quick Start on Windows (VS Code)

This is a **desktop quiz application**. You need **one server terminal** and **one client window per player**. You do **not** need MySQL, Node.js, Vercel, or Render.

## 1. Extract the ZIP

Right-click `multiplayer-quiz-system.zip` → **Extract All**. In VS Code, choose **File → Open Folder** and select the extracted `multiplayer-quiz-system` folder.

## 2. Start the server

Open **Terminal → New Terminal** in VS Code and run:

```powershell
py server.py
```

Keep this terminal open. If you see `py` not found, try `python server.py`. Alternatively, double-click `start_server.bat`.

## 3. Open two players

Open another terminal using the **+** icon in the VS Code terminal panel:

```powershell
py client.py
```

Run the same command in a third terminal to open another window. Alternatively, double-click `start_client.bat` twice.

In the first window, set the nickname to `Alice`; in the second, set it to `Bob`. Click **Connect** in both. Use server `127.0.0.1` and port `5555` when all windows are on the same PC.

## 4. Start the game

Return to the **server terminal**, type:

```text
start
```

Press Enter. Both windows receive the same quiz question and countdown. Choose answers and send chat messages. The server moves automatically through all 20 questions.

## 5. Restart or stop

In the server terminal:

- `reset` followed by `start` — play again with scores cleared
- `stop` — end the current game
- `reload` — reload edited `questions.json` when the game is inactive
- `quit` — close the server

## 6. Test the project

In a separate terminal in the project folder:

```powershell
py -m unittest discover -s tests -v
```

The tests do not require opening GUI windows.

## If you see an error

- **Connection refused:** Run the server before the clients.
- **WinError 10048:** Another server may already be running on port 5555. Close it, or start the server with `py server.py --port 5556` and enter `5556` in each client.
- **No module named tkinter:** Reinstall Python from python.org with Tk/Tcl support.
- **Python not found:** Try the `py` launcher, which is commonly installed on Windows.
- **Players on different computers:** Read the LAN section of `README.md` for host IP and firewall instructions.
