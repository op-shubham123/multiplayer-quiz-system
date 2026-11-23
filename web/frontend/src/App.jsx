import React, { useEffect, useRef, useState } from 'react';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const WS_URL = API_URL.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
const STORAGE_KEY = 'quizverse-web-session-v1';
const LETTERS = ['A', 'B', 'C', 'D'];

function Glyph({ name, size = 19, strokeWidth = 1.8 }) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };
  const icons = {
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    trophy: <><path d="M8 21h8M12 17v4M7 4h10v7a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4v3a4 4 0 0 0 4 4M17 6h3v3a4 4 0 0 1-4 4"/></>,
    chat: <><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    copy: <><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    play: <><path d="m8 5 11 7-11 7V5Z"/></>,
    reset: <><path d="M3 11a9 9 0 1 1 2.8 6.5M3 4v7h7"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3M12 3h6a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3h-6"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    link: <><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></>,
    stop: <rect x="5" y="5" width="14" height="14" rx="3"/>,
    send: <><path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13"/></>,
    spark: <path d="m12 2 2.3 7.7L22 12l-7.7 2.3L12 22l-2.3-7.7L2 12l7.7-2.3L12 2Z"/>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
    wifi: <><path d="M2 8.5a15 15 0 0 1 20 0M5 12a10 10 0 0 1 14 0M8.5 15.5a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none"/></>,
  };
  return <svg {...props}>{icons[name] || icons.spark}</svg>;
}

function Brand() {
  return <div className="brand"><div className="brand-mark"><Glyph name="spark" size={23} strokeWidth={2.4} /></div><span>quiz<span className="brand-accent">verse</span></span><span className="brand-dot">.</span></div>;
}

function Landing({ nickname, setNickname, roomInput, setRoomInput, mode, setMode, onSubmit, busy, error }) {
  return <>
    <header className="site-header wrap"><Brand /><div className="header-note"><span className="status-dot"/> REAL-TIME MULTIPLAYER</div></header>
    <main className="landing wrap">
      <div className="hero-copy">
        <div className="eyebrow"><span className="eyebrow-star">✳</span> THE ULTIMATE QUIZ ARENA <span className="eyebrow-line" /></div>
        <h1>Big brains.<br/><span>Better together.</span></h1>
        <p>Challenge your friends, race the clock, and climb the leaderboard. One room. Endless bragging rights.</p>
        <div className="hero-features"><span><Glyph name="users" size={17}/> Up to 30 players</span><span><Glyph name="clock" size={17}/> Live countdowns</span><span><Glyph name="trophy" size={17}/> Instant scoring</span></div>
        <div className="hero-visual" aria-hidden="true">
          <div className="visual-orbit orbit-one"/><div className="visual-orbit orbit-two"/>
          <div className="visual-card visual-card-a"><span className="tiny-avatar purple">S</span><div><b>Sarah just scored!</b><small>+10 points</small></div><span className="visual-fire">✦</span></div>
          <div className="visual-card visual-card-b"><span className="visual-trophy"><Glyph name="trophy" size={20}/></span><div><b>Leaderboard updated</b><small>Round 4 of 20</small></div></div>
          <div className="visual-spark visual-spark-one">✧</div><div className="visual-spark visual-spark-two">✳</div>
        </div>
      </div>
      <div className="entry-column">
        <div className="entry-card">
          <div className="entry-top"><div className="entry-icon"><Glyph name="spark" size={22}/></div><span className="entry-tag">LET'S PLAY</span></div>
          <h2>Ready to compete?</h2><p className="muted entry-description">Get started in seconds. No account needed.</p>
          <div className="mode-switch" role="tablist" aria-label="Choose how to play">
            <button type="button" role="tab" aria-selected={mode === 'create'} className={mode === 'create' ? 'active' : ''} onClick={() => setMode('create')}>Create a room</button>
            <button type="button" role="tab" aria-selected={mode === 'join'} className={mode === 'join' ? 'active' : ''} onClick={() => setMode('join')}>Join a room</button>
          </div>
          <form onSubmit={onSubmit}>
            <label className="form-label" htmlFor="nickname">YOUR NICKNAME</label>
            <div className="input-wrap"><span className="input-leading"><Glyph name="users" size={18}/></span><input id="nickname" autoComplete="nickname" maxLength={20} minLength={2} placeholder="e.g. QuizMaster99" value={nickname} onChange={e => setNickname(e.target.value)} required /></div>
            {mode === 'join' && <><label className="form-label" htmlFor="room-code">ROOM CODE</label><div className="input-wrap"><span className="input-leading"><Glyph name="link" size={18}/></span><input id="room-code" className="code-input" autoComplete="off" maxLength={6} placeholder="6-CHARACTER CODE" value={roomInput} onChange={e => setRoomInput(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))} required /></div></>}
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="primary-button" disabled={busy} type="submit">{busy ? 'Connecting…' : mode === 'create' ? 'Create my room' : 'Join the game'}<Glyph name="arrow" size={19}/></button>
          </form>
          <div className="entry-bottom"><Glyph name="shield" size={17}/> Free to play · No signup required</div>
        </div>
        <div className="entry-tip"><span className="tip-icon">✦</span><div><strong>Playing with friends?</strong><p>Create a room and share the 6-character code. Everyone joins from their own device.</p></div></div>
      </div>
    </main>
    <footer className="landing-footer wrap"><span>© QuizVerse · Built for the love of competition</span><span>THINK FAST. PLAY FAIR. HAVE FUN.</span></footer>
  </>;
}

