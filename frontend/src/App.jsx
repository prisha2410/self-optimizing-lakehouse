import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [tables, setTables] = useState([])
  const [decisions, setDecisions] = useState([])
  const [executedActions, setExecutedActions] = useState([])
  const [queryLog, setQueryLog] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [tablesRes, decisionsRes, executedRes, logRes] = await Promise.all([
        fetch(`${API_BASE}/tables`).then(r => r.json()),
        fetch(`${API_BASE}/agent/decisions`).then(r => r.json()),
        fetch(`${API_BASE}/agent/executed-actions`).then(r => r.json()),
        fetch(`${API_BASE}/query-log`).then(r => r.json()),
      ])
      setTables(tablesRes.tables || [])
      setDecisions(decisionsRes.decisions || [])
      setExecutedActions(executedRes.executed || [])
      setQueryLog(logRes.entries || [])
    } catch (err) {
      console.error('Failed to load data:', err)
    }
    setLoading(false)
  }

  async function handleSearch(e) {
    e.preventDefault()
    if (!searchQuery.trim()) return
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(searchQuery)}&top_k=5`)
    const data = await res.json()
    setSearchResults(data.results || [])
  }

  return (
    <div className="dashboard">
      <header>
        <h1>lakehouse://self-optimizing</h1>
        <span className="subtitle">iceberg · agentic tuning · semantic search</span>
      </header>

      {loading ? (
        <p className="loading">$ loading dashboard...</p>
      ) : (
        <>
          <div className="grid">
            <section className="card full">
              <h2>Lakehouse Tables</h2>
              <table>
                <thead>
                  <tr>
                    <th>Table</th>
                    <th>Partition Spec</th>
                    <th>Files</th>
                  </tr>
                </thead>
                <tbody>
                  {tables.map((t) => (
                    <tr key={t.name}>
                      <td>{t.name}</td>
                      <td className="mono">{t.partition_spec}</td>
                      <td>{t.file_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="card full">
              <h2>Agent Analysis</h2>
              {decisions.length === 0 ? (
                <p className="empty">no analysis run yet</p>
              ) : (
                decisions.map((d, i) => (
                  <div key={i} className="decision">
                    <div className="decision-header">
                      <span className="issue">{d.issue}</span>
                      <span className="action-badge">{d.recommended_action}</span>
                    </div>
                    <p className="evidence"><strong>evidence </strong>{d.evidence}</p>
                    <p className="reasoning"><strong>reasoning </strong>{d.reasoning}</p>
                  </div>
                ))
              )}
            </section>

            <section className="card">
              <h2>Executed Actions</h2>
              {executedActions.length === 0 ? (
                <p className="empty">no actions executed yet</p>
              ) : (
                <ul className="executed-list">
                  {executedActions.map((a, i) => (
                    <li key={i}>
                      <strong>{a.column}</strong> → {a.transform}
                      <div className="issue-addressed">{a.issue_addressed}</div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card">
              <h2>Query Performance</h2>
              <table>
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Files</th>
                    <th>Rows</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {queryLog.map((q, i) => (
                    <tr key={i}>
                      <td>{q.query_name}</td>
                      <td>{q.files_scanned}</td>
                      <td>{q.rows_returned.toLocaleString()}</td>
                      <td>{q.elapsed_seconds}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="card full">
              <h2>Semantic Search</h2>
              <form onSubmit={handleSearch} className="search-form">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="electronics purchases, office furniture..."
                />
                <button type="submit">Search</button>
              </form>
              {searchResults.length > 0 && (
                <ul className="search-results">
                  {searchResults.map((r) => (
                    <li key={r.doc_id}>
                      <span className="similarity">{(r.similarity * 100).toFixed(1)}%</span>
                      <strong>{r.doc_id}</strong> — {r.vendor} ({r.category}) — Rs. {r.total}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <button className="refresh-btn" onClick={loadAll}>refresh</button>
        </>
      )}
    </div>
  )
}

export default App