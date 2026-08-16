import { useEffect, useState } from 'react'

const API = '/api'

function carbonClass(intensity) {
  if (intensity < 450) return 'clean'
  if (intensity < 550) return 'moderate'
  return 'dirty'
}

export default function App() {
  const [grid, setGrid] = useState(null)
  const [stats, setStats] = useState(null)
  const [jobs, setJobs] = useState([])
  const [policy, setPolicy] = useState('greedy')
  const [batchCount, setBatchCount] = useState(5)
  const [submitting, setSubmitting] = useState(false)

  const fetchAll = async (pol = policy) => {
    const [g, s, j] = await Promise.all([
      fetch(`${API}/grid/status`).then((r) => r.json()),
      fetch(`${API}/stats?policy=${pol}`).then((r) => r.json()),
      fetch(`${API}/jobs`).then((r) => r.json()),
    ])
    setGrid(g)
    setStats(s)
    setJobs(j)
  }

  useEffect(() => {
    fetchAll()
    const id = setInterval(() => fetchAll(), 10000)
    return () => clearInterval(id)
  }, [policy])

  const switchPolicy = (p) => {
    setPolicy(p)
    fetchAll(p)
  }

  const pauseJob = async (id) => {
    await fetch(`${API}/jobs/${id}/pause`, { method: 'POST' })
    fetchAll()
  }

  const resumeJob = async (id) => {
    await fetch(`${API}/jobs/${id}/resume`, { method: 'POST' })
    fetchAll()
  }

  const submitBatch = async () => {
    setSubmitting(true)
    try {
      await fetch(`${API}/stats?policy=${policy}`)
      await fetch(`${API}/jobs/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          count: Number(batchCount),
          name_prefix: 'demo',
          job_type: 'simulated',
          total_epochs: 2,
          performance_target: 1,
        }),
      })
      await fetchAll()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h1>Green Hours Scheduler</h1>
        <div className="policy-tabs">
          <button className={policy === 'greedy' ? 'active' : ''} onClick={() => switchPolicy('greedy')}>
            Greedy
          </button>
          <button className={policy === 'ppo' ? 'active' : ''} onClick={() => switchPolicy('ppo')}>
            PPO
          </button>
        </div>
      </div>

      <div className="cards">
        <div className={`card carbon-card ${grid ? carbonClass(grid.carbon_intensity_g_per_kwh) : ''}`}>
          <div className="label">Carbon Intensity</div>
          <div className="value">
            {grid ? `${Math.round(grid.carbon_intensity_g_per_kwh)} gCO₂/kWh` : '—'}
          </div>
          <div className="label">{grid?.source} · {grid?.zone}</div>
        </div>
        <div className="card">
          <div className="label">Waiting</div>
          <div className="value">{stats?.jobs_waiting ?? '—'}</div>
        </div>
        <div className="card">
          <div className="label">Running</div>
          <div className="value">{stats?.jobs_running ?? '—'}</div>
        </div>
        <div className="card">
          <div className="label">Carbon Saved</div>
          <div className="value">
            {stats ? `${stats.total_carbon_saved_g.toFixed(1)} g` : '—'}
          </div>
        </div>
      </div>

      <div className="jobs">
        <div className="jobs-header">
          <h2>Job Queue · policy: {stats?.policy ?? policy}</h2>
          <div className="submit-bar">
            <input
              type="number"
              min="1"
              max="20"
              value={batchCount}
              onChange={(e) => setBatchCount(e.target.value)}
            />
            <button onClick={submitBatch} disabled={submitting}>
              {submitting ? 'Submitting…' : `Submit ${batchCount} jobs`}
            </button>
          </div>
        </div>
        {jobs.length === 0 && <p>No jobs yet.</p>}
        {jobs.map((job) => (
          <div key={job.id} className="job-row">
            <div>
              <strong>{job.name}</strong>
              <span className={`badge ${job.status}`} style={{ marginLeft: '0.75rem' }}>
                {job.status}
              </span>
              {job.performance_target != null && (
                <div className="progress">
                  Epoch {job.current_epoch} / floor {job.performance_target} (target {job.total_epochs})
                </div>
              )}
            </div>
            <div className="actions">
              {job.status === 'RUNNING' && (
                <button onClick={() => pauseJob(job.id)}>Pause</button>
              )}
              {job.status === 'MANUALLY_PAUSED' && (
                <button onClick={() => resumeJob(job.id)}>Resume</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
