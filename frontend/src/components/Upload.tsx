import React, { useEffect, useRef, useState } from 'react'
import { API_BASE, api } from '../api'
import Progress from './Progress'
import Wordlist from './Wordlist'
import { BatchImageResult, BatchProgress, PreviewWord } from '../types'

export default function Upload() {
  const defaultListName = () => {
    const d = new Date()
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }
  const [name, setName] = useState(defaultListName())
  const [listId, setListId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [imgFile, setImgFile] = useState<File | null>(null)
  const [imgFiles, setImgFiles] = useState<File[]>([])
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [mode, setMode] = useState<'file' | 'image'>('image')
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

  const loadWords = async (lid: number) => {
    try {
      const data = await api(`/wordlists/${lid}/words`)
      setWords(prev => ({ ...prev, [lid]: data }))
    } catch (e) {
      setMessage(`加载单词失败：${e}`)
    }
  }

  const toggleWordList = (lid: number) => {
    if (expandedListId === lid) {
      setExpandedListId(null)
    } else {
      setExpandedListId(lid)
      if (!words[lid]) loadWords(lid)
    }
  }

  const createList = async () => {
    const fd = new FormData()
    fd.set('name', name)
    const res = await fetch(`${API_BASE}/wordlists`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    setListId(data.id)
    loadWordlists()
  }

  const deleteWordlist = async (lid: number, listName: string) => {
    if (!confirm(`确定要删除词库"${listName}"吗？删除后无法恢复。`)) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/wordlists/${lid}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setMessage(data.message)
      if (expandedListId === lid) setExpandedListId(null)
      setWords(prev => { const nw = { ...prev }; delete (nw as any)[lid]; return nw })
      loadWordlists()
    } catch (err: any) {
      setMessage(err.message || '删除失败')
    } finally { setLoading(false) }
  }

  const createFromImage = async () => {
    if (!imgFile) return
    setLoading(true)
    setMessage('')
    try {
      const fd = new FormData()
      fd.set('file', imgFile)
      const res = await fetch(`${API_BASE}/wordlists/preview_from_image`, {
        method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setPreviewWords(data)
      setIsPreviewMode(true)
      setMessage(`识别到 ${data.length} 个单词，请确认`)
    } catch (e: any) { setMessage(`失败：${String(e)}`) } finally { setLoading(false) }
  }

  const createFromBatchImages = async () => {
    if (!imgFiles || imgFiles.length === 0) return
    setLoading(true); setMessage(''); setIsBatchMode(true)
    setBatchResults([]); setBatchProgress(null)
    try {
      const fd = new FormData(); imgFiles.forEach(file => fd.append('files', file))
      const res = await fetch(`${API_BASE}/wordlists/batch_preview_from_images`, {
        method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setMessage(`开始处理 ${data.total} 张图片...`)
      pollBatchProgress(data.task_id)
    } catch (e: any) { setMessage(`失败：${String(e)}`); setLoading(false); setIsBatchMode(false) }
  }

  const pollBatchProgress = async (taskId: string) => {
    const poll = async () => {
      try {
        const data = await api(`/wordlists/batch_status/${taskId}`)
        setBatchProgress(data)
        if (data.status === 'completed') {
          setBatchResults(data.results); setLoading(false)
          const successCount = data.results.filter((r: BatchImageResult) => r.status === 'success').length
          const totalWords = data.results.reduce((sum: number, r: BatchImageResult) => sum + r.count, 0)
          setMessage(`处理完成！成功 ${successCount}/${data.total} 张图片，共提取 ${totalWords} 个单词`)
          const allWords: PreviewWord[] = []
          data.results.forEach((result: BatchImageResult) => { if (result.status === 'success') allWords.push(...result.words) })
          setPreviewWords(allWords)
        } else setTimeout(() => poll(), 1000)
      } catch (e: any) { setMessage(`查询进度失败：${String(e)}`); setLoading(false); setIsBatchMode(false) }
    }
    poll()
  }

  const previewFromFile = async () => {
    if (!listId || !file) return
    setLoading(true); setMessage('')
    try {
      const fd = new FormData(); fd.set('file', file)
      const res = await fetch(`${API_BASE}/wordlists/${listId}/preview_upload`, {
        method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setPreviewWords(data); setIsPreviewMode(true)
      setMessage(`解析到 ${data.length} 个单词，请确认`)
    } catch (e: any) { setMessage(`失败：${String(e)}`) } finally { setLoading(false) }
  }

  const savePreviewedWords = async () => {
    if (!listId) {
      try {
        const fd = new FormData(); fd.set('name', name)
        const res = await fetch(`${API_BASE}/wordlists`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json(); setListId(data.id); await saveWordsToList(data.id)
      } catch (e: any) { setMessage(`创建词库失败：${String(e)}`) }
    } else { await saveWordsToList(listId) }
  }

  const saveWordsToList = async (targetListId: number) => {
    setLoading(true)
    try {
      const data = await api(`/wordlists/${targetListId}/save_words`, { method: 'POST', body: JSON.stringify(previewWords) })
      setMessage(data.message || `成功保存 ${data.count} 个单词`)
      setIsPreviewMode(false); setPreviewWords([]); loadWordlists()
    } catch (e: any) { setMessage(`保存失败：${String(e)}`) } finally { setLoading(false) }
  }

  const removePreviewWord = (index: number) => { setPreviewWords(prev => prev.filter((_, i) => i !== index)) }
  const addNewWord = () => {
    if (!newTerm.trim()) return
    setPreviewWords(prev => [...prev, { term: newTerm.trim(), definition: newDefinition.trim() || null, example: newExample.trim() || null }])
    setNewTerm(''); setNewDefinition(''); setNewExample('')
  }
  const cancelPreview = () => { setIsPreviewMode(false); setPreviewWords([]); setMessage('') }

  useEffect(() => { loadWordlists() }, [])
  useEffect(() => {
    if (imgFile) {
      const url = URL.createObjectURL(imgFile); setPreviewUrl(url)
      return () => URL.revokeObjectURL(url)
    } else setPreviewUrl(null)
  }, [imgFile])

  // Paste/Drop handlers (image)
  const dropRef = useRef<HTMLDivElement | null>(null)
  const onPaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    const items = e.clipboardData?.items; if (!items) return
    for (let i = 0; i < items.length; i++) {
      const it = items[i]
      if (it.type && it.type.startsWith('image/')) {
        const f = it.getAsFile(); if (f) { setImgFile(f); e.preventDefault(); setMessage('已从剪贴板粘贴图片'); break }
      }
    }
  }
  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); const files = e.dataTransfer?.files; if (!files || !files.length) return
    const imageFiles: File[] = []
    for (let i = 0; i < files.length; i++) { const f = files[i]; if (f.type && f.type.startsWith('image/')) imageFiles.push(f) }
    if (imageFiles.length > 1) { setImgFiles(imageFiles); setMessage(`已选择 ${imageFiles.length} 张图片（拖拽）`) }
    else if (imageFiles.length === 1) { setImgFile(imageFiles[0]); setMessage('已选择图片（拖拽）') }
    setDragOver(false)
  }
  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); if (!dragOver) setDragOver(true) }
  const onDragEnter = (e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => { if (e.currentTarget === e.target) setDragOver(false) }

  const handleMultipleImages = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const imageFiles: File[] = []
    for (let i = 0; i < files.length; i++) { if (files[i].type.startsWith('image/')) imageFiles.push(files[i]) }
    setImgFiles(imageFiles); setMessage(`已选择 ${imageFiles.length} 张图片`)
  }
  const removeImage = (index: number) => { setImgFiles(prev => prev.filter((_, i) => i !== index)) }
  const saveBatchResults = async () => { if (!listId) { try {
    const fd = new FormData(); fd.set('name', name)
    const res = await fetch(`${API_BASE}/wordlists`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json(); setListId(data.id); await saveWordsToList(data.id)
  } catch (e: any) { setMessage(`创建词库失败：${String(e)}`) } } else { await saveWordsToList(listId) } }

  useEffect(() => { if (mode === 'image') dropRef.current?.focus() }, [mode])

  return (
    <div className="card stack">
      <h3 className="card-title">上传单词库</h3>

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

          <div className="card surface-subtle" style={{ padding: '12px' }}>
            <h5 style={{ margin: '0 0 8px 0' }}>添加新单词</h5>
            <div className="stack">
              <input className="input" placeholder="单词 *" value={newTerm} onChange={e => setNewTerm(e.target.value)} />
              <input className="input" placeholder="释义" value={newDefinition} onChange={e => setNewDefinition(e.target.value)} />
              <input className="input" placeholder="例句" value={newExample} onChange={e => setNewExample(e.target.value)} />
              <button className="btn btn-sm" onClick={addNewWord} disabled={!newTerm.trim()}>添加</button>
            </div>
          </div>

          <div className="row">
            <button className="btn btn-outline" onClick={() => cancelPreview()}>取消</button>
            <button className="btn btn-primary" onClick={savePreviewedWords} disabled={loading || previewWords.length === 0}>
              {loading ? '保存中...' : '确认保存'}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="row">
            <button className="btn btn-outline" onClick={() => setShowList(!showList)}>
              {showList ? '隐藏词库列表' : '查看我的词库'}
            </button>
          </div>

          {showList && (
            <div className="card stack surface-subtle" style={{ padding: '12px' }}>
              <h4 style={{ margin: '0 0 8px 0' }}>我的词库</h4>
              <Wordlist
                wordlists={wordlists}
                expandedListId={expandedListId}
                words={words}
                loading={loading}
                onToggleWordList={toggleWordList}
                onDeleteWordlist={deleteWordlist}
              />
            </div>
          )}

          <div className="row">
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="词库名称" />
            <button className="btn btn-primary" onClick={createList}>创建词库</button>
            {listId && <span className="badge">已创建: {listId}</span>}
          </div>
          <div className="row">
            <select className="input" value={listId ?? ''} onChange={e => { const v = e.target.value; setListId(v ? Number(v) : null) }}>
              <option value="">选择已有词库作为导入目标</option>
              {wordlists.map((wl: any) => (<option key={wl.id} value={wl.id}>{wl.name} (ID: {wl.id})</option>))}
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
              <div className="row">
                <input className="file" type="file" accept="image/*" onChange={e => setImgFile(e.target.files?.[0] || null)} />
                <button className="btn" onClick={createFromImage} disabled={!imgFile || loading}>
                  {loading ? (<><span className="spinner" /> 正在识别…</>) : '识别单张'}
                </button>
              </div>
              <div className="row">
                <input className="file" type="file" accept="image/*" multiple onChange={e => handleMultipleImages(e.target.files)} />
                <button className="btn btn-primary" onClick={createFromBatchImages} disabled={imgFiles.length === 0 || loading}>
                  {loading ? (<><span className="spinner" /> 正在处理…</>) : `批量识别 (${imgFiles.length} 张)`}
                </button>
              </div>
              {imgFiles.length > 0 && (
                <div className="card surface-subtle" style={{ padding: '12px' }}>
                  <h5 style={{ margin: '0 0 8px 0' }}>待处理图片 ({imgFiles.length})</h5>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: '8px', maxHeight: '200px', overflow: 'auto' }}>
                    {imgFiles.map((file, idx) => (
                      <div key={idx} className="surface-subtle" style={{ position: 'relative', border: '1px solid var(--border)', borderRadius: '8px', padding: '4px' }}>
                        <img src={URL.createObjectURL(file)} alt={file.name} style={{ width: '100%', height: '80px', objectFit: 'cover', borderRadius: '4px' }} />
                        <button className="btn btn-sm" onClick={() => removeImage(idx)} style={{ position: 'absolute', top: 4, right: 4, fontSize: 10, padding: '2px 6px' }}>×</button>
                        <div style={{ fontSize: 10, marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {batchProgress && (
                <div className="card surface-subtle" style={{ padding: '12px' }}>
                  <h5 style={{ margin: '0 0 8px 0' }}>处理进度</h5>
                  <Progress current={batchProgress.completed} total={batchProgress.total} />
                  <div className="muted" style={{ fontSize: 13 }}>
                    {batchProgress.current_image && `当前: ${batchProgress.current_image}`}
                    {batchProgress.errors > 0 && ` (失败: ${batchProgress.errors})`}
                  </div>
                </div>
              )}

              {isBatchMode && batchResults.length > 0 && !isPreviewMode && (
                <div className="card surface-subtle" style={{ padding: '12px' }}>
                  <h5 style={{ margin: '0 0 8px 0' }}>提取结果 (共 {previewWords.length} 个单词)</h5>
                  <div className="stack">
                    {batchResults.map((result, idx) => (
                      <div key={idx} style={{ padding: '8px', background: result.status === 'success' ? '#f0f8f0' : '#fff0f0', borderRadius: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={() => setExpandedImage(expandedImage === idx ? null : idx)}>
                          <div style={{ flex: 1 }}>
                            <strong>{result.filename}</strong>
                            {result.status === 'success' ? (
                              <span className="muted"> - {result.count} 个单词</span>
                            ) : (
                              <span style={{ color: 'red' }}> - 失败: {result.error}</span>
                            )}
                          </div>
                          <button className="btn btn-sm">{expandedImage === idx ? (<><i className="ri-arrow-up-s-line" style={{ marginRight: 4 }} />收起</>) : (<><i className="ri-eye-line" style={{ marginRight: 4 }} />查看</>)}</button>
                        </div>
                        {expandedImage === idx && result.status === 'success' && (
                          <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #ddd' }}>
                            {result.words.map((word, widx) => (
                              <div key={widx} style={{ padding: 4, borderBottom: widx < result.words.length - 1 ? '1px solid #eee' : 'none' }}>
                                <div style={{ fontWeight: 600 }}>{word.term}</div>
                                {word.definition && <div className="muted">释义: {word.definition}</div>}
                                {word.example && <div className="muted" style={{ fontSize: 12 }}>例句: {word.example}</div>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="row" style={{ marginTop: 12 }}>
                    <button className="btn btn-outline" onClick={() => { setIsBatchMode(false); setBatchResults([]); setBatchProgress(null) }}>取消</button>
                    <button className="btn btn-primary" onClick={() => setIsPreviewMode(true)} disabled={previewWords.length === 0}>确认并编辑所有单词</button>
                  </div>
                </div>
              )}

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
