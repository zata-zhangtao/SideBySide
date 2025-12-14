import React, { useEffect, useState } from 'react'
import { api, API_BASE } from '../api'
import Wordlist from './Wordlist'

export default function MyWordlists() {
  const [wordlists, setWordlists] = useState<any[]>([])
  const [words, setWords] = useState<{ [listId: number]: any[] }>({})
  const [expandedListId, setExpandedListId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [listsLoading, setListsLoading] = useState(false)
  const [message, setMessage] = useState('')

  const loadWordlists = async () => {
    setListsLoading(true)
    try {
      const data = await api('/wordlists')
      setWordlists(data || [])
    } catch (e: any) {
      setMessage(`加载词库失败：${String(e)}`)
    } finally {
      setListsLoading(false)
    }
  }
  const loadWords = async (listId: number) => {
    try {
      const data = await api(`/wordlists/${listId}/words`)
      setWords(prev => ({ ...prev, [listId]: data }))
    } catch (e: any) {
      setMessage(`加载单词失败：${String(e)}`)
    }
  }
  const toggleWordList = (listId: number) => {
    if (expandedListId === listId) setExpandedListId(null)
    else {
      setExpandedListId(listId)
      if (!words[listId]) loadWords(listId)
    }
  }
  const deleteWordlist = async (listId: number, listName: string) => {
    if (!confirm(`确定要删除词库"${listName}"吗？删除后无法恢复。`)) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/wordlists/${listId}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setMessage(data.message || '删除成功')
      setWords(prev => { const nw = { ...prev } as any; delete nw[listId]; return nw })
      if (expandedListId === listId) setExpandedListId(null)
      await loadWordlists()
    } catch (e: any) {
      setMessage(e.message || '删除失败')
    } finally { setLoading(false) }
  }

  useEffect(() => { loadWordlists() }, [])

  return (
    <div className="card stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3 className="card-title" style={{ margin: 0 }}><i className="ri-book-2-line" style={{ marginRight: 6 }} />我的词库</h3>
        <div className="row">
          <button className="btn btn-sm" onClick={loadWordlists}><i className="ri-refresh-line" style={{ marginRight: 4 }} />刷新</button>
          <span className="badge">共 {wordlists.length} 个</span>
        </div>
      </div>
      <div className="card surface-subtle" style={{ padding: 12 }}>
        {listsLoading ? (
          <div className="muted">加载中…</div>
        ) : (
          <Wordlist
            wordlists={wordlists}
            expandedListId={expandedListId}
            words={words}
            loading={loading}
            onToggleWordList={toggleWordList}
            onDeleteWordlist={deleteWordlist}
          />
        )}
      </div>
      {message && <div className={`alert ${message.includes('失败') ? 'alert-error' : 'alert-success'}`}>{message}</div>}
    </div>
  )
}

