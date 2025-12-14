import React from 'react'

interface WordlistItem {
  id: number
  name: string
  description?: string
}

interface WordlistProps {
  wordlists: WordlistItem[]
  expandedListId: number | null
  words: { [listId: number]: any[] }
  loading?: boolean
  onToggleWordList: (id: number) => void
  onDeleteWordlist: (id: number, name: string) => void
}

export default function Wordlist({ wordlists, expandedListId, words, loading, onToggleWordList, onDeleteWordlist }: WordlistProps) {
  if (!wordlists || wordlists.length === 0) return <div className="muted">暂无词库</div>

  return (
    <div className="list">
      {wordlists.map((wl) => (
        <div key={wl.id}>
          <div className="list-item" style={{ cursor: 'pointer' }}>
            <div style={{ flex: 1 }}>
              <strong>{wl.name}</strong> (ID: {wl.id})
              {wl.description && <span className="muted"> - {wl.description}</span>}
            </div>
            <button className="btn btn-sm" onClick={() => onToggleWordList(wl.id)}>
              {expandedListId === wl.id ? (<><i className="ri-arrow-up-s-line" style={{ marginRight: 4 }} />收起</>) : (<><i className="ri-list-check-2" style={{ marginRight: 4 }} />查看单词</>)}
            </button>
            <button className="btn btn-sm btn-danger" onClick={(e) => { e.stopPropagation(); onDeleteWordlist(wl.id, wl.name) }} disabled={loading}>
              <i className="ri-delete-bin-6-line" style={{ marginRight: 4 }} />删除
            </button>
          </div>

          {expandedListId === wl.id && (
            <div className="card surface-subtle" style={{ marginTop: 8, padding: 12 }}>
              {!words[wl.id] ? (
                <div className="muted">加载中...</div>
              ) : words[wl.id].length === 0 ? (
                <div className="muted">该词库暂无单词</div>
              ) : (
                <div className="stack">
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>
                    共 {words[wl.id].length} 个单词
                  </div>
                  {words[wl.id].map((word: any, idx: number) => (
                    <div key={word.id} style={{ padding: 8, borderBottom: idx < words[wl.id].length - 1 ? '1px solid #eee' : 'none' }}>
                      <div style={{ marginBottom: 4 }}>
                        <span style={{ fontWeight: 600, fontSize: 16 }}>{word.term}</span>
                      </div>
                      {word.definition && (
                        <div style={{ marginBottom: 4 }} className="muted">
                          释义: {word.definition}
                        </div>
                      )}
                      {word.example && (
                        <div className="muted" style={{ fontSize: 14 }}>
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
  )
}
