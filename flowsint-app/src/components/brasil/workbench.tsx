import { useEffect, useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, MiniMap, Position } from '@xyflow/react'
import {
  Network,
  Workflow,
  Database,
  ArrowUpRight,
  Play,
  Plus,
  Download,
  ShieldCheck,
  Search,
  Fingerprint,
  Clock3,
  ChevronRight,
  FlaskConical,
  RefreshCw,
  Building2,
  MapPin,
  X,
  FileCheck2
} from 'lucide-react'
import '@xyflow/react/dist/style.css'
import './brasil.css'

type Api = (path: string, options?: RequestInit) => Promise<any>
type Case = { id: string; title: string; purpose: string; created_at: string; runs?: Run[] }
type Evidence = {
  id: string
  kind: string
  query: string
  status: string
  url?: string
  retrieved_at: string
  sha256?: string
  raw?: string
  data?: Record<string, unknown>
  message?: string
  mode: string
}
type Entity = {
  id: string
  kind: string
  label: string
  properties: Record<string, unknown>
  evidence_id: string
}
type Run = {
  id: string
  mode: string
  seed: string
  steps: string[]
  status: string
  created_at: string
  graph: { nodes: Entity[]; edges: { id: string; source: string; target: string; label: string }[] }
  evidence: Evidence[]
  changes: { entity: string; field: string; before: unknown; after: unknown }[]
  baseline_id: string | null
  chain_hash: string
}
type Recipe = { id: string; name: string; description: string; seed_kind: string; steps: string[] }
type Source = {
  id: string
  name: string
  category: string
  url: string
  status: string
  description: string
  provenance: string
}
const labels: Record<string, string> = {
  cnpj: 'Cadastro CNPJ',
  cep: 'Área postal',
  municipio: 'Município IBGE'
}
const colors: Record<string, string> = { cnpj: '#69e3b0', cep: '#e4bc76', municipio: '#82afff' }
const fmt = (x: unknown) =>
  x == null ? 'Não informado' : typeof x === 'object' ? JSON.stringify(x) : String(x)