function Leaderboard({ players, playerId }) {
  return <section className="panel leaderboard-panel"><div className="panel-heading"><div><span className="heading-icon gold"><Glyph name="trophy" size={19}/></span><h3>Leaderboard</h3></div><span className="small-pill">LIVE</span></div>
    <div className="leader-list">{players.length ? players.map((p, i) => <div className={'leader-row ' + (p.id === playerId ? 'my-row' : '')} key={p.id}><span className={'rank rank-' + i}>{i === 0 ? '♛' : String(i + 1).padStart(2, '0')}</span><span className={'avatar avatar-' + (i % 5)}>{p.name.slice(0, 1).toUpperCase()}</span><div className="leader-name"><span>{p.name}{p.id === playerId && <em>you</em>}</span><small>{p.is_host ? 'Room host' : p.connected ? 'Playing now' : 'Offline'}</small></div><strong>{p.score}<small> pts</small></strong></div>) : <p className="empty-state">Players will appear here.</p>}</div>
  </section>;
}

function Chat({ messages, onSend, playerId }) {
  const [draft, setDraft] = useState('');
  const scrollRef = useRef(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }, [messages]);
  function submit(e) { e.preventDefault(); const text = draft.trim(); if (!text) return; onSend(text); setDraft(''); }
  return <section className="panel chat-panel"><div className="panel-heading"><div><span className="heading-icon violet"><Glyph name="chat" size={19}/></span><h3>Room chat</h3></div><span className="chat-live-dot" /></div>
    <div className="chat-messages" ref={scrollRef} aria-live="polite">{messages.length ? messages.map((m, i) => <div className={'chat-item ' + (m.player_id === playerId ? 'chat-mine' : '')} key={`${i}-${m.time}`}><div className="chat-meta"><b>{m.player_id === playerId ? 'You' : m.name}</b><span>{m.time}</span></div><div className="chat-bubble">{m.text}</div></div>) : <div className="chat-placeholder"><Glyph name="chat" size={27}/><p>No messages yet.<br/>Say hello to your teammates!</p></div>}</div>
    <form className="chat-form" onSubmit={submit}><input aria-label="Chat message" maxLength={300} placeholder="Say something…" value={draft} onChange={e => setDraft(e.target.value)} /><button type="submit" disabled={!draft.trim()} aria-label="Send message"><Glyph name="send" size={17}/></button></form>
  </section>;
}

