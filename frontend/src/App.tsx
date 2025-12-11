import React, { useEffect, useMemo, useState } from 'react'

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
  if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json'
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
        const data = await api('/auth/register?username=' + encodeURIComponent(username) + '&password=' + encodeURIComponent(password), { method: 'POST' })
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
    <form onSubmit={submit} style={{ display: 'grid', gap: 8, maxWidth: 320 }}>
      <h2>{mode === 'login' ? '登录' : '注册'}</h2>
      <input placeholder="用户名" value={username} onChange={e => setUsername(e.target.value)} />
      <input placeholder="密码" type="password" value={password} onChange={e => setPassword(e.target.value)} />
      {err && <div style={{ color: 'red' }}>{err}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit">{mode === 'login' ? '登录' : '注册并登录'}</button>
        <button type="button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? '去注册' : '去登录'}</button>
      </div>
    </form>
  )
}

function UploadWordlist() {
  const [name, setName] = useState('My Words')
  const [listId, setListId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('')

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

  return (
    <div style={{ border: '1px solid #ddd', padding: 12 }}>
      <h3>上传单词库</h3>
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="词库名称" />
        <button onClick={createList}>创建词库</button>
        {listId && <span>已创建: {listId}</span>}
      </div>
      <div style={{ marginTop: 8 }}>
        <input type="file" accept=".csv,.json" onChange={e => setFile(e.target.files?.[0] || null)} />
        <button onClick={upload} disabled={!listId || !file}>上传</button>
      </div>
      {message && <div>{message}</div>}
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
    <div style={{ border: '1px solid #ddd', padding: 12 }}>
      <h3>创建异步打卡</h3>
      <input placeholder="词库ID" value={wordlistId} onChange={e => setWordlistId(e.target.value)} />
      <input placeholder="好友用户名" value={friend} onChange={e => setFriend(e.target.value)} />
      <button onClick={create}>创建</button>
      {sessionId && <div>Session #{sessionId}</div>}
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
    <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
      <h4>抽背单词</h4>
      {word && (
        <div>
          <div>释义：{word.definition || '—'}</div>
          <input placeholder="请输入英文单词" value={answer} onChange={e => setAnswer(e.target.value)} />
          <button onClick={submit}>提交</button>
          <button onClick={loadNext}>换一个</button>
        </div>
      )}
      {result && (
        <div style={{ color: result.correct ? 'green' : 'red' }}>
          {result.correct ? '回答正确！' : '回答错误'}
          {!result.correct && (
            <div>
              正确答案：{result.correct_answer}
              <div>例句：{result.example || '（无）'}</div>
            </div>
          )}
        </div>
      )}
      <div style={{ borderTop: '1px solid #eee', paddingTop: 8 }}>
        <h4>左右分屏 · 进度与积分</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div style={{ border: '1px solid #ddd', padding: 8 }}>
            <div style={{ fontWeight: 600 }}>{left?.username || '左侧'}</div>
            <div>积分：{scores?.[left?.id] || 0}</div>
            <div>正确率：{Math.round((accuracy?.[left?.id] || 0) * 100)}%</div>
          </div>
          <div style={{ border: '1px solid #ddd', padding: 8 }}>
            <div style={{ fontWeight: 600, textAlign: 'right' }}>{right?.username || '右侧'}</div>
            <div style={{ textAlign: 'right' }}>积分：{scores?.[right?.id] || 0}</div>
            <div style={{ textAlign: 'right' }}>正确率：{Math.round((accuracy?.[right?.id] || 0) * 100)}%</div>
          </div>
        </div>
      </div>
      <div style={{ borderTop: '1px solid #eee', paddingTop: 8 }}>
        <h4>错题本（本次）</h4>
        {wrong.length === 0 ? '暂无' : (
          <ul>
            {wrong.map((w: any) => (
              <li key={w.word_id}>{w.term} — {w.definition || ''}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )}

function Leaderboard() {
  const [items, setItems] = useState<any[]>([])
  useEffect(() => { api('/leaderboard?period=weekly').then(setItems).catch(() => setItems([])) }, [])
  return (
    <div>
      <h3>排行榜（周）</h3>
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
    <div>
      <h3>学习报告（周）</h3>
      <input placeholder="好友用户名" value={peer} onChange={e => setPeer(e.target.value)} />
      <button onClick={run}>生成</button>
      {report && <pre style={{ background: '#fafafa', padding: 8 }}>{JSON.stringify(report, null, 2)}</pre>}
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
    <div>
      <h3>好友</h3>
      <div>
        <input value={username} onChange={e => setUsername(e.target.value)} placeholder="用户名" />
        <button onClick={add}>添加好友</button>
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
    return <div style={{ padding: 16 }}><Login onLogin={() => setToken(localStorage.getItem('token'))} /></div>
  }

  return (
    <div style={{ padding: 12, display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div>Hi, {me.username}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setTab('upload')}>上传词库</button>
          <button onClick={() => setTab('session')}>开始打卡</button>
          <button onClick={() => setTab('friends')}>好友</button>
          <button onClick={() => setTab('leaderboard')}>排行榜</button>
          <button onClick={() => setTab('report')}>学习报告</button>
          <button onClick={() => { localStorage.removeItem('token'); location.reload() }}>退出</button>
        </div>
      </div>
      {tab === 'upload' && <UploadWordlist />}
      {tab === 'session' && <StartSession />}
      {tab === 'leaderboard' && <Leaderboard />}
      {tab === 'report' && <WeeklyReport />}
      {tab === 'friends' && <Friends />}
    </div>
  )
}