const date = (s: string) => new Date(s).toLocaleString('pt-BR')
function download(name: string, value: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })
  )
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function BrazilWorkbench({ api, lab = false }: { api: Api; lab?: boolean }) {
  const [mobile, setMobile] = useState(window.innerWidth < 760)
  useEffect(() => {
    const resize = () => setMobile(window.innerWidth < 760)
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  const [page, setPage] = useState('investigar'),
    [tab, setTab] = useState('grafo')
  const [cases, setCases] = useState<Case[]>([]),
    [active, setActive] = useState<Case | null>(null)
  const [recipes, setRecipes] = useState<Recipe[]>([]),
    [recipe, setRecipe] = useState('empresa-territorio')
  const [sources, setSources] = useState<Source[]>([]),
    [search, setSearch] = useState(''),
    [filter, setFilter] = useState('all')
  const [seed, setSeed] = useState(''),
    [mode, setMode] = useState('live'),
    [runId, setRunId] = useState('')
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState('')
  const [selected, setSelected] = useState<Entity | null>(null),
    [modal, setModal] = useState(false)
  const [title, setTitle] = useState(''),
    [purpose, setPurpose] = useState('')
  const [depth, setDepth] = useState(3)
  const chosen = recipes.find((r) => r.id === recipe)
  const runs = active?.runs || [],
    run = runs.find((r) => r.id === runId) || runs[runs.length - 1]
  const request = (path: string, options?: RequestInit) => api('/api/brasil' + path, options)
  useEffect(() => {
    let alive = true
    Promise.all([api('/api/brasil/cases'), api('/api/brasil/recipes'), api('/api/brasil/sources')])
      .then(([c, r, s]) => {
        if (alive) {
          setCases(c)
          setRecipes(r)
          setSources(s)
        }
      })
      .catch((e) => setError(e.message))
    return () => {
      alive = false
    }
  }, [api])
  async function load(id: string) {
    setError('')
    try {
      setActive(await request('/cases/' + id))
      setRunId('')
      setSelected(null)
    } catch (e) {
      setError(String(e))
    }
  }
  async function create() {
    setBusy(true)
    setError('')
    try {
      const c = await request('/cases', {
        method: 'POST',
        body: JSON.stringify({ title, purpose })
      })
      setCases([c, ...cases])
      setActive({ ...c, runs: [] })
      setModal(false)
      setTitle('')
      setPurpose('')
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }
  async function execute(demo = false) {
    if (!chosen) return
    setBusy(true)
    setError('')
    setNotice('')
    setSelected(null)
    try {
      let current = active
      if (demo) {
        current = await request('/cases', {
          method: 'POST',
          body: JSON.stringify({
            title: 'Operação Aurora · laboratório',
            purpose: 'Aprender a investigar relações empresariais usando apenas dados sintéticos.'
          })
        })
        setCases(await request('/cases'))
        setRecipe('empresa-territorio')
        setDepth(3)
        setSeed('11222333000181')
        setMode('demo')
      }
      if (!current) throw new Error('Crie ou selecione um caso antes de executar.')
      const payload = demo
        ? {
            seed_kind: 'cnpj',
            seed: '11222333000181',
            steps: ['cnpj', 'cep', 'municipio'],
            mode: 'demo'
          }
        : { seed_kind: chosen.seed_kind, seed, steps: chosen.steps.slice(0, depth), mode }
      const result = await request('/cases/' + current.id + '/runs', {
        method: 'POST',
        body: JSON.stringify(payload)
      })
      setActive(await request('/cases/' + current.id))
      setRunId(result.id)
      setPage('investigar')
      setTab('grafo')
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }
  async function exportBundle() {
    if (!active) return
    try {
      const b = await request('/cases/' + active.id + '/export')
      download('osintbrflow-' + active.id + '.json', b)
      setNotice('Pacote exportado com respostas preservadas e manifesto de integridade.')
    } catch (e) {
      setError(String(e))
    }
  }
  async function exportGraph() {
    if (!active || !run) return
    try {
      download(
        'flowsint-graph-' + run.id + '.json',
        await request('/cases/' + active.id + '/graph/' + run.id)
      )
      setNotice(
        'Grafo exportado. Na investigação nativa, use Importar JSON para continuar com outros enriquecedores.'
      )
    } catch (e) {
      setError(String(e))
    }
  }
  async function verifyFile(file?: File) {
    if (!file) return
    try {
      if (file.size > 15_000_000) throw new Error('Limite: 15 MB.')
      const result = await request('/verify', { method: 'POST', body: await file.text() })
      setNotice(
        result.valid
          ? `Integridade verificada · ${result.runs} coletas. O hash não comprova a veracidade da fonte.`
          : result.errors.join(' ')
      )
    } catch (e) {
      setError(String(e))
    }
  }
  const nodes = useMemo(
    () =>
      (run?.graph.nodes || []).map((n, i) => ({
        id: n.id,
        position: mobile ? { x: 0, y: i * 220 } : { x: i * 320, y: i === 1 ? 150 : 70 },
        sourcePosition: mobile ? Position.Bottom : Position.Right,
        targetPosition: mobile ? Position.Top : Position.Left,
        data: {
          label: (
            <div className="br-node">
              <span style={{ color: colors[n.kind] }}>{labels[n.kind]}</span>
              <strong>{n.label}</strong>
              <small>{n.id.split(':')[1]}</small>
              <em>
                Fonte preservada <ShieldCheck size={12} />
              </em>
            </div>
          )
        },
        style: {
          background: '#142327',
          border: `1px solid ${colors[n.kind]}77`,
          borderRadius: 14,
          width: 240,
          color: '#eef6f4'
        }
      })),
    [run, mobile]
  )
  const edges = useMemo(
    () =>
      (run?.graph.edges || []).map((e) => ({
        ...e,
        style: { stroke: '#73b59c', strokeWidth: 1.5 },
        labelStyle: { fill: '#afc4bf', fontSize: 10 },
        labelBgStyle: { fill: '#0b171a' },
        animated: false
      })),
    [run]
  )
  const displayed = sources.filter(
    (s) =>
      (filter === 'all' || s.status === filter) &&
      (s.name + ' ' + s.category + ' ' + s.description).toLowerCase().includes(search.toLowerCase())
  )
  const selectedEvidence = run?.evidence.find((e) => e.id === selected?.evidence_id)
  return (
    <div className="br-shell">
      <aside className="br-sidebar">
        <a className="br-brand" href={lab ? '/brasil.html' : '/dashboard/brasil'}>
          <span className="br-mark">
            <Network size={24} />
          </span>
          <span>
            OSINT BRASIL
            <strong>
              FLOW<span> / 01</span>
            </strong>
          </span>
        </a>
        <div className="br-sidebar-label">INTELIGÊNCIA COM CONTEXTO</div>
        {[
          ['investigar', 'Investigar', Network],
          ['fluxos', 'Fluxos brasileiros', Workflow],
          ['fontes', 'Atlas de fontes', Database]
        ].map(([id, label, Icon]) => {
          const I = Icon as typeof Network
          return (
            <button
              key={String(id)}
              className={'br-nav ' + (page === id ? 'active' : '')}
              onClick={() => setPage(String(id))}
            >
              <I size={18} />
              {String(label)}
              <ChevronRight size={13} />
            </button>
          )
        })}
        <div className="br-sidebar-label br-cases-label">
          SEUS CASOS{' '}
          <button title="Novo caso" onClick={() => setModal(true)}>
            <Plus size={16} />
          </button>
        </div>
        <div className="br-case-list">
          {cases.length ? (
            cases.map((c) => (
              <button
                key={c.id}
                onClick={() => load(c.id)}
                className={active?.id === c.id ? 'selected' : ''}
              >
                <span className="br-case-dot" />
                {c.title}
              </button>
            ))
          ) : (
            <p>Seu próximo caso começa com uma pergunta.</p>
          )}
        </div>
        <button className="br-lab-button" disabled={busy} onClick={() => execute(true)}>
          <FlaskConical size={19} />
          <span>
            Explore o laboratório<small>Caso fictício. Nenhuma consulta externa.</small>
          </span>
        </button>
        <footer>
          <span className="br-status-dot" />{' '}
          {lab ? 'Laboratório local · usuário único' : 'Sessão autenticada'}
          <small>Derivado de Flowsint · Apache 2.0</small>
        </footer>
      </aside>
      <main className="br-main">
        <header className="br-top">
          <span>
            WORKSPACE <span>/</span>{' '}
            {page === 'fontes'
              ? 'Atlas de fontes'
              : page === 'fluxos'
                ? 'Fluxos brasileiros'
                : active?.title || 'Nova investigação'}
          </span>
          <div>
            <span className="br-tag">BRASIL</span>
            <button className="br-button" onClick={() => setModal(true)}>
              <Plus size={15} /> Novo caso
            </button>
          </div>
        </header>
        <div className="br-content">
          {error && (
            <div role="alert" className="br-alert">
              {error}
              <button onClick={() => setError('')} aria-label="Fechar erro">
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="br-notice">
              {notice}
            </div>
          )}
          <div className="br-heading">
            <div>
              <div className="br-eyebrow">DO INDÍCIO À EVIDÊNCIA</div>
              <h1>
                {page === 'fontes'
                  ? 'As fontes certas. O contexto brasileiro.'
                  : page === 'fluxos'
                    ? 'Investigações que seguem um raciocínio.'
                    : 'Conecte os fatos. Preserve a origem.'}
              </h1>
              <p>
                {page === 'fontes'
                  ? 'Fontes automatizadas e pesquisa manual claramente identificadas.'
                  : page === 'fluxos'
                    ? 'Escolha uma missão, ajuste o percurso e execute no seu caso.'
                    : 'Cadastro, território e tempo em uma investigação verificável.'}
              </p>
            </div>
            <div className="br-seal">
              <Fingerprint size={30} />
              <span>
                PROVENIÊNCIA
                <br />
                <b>POR PADRÃO</b>
              </span>
            </div>
          </div>
          {page === 'fontes' ? (
            <>
              <div className="br-search">
                <Search size={18} />
                <input
                  aria-label="Buscar fonte"
                  placeholder="Busque por fonte, tema ou órgão…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <select
                  aria-label="Filtrar acesso"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">Todas as fontes</option>
                  <option value="api">API implementada</option>
                  <option value="manual">Consulta manual</option>
                </select>
                <span>{displayed.length} fontes</span>
              </div>
              <div className="br-source-grid">
                {displayed.slice(0, 120).map((s) => (
                  <article className="br-source" key={s.id}>
                    <span className={'br-badge ' + (s.status === 'api' ? 'live' : '')}>
                      {s.status === 'api' ? 'CONECTOR REAL' : 'PESQUISA MANUAL'}
                    </span>
                    <h3>{s.name}</h3>
                    <small>{s.category}</small>
                    <p>
                      {s.description ||
                        'Fonte de referência para consulta externa. Disponibilidade e requisitos devem ser conferidos no portal.'}
                    </p>
                    <a href={s.url} target="_blank" rel="noreferrer">
                      Abrir fonte <ArrowUpRight size={14} />
                    </a>
                    <footer>{s.provenance}</footer>
                  </article>
                ))}
              </div>
              {displayed.length > 120 && (
                <p>Exibindo 120 resultados. Refine a busca para localizar outras fontes.</p>
              )}
            </>
          ) : (
            <>
              {page === 'fluxos' && (
                <div className="br-recipes">
                  {recipes.map((r) => (
                    <button
                      key={r.id}
                      className={recipe === r.id ? 'chosen' : ''}
                      onClick={() => {
                        setRecipe(r.id)
                        setDepth(r.steps.length)
                        setMode('live')
                        setSeed('')
                      }}
                    >
                      <Workflow size={24} />
                      <h3>{r.name}</h3>
                      <p>{r.description}</p>
                      <span>
                        {r.steps.length} etapas <ChevronRight size={15} />
                      </span>
                    </button>
                  ))}
                </div>
              )}
              <section className="br-launch">
                <div className="br-launch-title">
                  <span className="br-icon-box">
                    <Workflow size={18} />
                  </span>
                  <div>
                    <b>Uma semente. Novas conexões.</b>
                    <small>Consultas limitadas ao fluxo selecionado.</small>
                  </div>
                  <span className="br-badge">SEM CHAVE DE API</span>
                </div>
                <div className="br-launch-form">
                  <label>
                    FLUXO
                    <select
                      value={recipe}
                      onChange={(e) => {
                        setRecipe(e.target.value)
                        setDepth(3)
                        setMode('live')
                        setSeed('')
                      }}
                    >
                      {recipes.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="br-seed">
                    {chosen?.seed_kind === 'cnpj'
                      ? 'CNPJ NUMÉRICO OU ALFANUMÉRICO'
                      : chosen?.seed_kind === 'cep'
                        ? 'CEP'
                        : 'CÓDIGO IBGE'}
                    <input
                      aria-label="Semente da investigação"
                      placeholder={
                        chosen?.seed_kind === 'cnpj'
                          ? '00.000.000/0001-00'
                          : chosen?.seed_kind === 'cep'
                            ? '00000-000'
                            : '3106200'
                      }
                      value={seed}
                      onChange={(e) => setSeed(e.target.value)}
                    />
                  </label>
                  <label>
                    MODO
                    <select value={mode} onChange={(e) => setMode(e.target.value)}>
                      <option value="live">Fontes reais</option>
                      <option value="demo">Dados sintéticos</option>
                    </select>
                  </label>
                  <button
                    className="br-primary"
                    disabled={busy || !seed || !active}
                    onClick={() => execute()}
                  >
                    {busy ? <RefreshCw className="br-spin" size={17} /> : <Play size={17} />}{' '}
                    {busy ? 'Consultando…' : 'Executar fluxo'}
                  </button>
                </div>
                <div className="br-path">
                  {chosen?.steps.map((s, i) => (
                    <span key={s} className={i < depth ? '' : 'muted'}>
                      <i>{i + 1}</i>
                      {labels[s]}
                      {i < chosen.steps.length - 1 && <ChevronRight size={13} />}
                    </span>
                  ))}
                  <label>
                    Parar após{' '}
                    <select
                      aria-label="Limite de etapas"
                      value={Math.min(depth, chosen?.steps.length || 1)}
                      onChange={(e) => setDepth(Number(e.target.value))}
                    >
                      {chosen?.steps.map((_, i) => (
                        <option key={i} value={i + 1}>
                          {i + 1} etapa(s)
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </section>
              <div className="br-metrics">
                <div>
                  <Network size={20} />
                  <strong>{run?.graph.nodes.length || 0}</strong>
                  <span>Entidades observadas</span>
                </div>
                <div>
                  <ShieldCheck size={20} />
                  <strong>{run?.evidence.filter((e) => e.status === 'ok').length || 0}</strong>
                  <span>Respostas preservadas</span>
                </div>
                <div>
                  <Clock3 size={20} />
                  <strong>{runs.length}</strong>
                  <span>Coletas neste caso</span>
                </div>
                <div>
                  <Fingerprint size={20} />
                  <strong>{run?.baseline_id ? run.changes.length : '—'}</strong>
                  <span>
                    {run?.baseline_id
                      ? 'Mudanças desde a coleta anterior'
                      : 'Aguardando comparação'}
                  </span>
                </div>
              </div>
              <section className="br-investigation">
                <div className="br-tabbar">
                  <div>
                    {['grafo', 'evidências', 'mudanças', 'histórico'].map((t) => (
                      <button
                        className={tab === t ? 'active' : ''}
                        onClick={() => setTab(t)}
                        key={t}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  <div>
                    <label className="br-upload" title="Verificar integridade de um pacote">
                      <FileCheck2 size={16} />
                      <input
                        aria-label="Verificar pacote"
                        type="file"
                        accept=".json"
                        onChange={(e) => verifyFile(e.target.files?.[0])}
                      />
                    </label>
                    <button
                      disabled={!run}
                      onClick={exportGraph}
                      title="Exportar grafo para Flowsint"
                    >
                      <Network size={16} />
                    </button>
                    <button disabled={!active} onClick={exportBundle} title="Exportar evidências">
                      <Download size={16} />
                    </button>
                  </div>
                </div>
                {run ? (
                  <>
                    <div className="br-run-strip">
                      <span className={'br-badge ' + (run.mode === 'demo' ? 'demo' : 'live')}>
                        {run.mode === 'demo' ? 'DADOS SINTÉTICOS' : 'COLETA REAL'}
                      </span>
                      <span>{date(run.created_at)}</span>
                      <span>
                        {run.status === 'complete'
                          ? 'Fluxo concluído'
                          : run.status === 'partial'
                            ? 'Coleta parcial'
                            : 'Coleta falhou'}
                      </span>
                      <code>{run.id.slice(0, 8)}</code>
                    </div>
                    {tab === 'grafo' && (
                      <div className="br-graph">
                        <ReactFlow
                          key={run.id + String(mobile)}
                          nodes={nodes}
                          minZoom={0.15}
                          edges={edges}
                          fitView
                          fitViewOptions={{ padding: 0.35 }}
                          onNodeClick={(_, n) =>
                            setSelected(run.graph.nodes.find((x) => x.id === n.id) || null)
                          }
                          nodesDraggable={false}
                          colorMode="dark"
                        >
                          <Background color="#244036" gap={22} />
                          <Controls />
                          <MiniMap
                            nodeColor={(n) =>
                              colors[run.graph.nodes.find((x) => x.id === n.id)?.kind || 'cnpj']
                            }
                            maskColor="#081215aa"
                          />
                        </ReactFlow>
                        <div className="br-graph-caption">
                          Clique em uma entidade para rastrear sua origem.
                        </div>
                        {selected && (
                          <aside className="br-inspector">
                            <button
                              className="br-close"
                              onClick={() => setSelected(null)}
                              aria-label="Fechar entidade"
                            >
                              <X size={17} />
                            </button>
                            <span className="br-eyebrow">ENTIDADE OBSERVADA</span>
                            <h3>{selected.label}</h3>
                            {Object.entries(selected.properties).map(([k, v]) => (
                              <div key={k}>
                                <small>{k}</small>
                                <p>{fmt(v)}</p>
                              </div>
                            ))}
                            <span className="br-eyebrow">ORIGEM</span>
                            <p>{selectedEvidence?.url}</p>
                            <small>SHA-256</small>
                            <code>{selectedEvidence?.sha256}</code>
                            <p>Relação reportada pela fonte. Não é uma conclusão sobre conduta.</p>
                          </aside>
                        )}
                      </div>
                    )}
                    {tab === 'evidências' && (
                      <div className="br-evidence-list">
                        {run.evidence.map((e) => (
                          <details key={e.id}>
                            <summary>
                              <ShieldCheck size={18} />
                              <b>{labels[e.kind]}</b>
                              <span>{e.status === 'ok' ? 'PRESERVADA' : e.status}</span>
                              <small>{date(e.retrieved_at)}</small>
                            </summary>
                            <p>{e.message || e.url}</p>
                            <code>{e.sha256}</code>
                            <pre>{e.raw || e.message}</pre>
                          </details>
                        ))}
                      </div>
                    )}
                    {tab === 'mudanças' && (
                      <div className="br-changes">
                        {!run.baseline_id ? (
                          <div className="br-empty">
                            <Clock3 size={32} />
                            <h3>Precisamos de duas coletas comparáveis.</h3>
                            <p>
                              Repita a mesma semente, modo e fluxo. Falhas não são tratadas como
                              desaparecimento de dados.
                            </p>
                          </div>
                        ) : run.changes.length ? (
                          <table>
                            <thead>
                              <tr>
                                <th>Entidade / campo</th>
                                <th>Antes</th>
                                <th>Depois</th>
                              </tr>
                            </thead>
                            <tbody>
                              {run.changes.map((c, i) => (
                                <tr key={i}>
                                  <td>
                                    {c.entity}
                                    <small>{c.field}</small>
                                  </td>
                                  <td>{fmt(c.before)}</td>
                                  <td>{fmt(c.after)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <div className="br-empty">
                            <ShieldCheck size={32} />
                            <h3>Nenhuma mudança nos campos comparados.</h3>
                            <p>
                              A mesma resposta não constitui uma fonte independente de corroboração.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                    {tab === 'histórico' && (
                      <div className="br-history">
                        {[...runs].reverse().map((r) => (
                          <button
                            className={r.id === run.id ? 'active' : ''}
                            key={r.id}
                            onClick={() => {
                              setRunId(r.id)
                              setSelected(null)
                            }}
                          >
                            <Clock3 size={20} />
                            <div>
                              <b>{date(r.created_at)}</b>
                              <p>
                                {r.seed} · {r.mode === 'demo' ? 'sintético' : 'real'} · {r.status}
                              </p>
                              <code>{r.chain_hash.slice(0, 32)}…</code>
                            </div>
                            <ChevronRight size={18} />
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="br-empty br-first">
                    <div className="br-empty-symbol">
                      <Building2 size={27} />
                      <span />
                      <MapPin size={27} />
                    </div>
                    <h2>Qual conexão você quer investigar?</h2>
                    <p>
                      Crie um caso e informe um identificador. Ou conheça o percurso com uma
                      investigação fictícia, sem acessar fontes externas.
                    </p>
                    <button className="br-primary" disabled={busy} onClick={() => execute(true)}>
                      <FlaskConical size={16} /> Explorar caso demonstrativo
                    </button>
                  </div>
                )}
              </section>
              <div className="br-bottom-note">
                <ShieldCheck size={15} />
                <span>
                  Um vínculo é uma observação, não uma acusação. CEP não prova residência; hash não
                  prova veracidade.
                </span>
                <a
                  href="https://github.com/Ridd1kulusC0d3r/OsintbrFLOW"
                  target="_blank"
                  rel="noreferrer"
                >
                  Método e código <ArrowUpRight size={13} />
                </a>
              </div>
            </>
          )}
        </div>
      </main>
      {modal && (
        <div className="br-modal-backdrop">
          <form
            className="br-modal"
            onSubmit={(e) => {
              e.preventDefault()
              create()
            }}
          >
            <button
              type="button"
              className="br-close"
              onClick={() => setModal(false)}
              aria-label="Fechar novo caso"
            >
              <X size={19} />
            </button>
            <span className="br-eyebrow">UMA PERGUNTA BEM DEFINIDA</span>
            <h2>Abrir investigação</h2>
            <label>
              Nome do caso
              <input
                autoFocus
                minLength={3}
                maxLength={120}
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ex.: verificação de fornecedor"
              />
            </label>
            <label>
              Finalidade da investigação
              <textarea
                minLength={5}
                maxLength={500}
                required
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="O que você precisa verificar e por quê?"
              />
            </label>
            <button className="br-primary" disabled={busy} type="submit">
              <Plus size={16} /> Criar caso
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
