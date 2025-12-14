import React, { useEffect, useRef, useState } from 'react'
import Upload from './components/Upload'

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

interface PreviewWord {
  term: string
  definition?: string | null
  example?: string | null
}

interface BatchImageResult {
  filename: string
  index: number
  status: 'success' | 'error'
  words: PreviewWord[]
  count: number
  error?: string
}

interface BatchProgress {
  task_id: string
  total: number
  completed: number
  errors: number
  current_image: string | null
  current_index: number
  status: 'processing' | 'completed'
  results: BatchImageResult[]
}

function UploadWordlist() {
  const [name, setName] = useState('My Words')
  const [listId, setListId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [imgFile, setImgFile] = useState<File | null>(null)
  const [imgFiles, setImgFiles] = useState<File[]>([])
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [mode, setMode] = useState<'file' | 'image'>('file')
  const [loading, setLoading] = useState(false)
  const [wordlists, setWordlists] = useState<any[]>([])
  const [showList, setShowList] = useState(false)
  const [expandedListId, setExpandedListId] = useState<number | null>(null)
  const [words, setWords] = useState<{ [listId: number]: any[] }>({})
  const [previewWords, setPreviewWords] = useState<PreviewWord[]>([])
  const [isPreviewMode, setIsPreviewMode] = useState(false)
  const [newTerm, setNewTerm] = useState('')
  const [newDefinition, setNewDefinition] = useState('')
  const [newExample, setNewExample] = useState('')
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null)
  const [isBatchMode, setIsBatchMode] = useState(false)
  const [batchResults, setBatchResults] = useState<BatchImageResult[]>([])
  const [expandedImage, setExpandedImage] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const loadWordlists = async () => {
    try {
      const data = await api('/wordlists')
      setWordlists(data)
    } catch (e) {
      setMessage(`加载词库失败：${e}`)
    }
  }

  const loadWords = async (listId: number) => {
    try {
      const data = await api(`/wordlists/${listId}/words`)
      setWords(prev => ({ ...prev, [listId]: data }))
    } catch (e) {
      setMessage(`加载单词失败：${e}`)
    }
  }

  const toggleWordList = (listId: number) => {
    if (expandedListId === listId) {
      setExpandedListId(null)
    } else {
      setExpandedListId(listId)
      if (!words[listId]) {
        loadWords(listId)
      }
    }
  }

  const createList = async () => {
    const fd = new FormData()
    fd.set('name', name)
    const res = await fetch(`${API_BASE}/wordlists`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    setListId(data.id)
    loadWordlists() // Refresh list after creating
  }

  const deleteWordlist = async (listId: number, listName: string) => {
    if (!confirm(`确定要删除词库"${listName}"吗？删除后无法恢复。`)) {
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/wordlists/${listId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setMessage(data.message)
      // Clear expanded state if this list was expanded
      if (expandedListId === listId) {
        setExpandedListId(null)
      }
      // Remove from words cache
      setWords(prev => {
        const newWords = { ...prev }
        delete newWords[listId]
        return newWords
      })
      loadWordlists() // Refresh list after deleting
    } catch (err: any) {
      setMessage(err.message || '删除失败')
    } finally {
      setLoading(false)
    }
  }

  const createFromImage = async () => {
    if (!imgFile) return
    setLoading(true)
    setMessage('')
    try {
      const fd = new FormData()
      fd.set('file', imgFile)
      const res = await fetch(`${API_BASE}/wordlists/preview_from_image`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setPreviewWords(data)
      setIsPreviewMode(true)
      setMessage(`识别到 ${data.length} 个单词，请确认`)
    } catch (e: any) {
      setMessage(`失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const createFromBatchImages = async () => {
    if (!imgFiles || imgFiles.length === 0) return
    setLoading(true)
    setMessage('')
    setIsBatchMode(true)
    setBatchResults([])
    setBatchProgress(null)

    try {
      const fd = new FormData()
      imgFiles.forEach(file => fd.append('files', file))

      const res = await fetch(`${API_BASE}/wordlists/batch_preview_from_images`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()

      setMessage(`开始处理 ${data.total} 张图片...`)

      // Start polling for progress
      pollBatchProgress(data.task_id)
    } catch (e: any) {
      setMessage(`失败：${String(e)}`)
      setLoading(false)
      setIsBatchMode(false)
    }
  }

  const pollBatchProgress = async (taskId: string) => {
    const poll = async () => {
      try {
        const data = await api(`/wordlists/batch_status/${taskId}`)
        setBatchProgress(data)

        if (data.status === 'completed') {
          setBatchResults(data.results)
          setLoading(false)
          const successCount = data.results.filter((r: BatchImageResult) => r.status === 'success').length
          const totalWords = data.results.reduce((sum: number, r: BatchImageResult) => sum + r.count, 0)
          setMessage(`处理完成！成功 ${successCount}/${data.total} 张图片，共提取 ${totalWords} 个单词`)
          // Flatten all words for bulk review
          const allWords: PreviewWord[] = []
          data.results.forEach((result: BatchImageResult) => {
            if (result.status === 'success') {
              allWords.push(...result.words)
            }
          })
          setPreviewWords(allWords)
        } else {
          // Continue polling
          setTimeout(() => poll(), 1000)
        }
      } catch (e: any) {
        setMessage(`查询进度失败：${String(e)}`)
        setLoading(false)
        setIsBatchMode(false)
      }
    }
    poll()
  }

  const previewFromFile = async () => {
    if (!listId || !file) return
    setLoading(true)
    setMessage('')
    try {
      const fd = new FormData()
      fd.set('file', file)
      const res = await fetch(`${API_BASE}/wordlists/${listId}/preview_upload`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setPreviewWords(data)
      setIsPreviewMode(true)
      setMessage(`解析到 ${data.length} 个单词，请确认`)
    } catch (e: any) {
      setMessage(`失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const savePreviewedWords = async () => {
    if (!listId) {
      // For image mode, create wordlist first
      try {
        const fd = new FormData()
        fd.set('name', name)
        const res = await fetch(`${API_BASE}/wordlists`, {
          method: 'POST',
          body: fd,
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
        })
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setListId(data.id)
        await saveWordsToList(data.id)
      } catch (e: any) {
        setMessage(`创建词库失败：${String(e)}`)
      }
    } else {
      await saveWordsToList(listId)
    }
  }

  const saveWordsToList = async (targetListId: number) => {
    setLoading(true)
    try {
      const data = await api(`/wordlists/${targetListId}/save_words`, {
        method: 'POST',
        body: JSON.stringify(previewWords)
      })
      setMessage(data.message || `成功保存 ${data.count} 个单词`)
      setIsPreviewMode(false)
      setPreviewWords([])
      loadWordlists()
    } catch (e: any) {
      setMessage(`保存失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const removePreviewWord = (index: number) => {
    setPreviewWords(prev => prev.filter((_, i) => i !== index))
  }

  const addNewWord = () => {
    if (!newTerm.trim()) return
    setPreviewWords(prev => [...prev, {
      term: newTerm.trim(),
      definition: newDefinition.trim() || null,
      example: newExample.trim() || null
    }])
    setNewTerm('')
    setNewDefinition('')
    setNewExample('')
  }

  const cancelPreview = () => {
    setIsPreviewMode(false)
    setPreviewWords([])
    setMessage('')
  }

  // Load wordlists on mount
  useEffect(() => {
    loadWordlists()
  }, [])

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

    // Check if multiple image files
    const imageFiles: File[] = []
    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      if (f.type && f.type.startsWith('image/')) {
        imageFiles.push(f)
      }
    }

    if (imageFiles.length > 1) {
      setImgFiles(imageFiles)
      setMessage(`已选择 ${imageFiles.length} 张图片（拖拽）`)
    } else if (imageFiles.length === 1) {
      setImgFile(imageFiles[0])
      setMessage('已选择图片（拖拽）')
    }
    setDragOver(false)
  }
  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); if (!dragOver) setDragOver(true) }
  const onDragEnter = (e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => { if (e.currentTarget === e.target) setDragOver(false) }

  const handleMultipleImages = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const imageFiles: File[] = []
    for (let i = 0; i < files.length; i++) {
      if (files[i].type.startsWith('image/')) {
        imageFiles.push(files[i])
      }
    }
    setImgFiles(imageFiles)
    setMessage(`已选择 ${imageFiles.length} 张图片`)
  }

  const removeImage = (index: number) => {
    setImgFiles(prev => prev.filter((_, i) => i !== index))
  }

  const saveBatchResults = async () => {
    if (!listId) {
      // Create wordlist first
      try {
        const fd = new FormData()
        fd.set('name', name)
        const res = await fetch(`${API_BASE}/wordlists`, {
          method: 'POST',
          body: fd,
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
        })
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setListId(data.id)
        await saveWordsToList(data.id)
      } catch (e: any) {
        setMessage(`创建词库失败：${String(e)}`)
      }
    } else {
      await saveWordsToList(listId)
    }
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

      {/* 预览模式 */}
      {isPreviewMode ? (
        <div className="stack">
          <h4>预览单词 (共 {previewWords.length} 个)</h4>
          <div className="card scroll surface-subtle" style={{ maxHeight: '400px', padding: '12px' }}>
            {previewWords.length === 0 ? (
              <div className="muted">没有单词</div>
            ) : (
              <div className="stack">
                {previewWords.map((word, idx) => (
                  <div key={idx} style={{ padding: '8px', borderBottom: idx < previewWords.length - 1 ? '1px solid #eee' : 'none', display: 'flex', gap: '8px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600 }}>{word.term}</div>
                      {word.definition && <div className="muted">释义: {word.definition}</div>}
                      {word.example && <div className="muted" style={{ fontSize: '13px' }}>例句: {word.example}</div>}
                    </div>
                    <button className="btn btn-sm" onClick={() => removePreviewWord(idx)} style={{ alignSelf: 'flex-start' }}>删除</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 添加新单词 */}
          <div className="card surface-subtle" style={{ padding: '12px' }}>
            <h5 style={{ margin: '0 0 8px 0' }}>添加新单词</h5>
            <div className="stack">
              <input className="input" placeholder="单词 *" value={newTerm} onChange={e => setNewTerm(e.target.value)} />
              <input className="input" placeholder="释义" value={newDefinition} onChange={e => setNewDefinition(e.target.value)} />
              <input className="input" placeholder="例句" value={newExample} onChange={e => setNewExample(e.target.value)} />
              <button className="btn btn-sm" onClick={addNewWord} disabled={!newTerm.trim()}>添加</button>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="row">
            <button className="btn btn-outline" onClick={cancelPreview}>取消</button>
            <button className="btn btn-primary" onClick={savePreviewedWords} disabled={loading || previewWords.length === 0}>
              {loading ? '保存中...' : '确认保存'}
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* 查看词库按钮 */}
          <div className="row">
            <button className="btn btn-outline" onClick={() => setShowList(!showList)}>
              {showList ? '隐藏词库列表' : '查看我的词库'}
            </button>
          </div>

          {/* 词库列表 */}
          {showList && (
          <div className="card stack surface-subtle" style={{ padding: '12px' }}>
              <h4 style={{ margin: '0 0 8px 0' }}>我的词库</h4>
              {wordlists.length === 0 ? (
                <div className="muted">暂无词库</div>
              ) : (
                <div className="list">
                  {wordlists.map((wl: any) => (
                    <div key={wl.id} style={{ marginBottom: '8px' }}>
                      <div className="list-item" style={{ cursor: 'pointer' }}>
                        <div style={{ flex: 1 }}>
                          <strong>{wl.name}</strong> (ID: {wl.id})
                          {wl.description && <span className="muted"> - {wl.description}</span>}
                        </div>
                        <button
                          className="btn btn-sm"
                          onClick={() => toggleWordList(wl.id)}
                          style={{ marginLeft: '8px' }}
                        >
                          {expandedListId === wl.id ? '收起' : '查看单词'}
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteWordlist(wl.id, wl.name)
                          }}
                          style={{ marginLeft: '8px' }}
                          disabled={loading}
                        >
                          删除
                        </button>
                      </div>

                      {/* 单词列表 */}
                      {expandedListId === wl.id && (
                        <div className="card surface-subtle" style={{ marginTop: '8px', padding: '12px' }}>
                          {!words[wl.id] ? (
                            <div className="muted">加载中...</div>
                          ) : words[wl.id].length === 0 ? (
                            <div className="muted">该词库暂无单词</div>
                          ) : (
                            <div className="stack">
                              <div style={{ fontWeight: 600, marginBottom: '8px' }}>
                                共 {words[wl.id].length} 个单词
                              </div>
                              {words[wl.id].map((word: any, idx: number) => (
                                <div key={word.id} style={{
                                  padding: '8px',
                                  borderBottom: idx < words[wl.id].length - 1 ? '1px solid #eee' : 'none'
                                }}>
                                  <div style={{ marginBottom: '4px' }}>
                                    <span style={{ fontWeight: 600, fontSize: '16px' }}>{word.term}</span>
                                  </div>
                                  {word.definition && (
                                    <div style={{ marginBottom: '4px', color: '#555' }}>
                                      释义: {word.definition}
                                    </div>
                                  )}
                                  {word.example && (
                                    <div className="muted" style={{ fontSize: '14px' }}>
                                      例句: {word.example}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="row">
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="词库名称" />
            <button className="btn btn-primary" onClick={createList}>创建词库</button>
            {listId && <span className="badge">已创建: {listId}</span>}
          </div>
          {/* 选择已有词库作为导入目标 */}
          <div className="row">
            <select
              className="input"
              value={listId ?? ''}
              onChange={e => {
                const v = e.target.value
                setListId(v ? Number(v) : null)
              }}
            >
              <option value="">选择已有词库作为导入目标</option>
              {wordlists.map((wl: any) => (
                <option key={wl.id} value={wl.id}>{wl.name} (ID: {wl.id})</option>
              ))}
            </select>
            <button className="btn" onClick={() => setShowList(s => !s)}>{showList ? '收起列表' : '查看我的词库'}</button>
            {listId && <span className="badge">目标: {listId}</span>}
          </div>
          <div className="row">
            <button className={`btn btn-sm ${mode === 'file' ? 'btn-primary' : ''}`} onClick={() => setMode('file')}>CSV/JSON 导入</button>
            <button className={`btn btn-sm ${mode === 'image' ? 'btn-primary' : ''}`} onClick={() => setMode('image')}>图片建库（LLM）</button>
          </div>

          {mode === 'file' && (
            <div className="row">
              <input className="file" type="file" accept=".csv,.json" onChange={e => setFile(e.target.files?.[0] || null)} />
              <button className="btn" onClick={previewFromFile} disabled={!listId || !file}>预览</button>
            </div>
          )}

          {mode === 'image' && (
            <>
              {/* Single Image Mode */}
              <div className="row">
                <input className="file" type="file" accept="image/*" onChange={e => setImgFile(e.target.files?.[0] || null)} />
                <button className="btn" onClick={createFromImage} disabled={!imgFile || loading}>
                  {loading ? (<><span className="spinner" /> 正在识别…</>) : '识别单张'}
                </button>
              </div>

              {/* Batch Image Mode */}
              <div className="row">
                <input
                  className="file"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={e => handleMultipleImages(e.target.files)}
                />
                <button className="btn btn-primary" onClick={createFromBatchImages} disabled={imgFiles.length === 0 || loading}>
                  {loading ? (<><span className="spinner" /> 正在处理…</>) : `批量识别 (${imgFiles.length} 张)`}
                </button>
              </div>

              {/* Image Queue Display */}
              {imgFiles.length > 0 && (
                <div className="card surface-subtle" style={{ padding: '12px' }}>
                  <h5 style={{ margin: '0 0 8px 0' }}>待处理图片 ({imgFiles.length})</h5>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: '8px', maxHeight: '200px', overflow: 'auto' }}>
                    {imgFiles.map((file, idx) => (
                      <div key={idx} className="surface-subtle" style={{ position: 'relative', border: '1px solid var(--border)', borderRadius: '8px', padding: '4px' }}>
                        <img
                          src={URL.createObjectURL(file)}
                          alt={file.name}
                          style={{ width: '100%', height: '80px', objectFit: 'cover', borderRadius: '4px' }}
                        />
                        <button
                          className="btn btn-sm"
                          onClick={() => removeImage(idx)}
                          style={{ position: 'absolute', top: '4px', right: '4px', fontSize: '10px', padding: '2px 6px' }}
                        >
                          ×
                        </button>
                        <div style={{ fontSize: '10px', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {file.name}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Progress Display */}
              {batchProgress && (
                <div className="card surface-subtle" style={{ padding: '12px' }}>
                  <h5 style={{ margin: '0 0 8px 0' }}>处理进度</h5>
                  <div className="progress" style={{ marginBottom: '8px', height: '16px' }}>
                    <div
                      className="progress-bar"
                      style={{ width: `${(batchProgress.completed / batchProgress.total) * 100}%` }}
                    >
                      {batchProgress.completed}/{batchProgress.total}
                    </div>
                  </div>
                  <div className="muted" style={{ fontSize: '13px' }}>
                    {batchProgress.current_image && `当前: ${batchProgress.current_image}`}
                    {batchProgress.errors > 0 && ` (失败: ${batchProgress.errors})`}
                  </div>
                </div>
              )}

              {/* Batch Results Display */}
              {isBatchMode && batchResults.length > 0 && !isPreviewMode && (
                <div className="card surface-subtle" style={{ padding: '12px' }}>
                  <h5 style={{ margin: '0 0 8px 0' }}>提取结果 (共 {previewWords.length} 个单词)</h5>
                  <div className="stack">
                    {batchResults.map((result, idx) => (
                      <div key={idx} style={{ padding: '8px', background: result.status === 'success' ? '#f0f8f0' : '#fff0f0', borderRadius: '4px' }}>
                        <div
                          style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                          onClick={() => setExpandedImage(expandedImage === idx ? null : idx)}
                        >
                          <div style={{ flex: 1 }}>
                            <strong>{result.filename}</strong>
                            {result.status === 'success' ? (
                              <span className="muted"> - {result.count} 个单词</span>
                            ) : (
                              <span style={{ color: 'red' }}> - 失败: {result.error}</span>
                            )}
                          </div>
                          <button className="btn btn-sm">
                            {expandedImage === idx ? '收起' : '查看'}
                          </button>
                        </div>

                        {expandedImage === idx && result.status === 'success' && (
                          <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #ddd' }}>
                            {result.words.map((word, widx) => (
                              <div key={widx} style={{ padding: '4px', borderBottom: widx < result.words.length - 1 ? '1px solid #eee' : 'none' }}>
                                <div style={{ fontWeight: 600 }}>{word.term}</div>
                                {word.definition && <div className="muted">释义: {word.definition}</div>}
                                {word.example && <div className="muted" style={{ fontSize: '12px' }}>例句: {word.example}</div>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="row" style={{ marginTop: '12px' }}>
                    <button className="btn btn-outline" onClick={() => { setIsBatchMode(false); setBatchResults([]); setBatchProgress(null); }}>
                      取消
                    </button>
                    <button className="btn btn-primary" onClick={() => setIsPreviewMode(true)} disabled={previewWords.length === 0}>
                      确认并编辑所有单词
                    </button>
                  </div>
                </div>
              )}

              {/* Single Image Dropzone (when not in batch mode) */}
              {!isBatchMode && imgFiles.length === 0 && (
                <div
                  ref={dropRef}
                  className={`dropzone ${dragOver ? 'is-dragover' : ''}`}
                  onPaste={onPaste}
                  onDrop={onDrop}
                  onDragOver={onDragOver}
                  onDragEnter={onDragEnter}
                  onDragLeave={onDragLeave}
                  tabIndex={0}
                >
                  {previewUrl ? (
                    <div className="stack" style={{ alignItems: 'center' }}>
                      <img className="preview" src={previewUrl} alt="预览" />
                      <div className="muted">已准备：{imgFile?.name || '粘贴的图片'}（{imgFile ? Math.round(imgFile.size / 1024) : 0} KB）</div>
                      <div className="muted">按 Ctrl/⌘+V 替换，或拖拽进来。支持拖拽多张图片批量处理</div>
                    </div>
                  ) : (
                    <div className="stack" style={{ alignItems: 'center' }}>
                      <div>将图片粘贴到此处（Ctrl/⌘+V）</div>
                      <div className="muted">或拖拽图片到此处。支持拖拽多张图片批量处理</div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {message && (
            <div className={`alert ${message.startsWith('失败') ? 'alert-error' : 'alert-success'}`}>{message}</div>
          )}
        </>
      )}
    </div>
  )
}

function StartSession() {
  const [wordlistId, setWordlistId] = useState('')
  const [friend, setFriend] = useState('')
  const [ratio, setRatio] = useState(50) // zh->en percentage when random
  const [practiceRatio, setPracticeRatio] = useState(100) // percentage of words to include
  const [sessionId, setSessionId] = useState<number | null>(() => {
    const saved = localStorage.getItem('activeSessionId')
    const n = saved ? Number(saved) : null
    return n != null && !isNaN(n) ? n : null
  })
  const [joinId, setJoinId] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [wordlists, setWordlists] = useState<any[]>([])
  const [listsLoading, setListsLoading] = useState(false)
  const [mySessions, setMySessions] = useState<any[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [includeParticipating, setIncludeParticipating] = useState(false)

  const loadWordlists = async () => {
    setListsLoading(true)
    try {
      const data = await api('/wordlists')
      setWordlists(data)
    } catch (e: any) {
      setMessage(`加载词库失败：${String(e)}`)
    } finally {
      setListsLoading(false)
    }
  }

  useEffect(() => { loadWordlists() }, [])
  const loadMySessions = async () => {
    setSessionsLoading(true)
    try {
      const qs = includeParticipating ? '/sessions?created_by_me=true&participating=true' : '/sessions?created_by_me=true'
      const data = await api(qs)
      setMySessions(data || [])
    } catch (e: any) {
      setMessage(`加载我的会话失败：${String(e)}`)
    } finally {
      setSessionsLoading(false)
    }
  }
  useEffect(() => { loadMySessions() }, [includeParticipating])

  // Persist/restore current session id
  useEffect(() => {
    if (sessionId != null) localStorage.setItem('activeSessionId', String(sessionId))
    else localStorage.removeItem('activeSessionId')
  }, [sessionId])
  useEffect(() => {
    // Validate saved session on first mount
    const saved = localStorage.getItem('activeSessionId')
    if (saved) {
      const n = Number(saved)
      if (!isNaN(n)) {
        api(`/sessions/${n}`).catch(() => {
          localStorage.removeItem('activeSessionId')
          setSessionId(null)
          setMessage('原有 Session 已失效或无访问权限')
        })
      }
    }
  }, [])

  const create = async () => {
    setMessage('')
    setLoading(true)
    try {
      const data = await api(`/sessions?wordlist_id=${encodeURIComponent(wordlistId)}&friend_username=${encodeURIComponent(friend)}&zh2en_ratio=${encodeURIComponent(String(ratio))}&practice_ratio=${encodeURIComponent(String(practiceRatio))}`,
        { method: 'POST' })
      setSessionId(data.id)
      const poolInfo = (data.practice_pool_size != null) ? `，题量占比 ${data.practice_ratio ?? practiceRatio}%（预计 ${data.practice_pool_size} 题）` : ''
      setMessage(`已创建异步打卡（中→英占比 ${data.zh2en_ratio ?? ratio}%${poolInfo}），邀请对方加入此 Session ID：${data.id}`)
      try { await loadMySessions() } catch {}
    } catch (e: any) {
      setMessage(`创建失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }
  const join = async () => {
    const idNum = Number(joinId)
    if (!idNum || isNaN(idNum)) { setMessage('请输入正确的 Session ID'); return }
    setMessage('')
    setLoading(true)
    try {
      // Probe detail to validate permission and status before entering
      const detail = await api(`/sessions/${idNum}`)
      if (detail?.status === 'archived') {
        setMessage('此会话已归档，无法加入')
        return
      }
      setSessionId(idNum)
      setMessage(`已加入 Session #${idNum}`)
    } catch (e: any) {
      setMessage(`加入失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }
  const copyId = async () => {
    if (!sessionId) return
    try {
      await navigator.clipboard.writeText(String(sessionId))
      setMessage('已复制 Session ID 到剪贴板')
    } catch {
      setMessage('复制失败，请手动复制 Session ID')
    }
  }
  const leave = () => {
    setSessionId(null)
    localStorage.removeItem('activeSessionId')
    setMessage('已退出当前 Session')
  }

  return (
    <div className="card stack">
      <h3 className="card-title">创建异步打卡</h3>
      <div className="row">
        <select
          className="input"
          value={wordlistId}
          onChange={e => setWordlistId(e.target.value)}
          disabled={listsLoading}
        >
          <option value="" disabled>{listsLoading ? '加载词库中…' : '选择词库'}</option>
          {wordlists.map((wl: any) => (
            <option key={wl.id} value={String(wl.id)}>
              {wl.name}（ID: {wl.id}）
            </option>
          ))}
        </select>
        <input className="input" placeholder="好友用户名" value={friend} onChange={e => setFriend(e.target.value)} />
        <div className="stack" style={{ minWidth: 220 }}>
          <label className="muted" htmlFor="ratio">中→英占比：{ratio}%</label>
          <input id="ratio" type="range" min={0} max={100} value={ratio}
                 onChange={e => setRatio(Number(e.target.value))} />
        </div>
        <div className="stack" style={{ minWidth: 260 }}>
          <label className="muted" htmlFor="practiceRatio">题量占比（抽取词库的一部分进行练习）：{practiceRatio}%</label>
          <input id="practiceRatio" type="range" min={1} max={100} value={practiceRatio}
                 onChange={e => setPracticeRatio(Number(e.target.value))} />
        </div>
        <button className="btn btn-primary" onClick={create} disabled={loading || !wordlistId}>
          {loading ? '创建中…' : '创建'}
        </button>
        {sessionId && (
          <>
            <span className="badge">Session #{sessionId}</span>
            <button className="btn" onClick={copyId}><i className="ri-file-copy-line" style={{ marginRight: 6 }} />复制ID</button>
            <button className="btn" onClick={leave}><i className="ri-close-circle-line" style={{ marginRight: 6 }} />退出会话</button>
          </>
        )}
      </div>
      <div className="row">
        <input className="input" placeholder="已有 Session ID，输入加入" value={joinId} onChange={e => setJoinId(e.target.value)} />
        <button className="btn" onClick={join} disabled={loading}>加入</button>
      </div>
      {message && <div className={`alert ${message.startsWith('创建失败') || message.startsWith('加入失败') ? 'alert-error' : 'alert-success'}`}>{message}</div>}
      {sessionId && <Quiz sessionId={sessionId} />}
      {!sessionId && (
        <div className="card surface-subtle" style={{ padding: 12 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h4 className="section-title" style={{ margin: 0 }}><i className="ri-folder-3-line" style={{ marginRight: 6 }} />我的会话</h4>
            <label className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={includeParticipating} onChange={e => setIncludeParticipating(e.target.checked)} />
              <span className="muted">包含我参与的</span>
            </label>
          </div>
          {sessionsLoading ? (
            <div className="muted">加载中…</div>
          ) : mySessions.length === 0 ? (
            <div className="muted">暂无会话</div>
          ) : (
            <div className="list">
              {mySessions.map((s: any) => (
                <div key={s.id} className="list-item">
                  <div style={{ display: 'grid' }}>
                    <div style={{ fontWeight: 600 }}>Session #{s.id} · {s.wordlist?.name || '—'}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {(s.participants || []).map((p: any) => p.username).join(' vs ')} · {s.created_at ? new Date(s.created_at).toLocaleString() : ''} · {s.status}
                    </div>
                  </div>
                  <div className="row">
                    {s.last_activity && <span className="badge">最近活动：{new Date(s.last_activity).toLocaleString()}</span>}
                    <button className="btn btn-sm" onClick={() => s.status !== 'archived' && setSessionId(s.id)} disabled={s.status === 'archived'}>
                      <i className="ri-arrow-right-circle-line" style={{ marginRight: 4 }} />{s.status === 'archived' ? '已归档' : '进入'}
                    </button>
                    {s.status !== 'archived' ? (
                      <button className="btn btn-sm" onClick={async () => { try { await api(`/sessions/${s.id}/status?status=archived`, { method: 'POST' }); await loadMySessions() } catch (e: any) { setMessage(`归档失败：${String(e)}`) } }}>
                        <i className="ri-inbox-archive-line" style={{ marginRight: 4 }} />归档
                      </button>
                    ) : (
                      <button className="btn btn-sm" onClick={async () => { try { await api(`/sessions/${s.id}/status?status=active`, { method: 'POST' }); await loadMySessions() } catch (e: any) { setMessage(`恢复失败：${String(e)}`) } }}>
                        <i className="ri-inbox-unarchive-line" style={{ marginRight: 4 }} />恢复
                      </button>
                    )}
                    {s.created_by_me && (
                      <button className="btn btn-sm btn-danger" onClick={async () => {
                        if (!confirm(`确定删除 Session #${s.id} 吗？此操作不可恢复`)) return
                        try { await api(`/sessions/${s.id}`, { method: 'DELETE' }); await loadMySessions() } catch (e: any) { setMessage(`删除失败：${String(e)}`) }
                      }}>
                        <i className="ri-delete-bin-6-line" style={{ marginRight: 4 }} />删除
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
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
  const [mode, setMode] = useState<'random' | 'zh2en' | 'en2zh'>(() => {
    try {
      const key = `quizMode_${sessionId}`
      const saved = localStorage.getItem(key)
      if (saved === 'random' || saved === 'zh2en' || saved === 'en2zh') return saved
    } catch {}
    return 'random'
  })
  // Track questions already answered in this run
  const seenRef = useRef<Set<number>>(new Set())
  const [finished, setFinished] = useState(false)

  // Persist mode per session and reload when session changes
  useEffect(() => {
    try { localStorage.setItem(`quizMode_${sessionId}`, mode) } catch {}
  }, [mode, sessionId])
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`quizMode_${sessionId}`)
      if (saved === 'random' || saved === 'zh2en' || saved === 'en2zh') setMode(saved)
      else setMode('random')
    } catch { setMode('random') }
  }, [sessionId])

  const loadNext = async () => {
    setAnswer('')
    setResult(null)
    setFinished(false)
    const dirParam = mode === 'random' ? '' : `?direction=${mode}`
    let picked: any = null
    // Try multiple times to avoid repeating answered questions
    for (let i = 0; i < 20; i++) {
      const cand = await api(`/sessions/${sessionId}/next_word${dirParam}`)
      if (!cand || typeof cand.word_id !== 'number') { picked = cand; break }
      if (!seenRef.current.has(cand.word_id)) { picked = cand; break }
    }
    if (!picked || typeof picked.word_id !== 'number' || seenRef.current.has(picked.word_id)) {
      // Likely exhausted all items this round
      setWord(null)
      setFinished(true)
      refresh()
      return
    }
    setWord(picked)
    refresh()
  }
  const submit = async () => {
    const r = await api(`/sessions/${sessionId}/attempts?word_id=${word.word_id}&answer=${encodeURIComponent(answer)}&direction=${encodeURIComponent(word.direction || 'zh2en')}`, { method: 'POST' })
    setResult(r)
    // Mark this word as answered for this run (no repeat)
    try { if (word?.word_id) seenRef.current.add(Number(word.word_id)) } catch {}
    refresh()
    // Auto-advance on correct answer after a short pause
    if (r?.correct) {
      setTimeout(() => {
        loadNext()
      }, 800)
    }
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
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">方向：</span>
        <button className={`btn btn-sm ${mode === 'random' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('random')}>随机</button>
        <button className={`btn btn-sm ${mode === 'zh2en' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('zh2en')}>中 → 英</button>
        <button className={`btn btn-sm ${mode === 'en2zh' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('en2zh')}>英 → 中</button>
        <button className="btn btn-sm" onClick={loadNext}>换题</button>
      </div>
      {!finished && word && (
        <div className="card stack">
          {word.direction === 'en2zh' ? (
            <>
              <div className="muted">单词</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{word.term}</div>
            </>
          ) : (
            <>
              <div className="muted">释义</div>
              <div>{word.definition || '—'}</div>
            </>
          )}
          <div className="row">
            <input
              className="input"
              placeholder={word.direction === 'en2zh' ? '请输入中文释义' : '请输入英文单词'}
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  if (result) loadNext()
                  else submit()
                }
              }}
            />
            <button className="btn btn-primary" onClick={submit}>提交</button>
            <button className="btn" onClick={loadNext}>换一个</button>
          </div>
        </div>
      )}
      {finished && (
        <div className="alert alert-success">
          本轮题目已完成，已作答的题不会再次出现。
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-sm" onClick={() => { seenRef.current.clear(); setFinished(false); loadNext() }}>重新开始本轮</button>
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
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const add = async () => {
    const u = username.trim()
    if (!u) { setMessage('请输入好友用户名'); return }
    setLoading(true)
    setMessage('')
    try {
      const res = await api(`/friends/add?username=${encodeURIComponent(u)}`, { method: 'POST' })
      setMessage(res?.message || '添加成功')
      setUsername('')
      await refresh()
    } catch (e: any) {
      setMessage(`添加失败：${String(e)}`)
    } finally {
      setLoading(false)
    }
  }
  const refresh = async () => { const r = await api('/friends'); setList(r) }
  useEffect(() => { refresh() }, [])
  return (
    <div className="card stack">
      <h3 className="card-title">好友</h3>
      <div className="row">
        <input className="input" value={username} onChange={e => setUsername(e.target.value)} placeholder="用户名" />
        <button className="btn" onClick={add} disabled={loading}>{loading ? '添加中…' : '添加好友'}</button>
      </div>
      {message && <div className={`alert ${message.startsWith('添加失败') ? 'alert-error' : 'alert-success'}`}>{message}</div>}
      <ul>
        {list.map(f => <li key={f.id}>{f.username}</li>)}
      </ul>
    </div>
  )
}

export default function App() {
  const { token, setToken } = useToken()
  const [me, setMe] = useState<any>(null)
  type Tab = 'upload'|'session'|'leaderboard'|'report'|'friends'
  const validTabs = new Set<Tab>(['upload','session','leaderboard','report','friends'])
  const getInitialTab = (): Tab => {
    const fromHash = (location.hash || '').replace(/^#/, '') as Tab
    if (validTabs.has(fromHash)) return fromHash
    const saved = localStorage.getItem('activeTab') as Tab | null
    if (saved && validTabs.has(saved)) return saved
    return 'upload'
  }
  const [tab, setTab] = useState<Tab>(getInitialTab)

  // Persist tab to URL hash and localStorage; react to back/forward
  useEffect(() => {
    const newHash = `#${tab}`
    if (location.hash !== newHash) {
      history.replaceState(null, '', newHash)
    }
    localStorage.setItem('activeTab', tab)
  }, [tab])
  useEffect(() => {
    const onHash = () => {
      const h = (location.hash || '').replace(/^#/, '') as Tab
      if (validTabs.has(h) && h !== tab) setTab(h)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [tab])

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
            <button className={`btn btn-sm tab ${tab === 'upload' ? 'active' : ''}`} onClick={() => setTab('upload')}><i className="ri-upload-2-line" style={{ marginRight: 6 }} />上传词库</button>
            <button className={`btn btn-sm tab ${tab === 'session' ? 'active' : ''}`} onClick={() => setTab('session')}><i className="ri-timer-line" style={{ marginRight: 6 }} />开始打卡</button>
            <button className={`btn btn-sm tab ${tab === 'friends' ? 'active' : ''}`} onClick={() => setTab('friends')}><i className="ri-user-heart-line" style={{ marginRight: 6 }} />好友</button>
            <button className={`btn btn-sm tab ${tab === 'leaderboard' ? 'active' : ''}`} onClick={() => setTab('leaderboard')}><i className="ri-bar-chart-2-line" style={{ marginRight: 6 }} />排行榜</button>
            <button className={`btn btn-sm tab ${tab === 'report' ? 'active' : ''}`} onClick={() => setTab('report')}><i className="ri-file-chart-line" style={{ marginRight: 6 }} />学习报告</button>
          </nav>
          <div className="row">
            <span className="muted">Hi, {me.username}</span>
            <button className="btn btn-outline" onClick={() => { localStorage.removeItem('token'); location.reload() }}><i className="ri-logout-box-r-line" style={{ marginRight: 6 }} />退出</button>
          </div>
        </div>
      </header>
      <main className="container grid">
        {tab === 'upload' && <Upload />}
        {tab === 'session' && <StartSession />}
        {tab === 'leaderboard' && <Leaderboard />}
        {tab === 'report' && <WeeklyReport />}
        {tab === 'friends' && <Friends />}
      </main>
    </>
  )
}
