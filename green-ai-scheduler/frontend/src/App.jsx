import { useEffect, useState } from 'react'

const API = '/api'

function carbonClass(intensity) {
  if (intensity < 550) return 'clean'
  if (intensity < 700) return 'moderate'
  return 'dirty'
}

function gaiqGrade(job) {
  if (!job || job.baseline_carbon_estimate_g <= 0 || job.status !== 'COMPLETED') return '—'
  const ratio = job.carbon_used_g / job.baseline_carbon_estimate_g
  if (ratio <= 0.75) return 'A'
  if (ratio <= 0.9) return 'B'
  if (ratio <= 1.05) return 'C'
  return 'D'
}

const STATUS_ORDER = ['RUNNING', 'WAITING', 'QUEUED', 'MANUALLY_PAUSED', 'PAUSED', 'COMPLETED', 'FAILED']
const STATUS_LABEL = {
  RUNNING: 'Running',
  WAITING: 'Waiting',
  QUEUED: 'Queued',
  MANUALLY_PAUSED: 'Paused (Manual)',
  PAUSED: 'Paused',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
}

function sortJobs(jobs) {
  return [...jobs].sort((a, b) => {
    const statusDiff = STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)
    if (statusDiff !== 0) return statusDiff
    // Within same status, newest first
    return (b.id ?? 0) - (a.id ?? 0)
  })
}