function QuestionPanel({ game, answer, send, seconds, isHost }) {
  const phase = game?.phase || 'lobby';
  const index = game?.question_index ?? -1;
  const count = game?.question_count || 20;
  const currentAnswer = game?.your_answer ?? answer;
  const locked = currentAnswer !== null && currentAnswer !== undefined;
  const result = game?.result;
  const correct = result?.correct_index;
  const percent = Math.min(100, Math.max(0, ((index + 1) / count) * 100));

  if (phase === 'lobby') return <section className="panel question-panel lobby-panel"><div className="lobby-decoration"><span>✳</span><span>✦</span><span>✳</span></div><div className="lobby-graphic"><div className="lobby-circle circle-outer"/><div className="lobby-circle circle-inner"/><Glyph name="users" size={47} strokeWidth={1.4}/></div><span className="phase-tag"><span className="status-dot"/> WAITING ROOM</span><h2>Gather your squad.</h2><p>Invite your friends using the room code above. {isHost ? 'When everyone is ready, hit Start game to begin.' : 'The host will start the quiz when everyone is ready.'}</p><div className="lobby-hint"><Glyph name="spark" size={19}/> 20 questions · 10 points per correct answer · 20 seconds each</div></section>;
  if (phase === 'finished') return <section className="panel question-panel finished-panel"><div className="finished-icon"><Glyph name="trophy" size={55}/></div><span className="phase-tag">GAME COMPLETE</span><h2>That's a wrap!</h2><p>Great game, everyone. Check the leaderboard to see who came out on top.</p>{isHost && <div className="lobby-hint"><Glyph name="reset" size={18}/> Click Play again above to start a fresh round.</div>}</section>;
  const showQuestion = phase === 'question' || phase === 'results';
  return <section className="panel question-panel">
    <div className="question-head"><div className="round-label"><span className="round-icon"><Glyph name="spark" size={16}/></span> QUESTION {index + 1} <span className="round-of">/ {count}</span></div><div className={'timer-pill ' + (seconds <= 5 && phase === 'question' ? 'timer-low' : '')}><Glyph name="clock" size={17}/>{phase === 'question' ? `${seconds}s left` : 'Answer reveal'}</div></div>
    <div className="progress-track"><div className="progress-fill" style={{ width: `${percent}%` }}/></div>
    {showQuestion && <><h2 className="question-title">{game.question?.prompt || 'Revealing the answer…'}</h2><div className="question-subtitle">{phase === 'results' ? 'Here’s how everyone did.' : locked ? 'Answer locked in. Waiting for the round to finish.' : 'Select the correct answer below.'}</div>
      <div className="answer-grid">{(game.question?.options || []).map((option, i) => {
        const isCorrect = phase === 'results' && correct === i;
        const isWrong = phase === 'results' && currentAnswer === i && correct !== i;
        const isSelected = phase === 'question' && currentAnswer === i;
        return <button type="button" key={i} className={'answer-option ' + (isCorrect ? 'correct' : isWrong ? 'wrong' : isSelected ? 'selected' : '')} disabled={phase !== 'question' || locked} onClick={() => send({ type: 'answer', choice: i })}><span className="answer-letter">{LETTERS[i]}</span><span className="answer-text">{option}</span>{(isCorrect || isSelected) && <Glyph name="check" size={20}/>}</button>;
      })}</div>
      {phase === 'results' && <div className="answer-explanation"><span className="explanation-star">✦</span><div><strong>Correct answer: {LETTERS[correct]}</strong><p>{result?.explanation || 'Well played!'}</p></div></div>}
      <div className="question-footer"><div><Glyph name="users" size={17}/> {game.answered_count} of {game.players.length} answers submitted</div><span>{phase === 'results' ? 'Next question coming up…' : locked ? '✓ Your answer is locked' : 'Choose wisely!'}</span></div>
    </>}
  </section>;
}

