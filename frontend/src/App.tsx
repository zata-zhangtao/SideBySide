import React, { useEffect, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

function useToken() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const save = (t: string | null) => {
    if (t) localStorage.setItem('token', t)
    else localStorage.removeItem('token')
    setToken(t)
  }
  return { token, setToken: save }
}

async function api(path: string, opts: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const headers: any = { ...(opts.headers || {}) }
  if (opts.body && !(opts.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [err, setErr] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    try {
      if (mode === 'register') {
        const data = await api('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) })
        localStorage.setItem('token', data.access_token)
        onLogin()
      } else {
        const form = new URLSearchParams()
        form.set('username', username)
        form.set('password', password)
        const res = await fetch(`${API_BASE}/auth/login`, { method: 'POST', body: form })
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json()
        localStorage.setItem('token', data.access_token)
        onLogin()
      }
    } catch (e: any) {
      setErr(String(e))
    }
  }

  return (
    <div className="container" style={{ placeItems: 'center' }}>
      <form onSubmit={submit} className="card stack" style={{ maxWidth: 420, margin: '48px auto' }}>
        <h2 className="card-title">{mode === 'login' ? '登录' : '注册'}</h2>
        <input className="input" placeholder="用户名" value={username} onChange={e => setUsername(e.target.value)} />
        <input className="input" placeholder="密码" type="password" value={password} onChange={e => setPassword(e.target.value)} />
        {err && <div className="alert alert-error">{err}</div>}
        <div className="row">
          <button className="btn btn-primary" type="submit">{mode === 'login' ? '登录' : '注册并登录'}</button>
          <button className="btn btn-ghost" type="button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? '去注册' : '去登录'}
          </button>
        </div>
      </form>
    </div>
  )
}

function UploadWordlist() {
  const [name, setName] = useState('My Words')
  const [listId, setListId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [imgFile, setImgFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [mode, setMode] = useState<'file' | 'image'>('file')
  const [loading, setLoading] = useState(false)

  const createList = async () => {
    const fd = new FormData()
    fd.set('name', name)
    const res = await fetch(`${API_BASE}/wordlists`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    setListId(data.id)
  }

  const upload = async () => {
    if (!listId || !file) return
    const fd = new FormData()
    fd.set('file', file)
    const res = await fetch(`${API_BASE}/wordlists/${listId}/upload`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    setMessage(data.message)
  }

  const createFromImage = async () => {
    if (!imgFile) return
    setLoading(true)
    setMessage('')
    try {
      const fd = new FormData()
      fd.set('name', name)
      fd.set('file', imgFile)
      const res = await fetch(`${API_BASE}/wordlists/from_image`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setListId(data.id)
      setMessage(data.message || '图片识别完成')
    } catch (e: any) {
      setMessage(`失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  // Preview management
  useEffect(() => {
    if (imgFile) {
      const url = URL.createObjectURL(imgFile)
      setPreviewUrl(url)
      return () => URL.revokeObjectURL(url)
    } else {
      setPreviewUrl(null)
    }
  }, [imgFile])

  // Paste/Drop handlers (image)
  const dropRef = useRef<HTMLDivElement | null>(null)
  const onPaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (let i = 0; i < items.length; i++) {
      const it = items[i]
      if (it.type && it.type.startsWith('image/')) {
        const f = it.getAsFile()
        if (f) {
          setImgFile(f)
          e.preventDefault()
          setMessage('已从剪贴板粘贴图片')
          break
        }
      }
    }
  }
  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const files = e.dataTransfer?.files
    if (!files || !files.length) return
    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      if (f.type && f.type.startsWith('image/')) {
        setImgFile(f)
        setMessage('已选择图片（拖拽）')
        break
      }
    }
  }
  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }
  useEffect(() => {
    if (mode === 'image') {
      // Focus dropzone for immediate paste
      dropRef.current?.focus()
    }
  }, [mode])

  return (
    <div className="card stack">
      <h3 className="card-title">上传单词库</h3>
      <div className="row">
        <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="词库名称" />
        <button className="btn btn-primary" onClick={createList}>创建词库</button>
        {listId && <span className="badge">已创建: {listId}</span>}
      </div>
      <div className="row">
        <button className={`btn btn-sm ${mode === 'file' ? 'btn-primary' : ''}`} onClick={() => setMode('file')}>CSV/JSON 导入</button>
        <button className={`btn btn-sm ${mode === 'image' ? 'btn-primary' : ''}`} onClick={() => setMode('image')}>图片建库（LLM）</button>
      </div>

      {mode === 'file' && (
        <div className="row">
          <input className="file" type="file" accept=".csv,.json" onChange={e => setFile(e.target.files?.[0] || null)} />
          <button className="btn" onClick={upload} disabled={!listId || !file}>上传</button>
        </div>
      )}

      {mode === 'image' && (
        <>
          <div className="row">
            <input className="file" type="file" accept="image/*" onChange={e => setImgFile(e.target.files?.[0] || null)} />
            <button className="btn" onClick={createFromImage} disabled={!imgFile || loading}>{loading ? '识别中…' : '识别并建库'}</button>
          </div>
          <div ref={dropRef} className="dropzone" onPaste={onPaste} onDrop={onDrop} onDragOver={onDragOver} tabIndex={0}>
            {previewUrl ? (
              <div className="stack" style={{ alignItems: 'center' }}>
                <img className="preview" src={previewUrl} alt="预览" />
                <div className="muted">已准备：{imgFile?.name || '粘贴的图片'}（{imgFile ? Math.round(imgFile.size / 1024) : 0} KB）</div>
                <div className="muted">按 Ctrl/⌘+V 替换，或拖拽进来</div>
              </div>
            ) : (
              <div className="stack" style={{ alignItems: 'center' }}>
                <div>将图片粘贴到此处（Ctrl/⌘+V）</div>
                <div className="muted">或拖拽图片到此处</div>
              </div>
            )}
          </div>
        </>
      )}

      {message && (
        <div className={`alert ${message.startsWith('失败') ? 'alert-error' : 'alert-success'}`}>{message}</div>
      )}
    </div>
  )
}

function StartSession() {
  const [wordlistId, setWordlistId] = useState('')
  const [friend, setFriend] = useState('')
  const [sessionId, setSessionId] = useState<number | null>(null)

  const create = async () => {
    const data = await api(`/sessions?wordlist_id=${encodeURIComponent(wordlistId)}&friend_username=${encodeURIComponent(friend)}`, { method: 'POST' })
    setSessionId(data.id)
  }

  return (
    <div className="card stack">
      <h3 className="card-title">创建异步打卡</h3>
      <div className="row">
        <input className="input" placeholder="词库ID" value={wordlistId} onChange={e => setWordlistId(e.target.value)} />
        <input className="input" placeholder="好友用户名" value={friend} onChange={e => setFriend(e.target.value)} />
        <button className="btn btn-primary" onClick={create}>创建</button>
        {sessionId && <span className="badge">Session #{sessionId}</span>}
      </div>
      {sessionId && <Quiz sessionId={sessionId} />}
    </div>
  )
}

function Quiz({ sessionId }: { sessionId: number }) {
  const [word, setWord] = useState<any>(null)
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState<any>(null)
  const [board, setBoard] = useState<any>(null)
  const [detail, setDetail] = useState<any>(null)
  const [wrong, setWrong] = useState<any[]>([])

  const loadNext = async () => {
    const w = await api(`/sessions/${sessionId}/next_word`)
    setWord(w)
    setAnswer('')
    setResult(null)
    refresh()
  }
  const submit = async () => {
    const r = await api(`/sessions/${sessionId}/attempts?word_id=${word.word_id}&answer=${encodeURIComponent(answer)}`, { method: 'POST' })
    setResult(r)
    refresh()
  }
  const refresh = async () => {
    const [b, d, w] = await Promise.all([
      api(`/sessions/${sessionId}/scoreboard`),
      api(`/sessions/${sessionId}`),
      api(`/sessions/${sessionId}/wrongbook`).catch(() => []),
    ])
    setBoard(b)
    setDetail(d)
    setWrong(w)
  }
  useEffect(() => { loadNext() }, [])

  const left = detail?.participants?.[0]
  const right = detail?.participants?.[1]
  const scores = board?.scores || {}
  const accuracy = board?.accuracy || {}

  return (
    <div className="page">
      <h4 className="section-title">抽背单词</h4>
      {word && (
        <div className="card stack">
          <div className="muted">释义</div>
          <div>{word.definition || '—'}</div>
          <div className="row">
            <input className="input" placeholder="请输入英文单词" value={answer} onChange={e => setAnswer(e.target.value)} />
            <button className="btn btn-primary" onClick={submit}>提交</button>
            <button className="btn" onClick={loadNext}>换一个</button>
          </div>
        </div>
      )}
      {result && (
        <div className={`alert ${result.correct ? 'alert-success' : 'alert-error'}`}>
          {result.correct ? '回答正确！' : '回答错误'}
          {!result.correct && (
            <div style={{ marginTop: 6 }}>
              正确答案：{result.correct_answer}
              <div>例句：{result.example || '（无）'}</div>
            </div>
          )}
        </div>
      )}
      <div className="divider" />
      <h4 className="section-title">左右分屏 · 进度与积分</h4>
      <div className="grid grid-2">
        <div className="card stack">
          <div style={{ fontWeight: 600 }}>{left?.username || '左侧'}</div>
          <div>积分：{scores?.[left?.id] || 0}</div>
          <div>正确率：{Math.round((accuracy?.[left?.id] || 0) * 100)}%</div>
        </div>
        <div className="card stack" style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 600 }}>{right?.username || '右侧'}</div>
          <div>积分：{scores?.[right?.id] || 0}</div>
          <div>正确率：{Math.round((accuracy?.[right?.id] || 0) * 100)}%</div>
        </div>
      </div>
      <div className="divider" />
      <h4 className="section-title">错题本（本次）</h4>
      {wrong.length === 0 ? '暂无' : (
        <div className="card">
          <ul>
            {wrong.map((w: any) => (
              <li key={w.word_id}>{w.term} — {w.definition || ''}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Leaderboard() {
  const [items, setItems] = useState<any[]>([])
  useEffect(() => { api('/leaderboard?period=weekly').then(setItems).catch(() => setItems([])) }, [])
  return (
    <div className="card">
      <h3 className="card-title">排行榜（周）</h3>
      <ol>
        {items.map((it, i) => (
          <li key={i}>{it.username}: {it.points}</li>
        ))}
      </ol>
    </div>
  )
}

function WeeklyReport() {
  const [peer, setPeer] = useState('')
  const [report, setReport] = useState<any>(null)
  const run = async () => { const r = await api(`/reports/weekly?user2_username=${encodeURIComponent(peer)}`); setReport(r) }
  return (
    <div className="card stack">
      <h3 className="card-title">学习报告（周）</h3>
      <div className="row">
        <input className="input" placeholder="好友用户名" value={peer} onChange={e => setPeer(e.target.value)} />
        <button className="btn" onClick={run}>生成</button>
      </div>
      {report && <pre>{JSON.stringify(report, null, 2)}</pre>}
    </div>
  )
}

function Friends() {
  const [username, setUsername] = useState('')
  const [list, setList] = useState<any[]>([])
  const add = async () => { await api(`/friends/add?username=${encodeURIComponent(username)}`, { method: 'POST' }); setUsername(''); refresh() }
  const refresh = async () => { const r = await api('/friends'); setList(r) }
  useEffect(() => { refresh() }, [])
  return (
    <div className="card stack">
      <h3 className="card-title">好友</h3>
      <div className="row">
        <input className="input" value={username} onChange={e => setUsername(e.target.value)} placeholder="用户名" />
        <button className="btn" onClick={add}>添加好友</button>
      </div>
      <ul>
        {list.map(f => <li key={f.id}>{f.username}</li>)}
      </ul>
    </div>
  )
}

export default function App() {
  const { token, setToken } = useToken()
  const [me, setMe] = useState<any>(null)
  const [tab, setTab] = useState<'upload'|'session'|'leaderboard'|'report'|'friends'>('upload')

  useEffect(() => { if (token) api('/users/me').then(setMe).catch(() => setMe(null)) }, [token])

  if (!token || !me) {
    return <Login onLogin={() => setToken(localStorage.getItem('token'))} />
  }

  return (
    <>
      <header className="app-header">
        <div className="container app-bar">
          <div className="brand">SideBySide</div>
          <nav className="tabs">
            <button className={`btn btn-sm tab ${tab === 'upload' ? 'active' : ''}`} onClick={() => setTab('upload')}>上传词库</button>
            <button className={`btn btn-sm tab ${tab === 'session' ? 'active' : ''}`} onClick={() => setTab('session')}>开始打卡</button>
            <button className={`btn btn-sm tab ${tab === 'friends' ? 'active' : ''}`} onClick={() => setTab('friends')}>好友</button>
            <button className={`btn btn-sm tab ${tab === 'leaderboard' ? 'active' : ''}`} onClick={() => setTab('leaderboard')}>排行榜</button>
            <button className={`btn btn-sm tab ${tab === 'report' ? 'active' : ''}`} onClick={() => setTab('report')}>学习报告</button>
          </nav>
          <div className="row">
            <span className="muted">Hi, {me.username}</span>
            <button className="btn btn-outline" onClick={() => { localStorage.removeItem('token'); location.reload() }}>退出</button>
          </div>
        </div>
      </header>
      <main className="container grid">
        {tab === 'upload' && <UploadWordlist />}
        {tab === 'session' && <StartSession />}
        {tab === 'leaderboard' && <Leaderboard />}
        {tab === 'report' && <WeeklyReport />}
        {tab === 'friends' && <Friends />}
      </main>
    </>
  )
}