function JobRow({ job, onPause, onResume }) {
  const [expanded, setExpanded] = useState(false)
  const grade = gaiqGrade(job)
  const saved =
    job.baseline_carbon_estimate_g > 0
      ? (job.baseline_carbon_estimate_g - job.carbon_used_g).toFixed(3)
      : null
  const efficiency =
    job.baseline_carbon_estimate_g > 0
      ? ((1 - job.carbon_used_g / job.baseline_carbon_estimate_g) * 100).toFixed(1)
      : null

  return (
    <div className={`job-row ${expanded ? 'expanded' : ''}`}>
      {/* Always-visible header row */}
      <div className="job-row-header" onClick={() => setExpanded((v) => !v)} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setExpanded((v) => !v)}>
        <div className="job-row-left">
          <span className={`expand-chevron ${expanded ? 'open' : ''}`}>▶</span>
          <div>
            <div className="job-name-line">
              <strong>{job.name}</strong>
              <span className={`badge ${job.status}`}>{STATUS_LABEL[job.status] ?? job.status}</span>
            </div>
            <div className="job-summary">
              <span>Epoch {job.current_epoch}/{job.total_epochs}</span>
              <span className="dot-sep">·</span>
              <span>Carbon {job.carbon_used_g.toFixed(3)} g</span>
              <span className="dot-sep">·</span>
              <span>GaiQ <strong className={`grade-inline grade-${grade}`}>{grade}</strong></span>
            </div>
          </div>
        </div>
        <div className="actions" onClick={(e) => e.stopPropagation()}>
          {job.status === 'RUNNING' && (
            <button onClick={() => onPause(job.id)}>Pause</button>
          )}
          {job.status === 'MANUALLY_PAUSED' && (
            <button onClick={() => onResume(job.id)}>Resume</button>
          )}
        </div>
      </div>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="job-detail">
          <div className="detail-grid">
            <div className="detail-item">
              <div className="detail-label">Carbon Used</div>
              <div className="detail-value carbon-val">{job.carbon_used_g.toFixed(4)} g CO₂</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Baseline Estimate</div>
              <div className="detail-value">{job.baseline_carbon_estimate_g.toFixed(4)} g CO₂</div>
            </div>
            {saved !== null && (
              <div className="detail-item">
                <div className="detail-label">Carbon Saved</div>
                <div className={`detail-value ${parseFloat(saved) >= 0 ? 'saved-pos' : 'saved-neg'}`}>
                  {parseFloat(saved) >= 0 ? '−' : '+'}{Math.abs(parseFloat(saved)).toFixed(3)} g
                </div>
              </div>
            )}
            {efficiency !== null && (
              <div className="detail-item">
                <div className="detail-label">Efficiency vs Baseline</div>
                <div className={`detail-value ${parseFloat(efficiency) >= 0 ? 'saved-pos' : 'saved-neg'}`}>
                  {efficiency}%
                </div>
              </div>
            )}
            <div className="detail-item">
              <div className="detail-label">Energy Used</div>
              <div className="detail-value">{(job.energy_used_kwh ?? 0).toFixed(5)} kWh</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">GaiQ Grade</div>
              <div className={`detail-value grade-lg grade-${grade}`}>{grade}</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Progress</div>
              <div className="detail-value">Epoch {job.current_epoch} / {job.total_epochs}</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Min-epoch Floor</div>
              <div className="detail-value">{job.performance_target ?? '—'}</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Pause Count</div>
              <div className="detail-value">{job.pause_count ?? 0}</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Priority</div>
              <div className="detail-value">{job.priority ?? 1}</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Job Type</div>
              <div className="detail-value">{job.job_type ?? '—'}</div>
            </div>
            <div className="detail-item">
              <div className="detail-label">Status</div>
              <div className="detail-value"><span className={`badge ${job.status}`}>{STATUS_LABEL[job.status] ?? job.status}</span></div>
            </div>
          </div>
          {job.current_epoch > 0 && job.total_epochs > 0 && (
            <div className="epoch-progress-wrap">
              <div className="epoch-progress-label">
                <span>Training Progress</span>
                <span>{Math.round((job.current_epoch / job.total_epochs) * 100)}%</span>
              </div>
              <div className="epoch-bar">
                <div
                  className="epoch-bar-fill"
                  style={{ width: `${Math.min(100, (job.current_epoch / job.total_epochs) * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [grid, setGrid] = useState(null)
  const [stats, setStats] = useState(null)
  const [jobs, setJobs] = useState([])
  const [policy, setPolicy] = useState('greedy')
  const [batchCount, setBatchCount] = useState(5)
  const [submitting, setSubmitting] = useState(false)
  const [view, setView] = useState('scheduler')
  const [comparison, setComparison] = useState(null)
  const [comparisonRunning, setComparisonRunning] = useState(false)
  const [comparisonSeed, setComparisonSeed] = useState(42)
  const [comparisonHorizon, setComparisonHorizon] = useState(2000)
  const [jobType, setJobType] = useState('simulated')
  const [totalEpochs, setTotalEpochs] = useState(2)
  const [priority, setPriority] = useState(1)
  const [submitStatus, setSubmitStatus] = useState('')

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
    setSubmitStatus(`Preparing ${batchCount} ${jobType === 'simulated' ? 'simulated' : 'real'} job${Number(batchCount) === 1 ? '' : 's'}...`)
    try {
      await fetch(`${API}/stats?policy=${policy}`)
      const response = await fetch(`${API}/jobs/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          count: Number(batchCount),
          name_prefix: jobType === 'simulated' ? 'simulated-demo' : `${jobType}-demo`,
          job_type: jobType,
          total_epochs: Number(totalEpochs),
          performance_target: 1,
          priority: Number(priority),
        }),
      })
      if (!response.ok) throw new Error('Unable to submit jobs')
      setSubmitStatus(`${batchCount} job${Number(batchCount) === 1 ? '' : 's'} queued under ${formatPolicy(policy)}.`)
      await fetchAll()
    } catch (error) {
      setSubmitStatus(error.message)
    } finally {
      setSubmitting(false)
    }
  }

  const runComparison = async () => {
    setComparisonRunning(true)
    try {
      const response = await fetch(`${API}/comparison/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          policies: ['greedy', 'forecast', 'constraint_lexicographic', 'ppo'],
          horizon: Number(comparisonHorizon),
          seed: Number(comparisonSeed),
        }),
      })
      const run = await response.json()
      const result = await fetch(`${API}/comparison/${run.run_id}`).then((r) => r.json())
      setComparison(result)
    } finally {
      setComparisonRunning(false)
    }
  }

  const formatPolicy = (name) => name.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  const completedJobs = jobs.filter((job) => job.status === 'COMPLETED')
  const gradeCounts = completedJobs.reduce((counts, job) => {
    const grade = gaiqGrade(job)
    if (grade !== '—') counts[grade] = (counts[grade] || 0) + 1
    return counts
  }, {})
  const leadingGrade = ['A', 'B', 'C', 'D'].find((grade) => gradeCounts[grade]) || '—'

  const sortedJobs = sortJobs(jobs)

  // Group sorted jobs by status group for section headers
  const groupedJobs = []
  let lastGroup = null
  for (const job of sortedJobs) {
    const group = STATUS_ORDER.includes(job.status) ? job.status : 'OTHER'
    if (group !== lastGroup) {
      groupedJobs.push({ type: 'header', group })
      lastGroup = group
    }
    groupedJobs.push({ type: 'job', job })
  }

  if (view === 'comparison') {
    const rows = comparison?.result?.policies ?? {}
    return (
      <div className="app">
        <div className="header">
          <div>
            <p className="eyebrow">Research workspace</p>
            <h1>Policy Comparison</h1>
          </div>
          <button className="quiet-button" onClick={() => setView('scheduler')}>Back to Scheduler</button>
        </div>
        <section className="comparison-intro">
          <div>
            <p className="eyebrow">Research workspace</p>
            <h2>Compare the decisions behind every training hour.</h2>
            <p>One carbon trace, one generated workload, four policies. Results stay separate from live jobs.</p>
          </div>
          <div className="intro-stamp"><strong>4</strong><span>policies<br />in one run</span></div>
        </section>
        <section className="comparison-controls">
          <div><label>Horizon<input type="number" min="1" value={comparisonHorizon} onChange={(e) => setComparisonHorizon(e.target.value)} /><small>Simulation ticks evaluated</small></label></div>
          <div><label>Seed<input type="number" min="0" value={comparisonSeed} onChange={(e) => setComparisonSeed(e.target.value)} /><small>Same workload randomness</small></label></div>
          <button className="run-button" onClick={runComparison} disabled={comparisonRunning}>
            {comparisonRunning ? 'Running benchmark...' : 'Run four-policy benchmark'}
          </button>
        </section>
        {comparison && (
          <>
            <div className="comparison-meta">
              <span>Run {comparison.run_id}</span>
              <span>{comparison.result.config.dataset}</span>
              <span>Seed {comparison.result.config.seed}</span>
              <span>Horizon {comparison.result.config.horizon}</span>
            </div>
            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead><tr><th>Policy</th><th>Carbon</th><th>Saved</th><th>Completed</th><th>Deadline misses</th><th>Avg pauses</th><th>Score</th></tr></thead>
                <tbody>{Object.entries(rows).map(([name, row]) => (
                  <tr key={name}>
                    <td><strong>{formatPolicy(name)}</strong></td>
                    <td>{row.total_carbon_g.toFixed(2)} g</td>
                    <td>{row.carbon_saved_g.toFixed(2)} g</td>
                    <td>{row.jobs_completed}/{row.jobs_submitted}</td>
                    <td>{row.deadline_misses}</td>
                    <td>{row.average_pause_count.toFixed(2)}</td>
                    <td>{comparison.result.score[name] == null ? '—' : comparison.result.score[name].toFixed(3)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="comparison-cards">
              {Object.entries(rows).map(([name, row]) => (
                <div className="comparison-card" key={name}><span>{formatPolicy(name)}</span><strong>{row.deadline_satisfaction_percent.toFixed(1)}%</strong><small>deadline satisfaction</small><div className="bar"><i style={{ width: `${row.clean_window_completion_percent}%` }} /></div><small>{row.clean_window_completion_percent.toFixed(1)}% clean-window finishes</small></div>
              ))}
            </div>
          </>
        )}
        {!comparison && <p className="empty-state">Run an experiment to generate reproducible results for all four policies.</p>}
      </div>
    )
  }

  return (
    <div className="app">
      <div className="header">
        <div>
          <p className="eyebrow">Carbon-aware compute control</p>
          <h1>Green Hours Scheduler</h1>
        </div>
        <div className="page-tabs">
          <button className={view === 'scheduler' ? 'active' : ''} onClick={() => setView('scheduler')}>Scheduler</button>
          <button className={view === 'comparison' ? 'active' : ''} onClick={() => setView('comparison')}>Comparison</button>
        </div>
        <div className="policy-tabs" aria-label="Scheduling policy">
          {['greedy', 'forecast', 'constraint_lexicographic', 'ppo'].map((name) => (
            <button key={name} className={policy === name ? 'active' : ''} onClick={() => switchPolicy(name)}>
              {formatPolicy(name)}
            </button>
          ))}
        </div>
      </div>

      <section className="scheduler-intro">
        <div className="intro-copy">
          <p className="eyebrow">Live control room</p>
          <h2>Schedule training for cleaner hours.</h2>
          <p>Choose a policy, send a workload, and let the grid signal guide execution.</p>
        </div>
        <div className={`grid-pulse ${grid ? carbonClass(grid.carbon_intensity_g_per_kwh) : ''}`}>
          <span className="pulse-dot" />
          <span>{grid?.source ? `${grid.source} · ${grid.zone}` : 'Grid signal connecting'}</span>
        </div>
      </section>

      <div className="cards">
        <div className={`card carbon-card ${grid ? carbonClass(grid.carbon_intensity_g_per_kwh) : ''}`}>
          <div className="label">Carbon Intensity</div>
          <div className="value">
            {grid ? `${Math.round(grid.carbon_intensity_g_per_kwh)} gCO₂/kWh` : '—'}
          </div>
          <div className="source-line"><span className="source-mark" />{grid?.source || 'Electricity Maps'} · {grid?.zone || 'IN'}</div>
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
        <div className="card grade-card">
          <div className="label">GaiQ grade</div>
          <div className="value grade-value">{leadingGrade}</div>
          <div className="label">Completed-job efficiency</div>
        </div>
      </div>

      <div className="jobs">
        <div className="jobs-header">
          <div>
            <p className="eyebrow">Execution queue</p>
            <h2>Jobs under {formatPolicy(policy)}</h2>
          </div>
          <div className="submit-bar">
              <label className="field"><span>Quantity</span><input type="number" min="1" max="20" value={batchCount} onChange={(e) => setBatchCount(e.target.value)} /></label>
              <label className="field"><span>Workload</span><select value={jobType} onChange={(e) => setJobType(e.target.value)}><option value="simulated">Simulated demo</option><option value="resnet50_cifar">Real ResNet50 + CIFAR</option><option value="bert_imdb">Real DistilBERT + IMDB</option></select></label>
              <label className="field"><span>Priority</span><select value={priority} onChange={(e) => setPriority(e.target.value)}><option value="1">Normal</option><option value="2">High</option></select></label>
              <label className="field"><span>Epochs</span><input type="number" min="1" max="10" value={totalEpochs} onChange={(e) => setTotalEpochs(e.target.value)} /></label>
              <button onClick={submitBatch} disabled={submitting}>{submitting ? 'Submitting...' : 'Submit jobs'}</button>
          </div>
        </div>
        {submitStatus && <div className={`submit-status ${submitting ? 'pending' : ''}`}><span className="status-dot" />{submitStatus}</div>}
        {jobs.length === 0 && <p className="empty-state">No jobs yet. Submit a batch above to get started.</p>}
        {groupedJobs.map((item, i) =>
          item.type === 'header' ? (
            <div key={`header-${item.group}-${i}`} className="job-group-header">
              <span className={`group-badge ${item.group}`}>{STATUS_LABEL[item.group] ?? item.group}</span>
              <div className="group-divider" />
            </div>
          ) : (
            <JobRow
              key={item.job.id}
              job={item.job}
              onPause={pauseJob}
              onResume={resumeJob}
            />
          )
        )}
      </div>
    </div>
  )
}