export default function App() {
  const [nickname, setNickname] = useState('');
  const [roomInput, setRoomInput] = useState('');
  const [mode, setMode] = useState('create');
  const [view, setView] = useState('landing');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [session, setSession] = useState(null);
  const [connection, setConnection] = useState('disconnected');
  const [game, setGame] = useState(null);
  const [messages, setMessages] = useState([]);
  const [answer, setAnswer] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [copied, setCopied] = useState(false);
  const socketRef = useRef(null);
  const sessionRef = useRef(null);
  const intentionalCloseRef = useRef(false);

  function connect(nextSession) {
    intentionalCloseRef.current = false;
    sessionRef.current = nextSession;
    setSession(nextSession);
    setView('game');
    setBusy(false);
    setError('');
    setConnection('connecting');
    setGame(null);
    setMessages([]);
    setAnswer(null);
    if (socketRef.current) socketRef.current.close();
    const ws = new WebSocket(`${WS_URL}/ws/${encodeURIComponent(nextSession.roomCode)}`);
    socketRef.current = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'join', name: nextSession.name,
        ...(nextSession.sessionToken ? { session_token: nextSession.sessionToken } : {}),
        ...(!nextSession.sessionToken && nextSession.hostToken ? { host_token: nextSession.hostToken } : {}) }));
    };
    ws.onmessage = (event) => {
      if (socketRef.current !== ws) return;
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'welcome') {
        const updated = { ...sessionRef.current, sessionToken: msg.session_token, playerId: msg.player_id, isHost: msg.is_host };
        sessionRef.current = updated;
        setSession(updated);
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        setMessages(msg.chat_history || []);
        setConnection('connected');
        setError('');
      } else if (msg.type === 'state') {
        setGame(msg);
        setAnswer(msg.your_answer ?? null);
      } else if (msg.type === 'chat') {
        setMessages(previous => [...previous, msg].slice(-50));
      } else if (msg.type === 'answer_ack') {
        setAnswer(msg.choice);
      } else if (msg.type === 'host_promoted') {
        const updated = { ...sessionRef.current, isHost: true };
        sessionRef.current = updated;
        setSession(updated);
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } else if (msg.type === 'error') {
        setError(msg.message || 'Something went wrong.');
      }
    };
    ws.onerror = () => { if (socketRef.current === ws) setError('Could not connect to the quiz server. Check the backend URL and try again.'); };
    ws.onclose = () => {
      if (socketRef.current !== ws || intentionalCloseRef.current) return;
      setConnection('disconnected');
      setError(previous => previous || 'Connection lost. The server may be restarting. Click Reconnect.');
    };
  }

  useEffect(() => {
    try {
      const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
      if (stored?.roomCode && stored?.name && stored?.sessionToken) connect(stored);
    } catch { sessionStorage.removeItem(STORAGE_KEY); }
    return () => { intentionalCloseRef.current = true; socketRef.current?.close(); };
  }, []);
  useEffect(() => { const interval = setInterval(() => setNow(Date.now()), 150); return () => clearInterval(interval); }, []);

  async function handleEntry(e) {
    e.preventDefault();
    setError('');
    const name = nickname.trim();
    if (name.length < 2 || name.length > 20) { setError('Nickname must be 2–20 characters.'); return; }
    if (mode === 'join' && !/^[A-Z0-9]{6}$/.test(roomInput)) { setError('Enter a valid 6-character room code.'); return; }
    setBusy(true);
    try {
      if (mode === 'create') {
        const response = await fetch(`${API_URL}/api/rooms`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not create a room.');
        connect({ roomCode: data.room_code, hostToken: data.host_token, name });
      } else {
        const response = await fetch(`${API_URL}/api/rooms/${roomInput}`);
        if (!response.ok) throw new Error('Room not found. Check the code and try again.');
        connect({ roomCode: roomInput, name });
      }
    } catch (err) { setError(err.message || 'Could not reach the server.'); setBusy(false); }
  }

  function send(payload) {
    if (socketRef.current?.readyState === WebSocket.OPEN && connection === 'connected') {
      socketRef.current.send(JSON.stringify(payload));
    } else { setError('Not connected. Click Reconnect and try again.'); }
  }

  function leave() {
    intentionalCloseRef.current = true;
    const ws = socketRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'leave' }));
      setTimeout(() => ws.close(), 200);
    } else ws?.close();
    socketRef.current = null;
    sessionRef.current = null;
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null); setGame(null); setMessages([]); setAnswer(null); setError(''); setConnection('disconnected'); setView('landing');
  }

  async function copyCode() {
    try { await navigator.clipboard.writeText(session.roomCode); setCopied(true); setTimeout(() => setCopied(false), 1800); }
    catch { setError(`Room code: ${session.roomCode}. Select it and copy manually.`); }
  }

  const seconds = game?.phase === 'question' && game.deadline ? Math.max(0, Math.ceil(game.deadline - now / 1000)) : 0;
  const isHost = Boolean(session?.isHost);
  const phase = game?.phase || 'lobby';
  const isReady = connection === 'connected' && Boolean(game);
  const hostActions = phase === 'lobby' ? [{ action: 'start', label: 'Start game', icon: 'play', main: true }]
    : phase === 'finished' ? [{ action: 'reset', label: 'Play again', icon: 'reset', main: true }, { action: 'reload', label: 'Reload questions', icon: 'reset' }]
    : [{ action: 'next', label: phase === 'question' ? 'Reveal answer' : 'Next question', icon: 'arrow', main: true }, { action: 'stop', label: 'End game', icon: 'stop' }];

  if (view === 'landing') return <Landing nickname={nickname} setNickname={setNickname} roomInput={roomInput} setRoomInput={setRoomInput} mode={mode} setMode={setMode} onSubmit={handleEntry} busy={busy} error={error}/>;

  return <>
    <header className="site-header wrap game-header"><Brand /><div className="game-header-right"><div className={'connection-pill ' + connection}><span className="status-dot"/>{connection === 'connected' ? 'CONNECTED' : connection === 'connecting' ? 'CONNECTING' : 'OFFLINE'}</div><button type="button" className="leave-button" onClick={leave}><Glyph name="logout" size={17}/> Leave room</button></div></header>
    <main className="wrap game-main">
      <div className="room-toolbar"><div className="room-identity"><div className="room-eyebrow">YOUR GAME ROOM <span className="room-eyebrow-line"/></div><div className="room-title-row"><h1>Game room <span className="room-code-text">{session?.roomCode}</span></h1><button className="copy-button" type="button" onClick={copyCode} title="Copy room code"><Glyph name={copied ? 'check' : 'copy'} size={17}/>{copied ? 'Copied!' : 'Copy code'}</button></div><p>Share the code with friends to invite them into your room.</p></div><div className="room-stat-row"><div className="stat-tile"><Glyph name="users" size={20}/><strong>{game?.players?.length || 0}</strong><span>Players</span></div><div className="stat-tile"><Glyph name="spark" size={20}/><strong>{game?.question_count || 20}</strong><span>Questions</span></div></div></div>
      {error && <div className="game-alert" role="alert"><span>{error}</span>{connection !== 'connected' && <button type="button" onClick={() => connect(sessionRef.current || session)}>Reconnect <Glyph name="arrow" size={15}/></button>}<button type="button" aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
      {isHost && <div className="host-toolbar"><div className="host-label"><span className="host-crown">♛</span><div><strong>Host controls</strong><small>You're running this room</small></div></div><div className="host-actions">{hostActions.map(a => <button type="button" key={a.action} className={a.main ? 'host-button main' : 'host-button'} disabled={!isReady} onClick={() => send({ type: 'host_action', action: a.action })}><Glyph name={a.icon} size={16}/>{a.label}</button>)}</div></div>}
      <div className="game-grid"><div className="game-left">{isReady ? <QuestionPanel game={game} answer={answer} send={send} seconds={seconds} isHost={isHost}/> : <section className="panel question-panel loading-panel"><div className="spinner"/><h2>Connecting to QuizVerse…</h2><p>Waking up the game server and joining your room.</p></section>}
        <div className="info-strip"><span><Glyph name="shield" size={17}/> Fair play, fast thinking</span><span><Glyph name="wifi" size={17}/> Real-time synchronized game</span></div>
      </div><aside className="game-sidebar"><Leaderboard players={game?.players || []} playerId={session?.playerId}/><Chat messages={messages} onSend={text => send({ type: 'chat', text })} playerId={session?.playerId}/></aside></div>
    </main>
    <footer className="game-footer wrap"><span>QUIZVERSE <span className="footer-star">✳</span> PLAY TO WIN</span><span>Built for great minds and good times.</span></footer>
  </>;
}
