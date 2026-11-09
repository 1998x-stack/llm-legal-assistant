import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, ApiError, type Finding, type Identity, type Matter, type MatterSummary, type Role } from './api';

type RiskPosture = 'balanced' | 'conservative' | 'fast';
type ClientRole = 'both' | 'receiving' | 'disclosing';
type ContextForm = {
  contract_type: string; language: string; parties_are_businesses: boolean;
  governing_law: string; client_role: ClientRole; risk_posture: RiskPosture; purpose: string;
};
const initialContext: ContextForm = {
  contract_type: 'mutual_nda', language: 'en', parties_are_businesses: true,
  governing_law: 'NY', client_role: 'both', risk_posture: 'balanced',
  purpose: 'Evaluate a potential business collaboration'
};

const complete = (f: Finding) => ['accepted', 'edited', 'dismissed'].includes(f.decision);

export function App() {
  const [identity, setIdentity] = useState<Identity>({user: 'demo-reviewer', role: 'reviewer'});
  const [matters, setMatters] = useState<MatterSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Matter | null>(null);
  const [newName, setNewName] = useState('Synthetic NDA — demo matter');
  const [file, setFile] = useState<File | null>(null);
  const [context, setContext] = useState<ContextForm>(initialContext);
  const [activeFinding, setActiveFinding] = useState<string | null>(null);
  const [decisionText, setDecisionText] = useState('');
  const [reason, setReason] = useState('');
  const [exportId, setExportId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(async () => {
    try {
      const result = await api.list(identity);
      setMatters(result.items);
    } catch (e) { setError(message(e)); }
  }, [identity]);

  const refresh = useCallback(async () => {
    if (!selectedId) return;
    try {
      const next = await api.detail(identity, selectedId);
      setDetail(next);
      if (next.context) setContext(next.context as ContextForm);
    } catch (e) { setDetail(null); setError(message(e)); }
  }, [identity, selectedId]);

  useEffect(() => { void loadList(); }, [loadList]);
  useEffect(() => { void refresh(); }, [refresh]);

  const currentFinding = useMemo(
    () => detail?.findings.find(f => f.id === activeFinding) ?? null,
    [detail, activeFinding]
  );
  const pending = detail?.findings.filter(f => !complete(f)).length ?? 0;
  const coverageComplete = (detail?.coverage.length ?? 0) === 3;
  const canApprove = identity.role === 'reviewer' &&
    Boolean(detail && ['REVIEW_READY', 'IN_REVIEW'].includes(detail.status)) &&
    pending === 0 && coverageComplete;

  function message(e: unknown): string {
    if (e instanceof ApiError) return e.code + ': ' + e.message;
    if (e instanceof Error) return e.message;
    return 'Unknown error';
  }

  async function perform(label: string, operation: () => Promise<unknown>) {
    setBusy(true); setError(''); setNotice('');
    try {
      await operation();
      await Promise.all([refresh(), loadList()]);
      setNotice(label + ' completed in the local demonstration.');
    } catch (e) {
      setError(message(e));
      if (e instanceof ApiError && e.code === 'VERSION_STALE') await refresh();
    } finally { setBusy(false); }
  }

  async function createMatter() {
    setBusy(true); setError(''); setNotice('');
    try {
      const created = await api.create(identity, newName);
      setSelectedId(created.matter_id); setActiveFinding(null); setFile(null);
      setContext(initialContext); setExportId(null);
      await loadList(); setNotice('Matter created. Upload a synthetic DOCX or text-based PDF.');
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }

  async function exportMatter() {
    if (!detail || !selectedId) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.export(identity, selectedId, detail.revision);
      setExportId(result.export_id);
      await refresh();
      await api.download(identity, selectedId, result.export_id);
      setNotice('Synthetic report exported. This does not constitute legal advice.');
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }

  function openFinding(f: Finding) {
    setActiveFinding(f.id);
    setDecisionText(f.edited_text || f.suggestion);
    setReason(f.reason || '');
    if (f.anchor) {
      document.getElementById('block-' + f.anchor.block_id)?.scrollIntoView({behavior: 'smooth', block: 'center'});
    }
  }

  const matter = detail;
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">§</span>
          <div><strong>Legal Intelligence</strong><span className="brand-sub">Evidence-first contract review</span></div>
        </div>
        <div className="topbar-right">
          <span className="demo-pill">LOCAL • SYNTHETIC DATA ONLY</span>
          <label className="identity-field">User
            <input value={identity.user} onChange={e => {
              setIdentity(prev => ({...prev, user: e.target.value}));
              setDetail(null); setSelectedId(null); setExportId(null);
            }} aria-label="Demo user identity" />
          </label>
          <label className="identity-field">Role
            <select value={identity.role} onChange={e => setIdentity(prev => ({...prev, role: e.target.value as Role}))}>
              <option value="reviewer">Simulated reviewer</option>
              <option value="preparer">Simulated preparer</option>
            </select>
          </label>
        </div>
      </header>
      <div className="warning"><strong>Technical prototype — NOT LEGAL ADVICE.</strong> Example rules are not approved by counsel. Demo identities are forgeable. Do not upload client contracts or host this application publicly.</div>
      <div className="body-shell">
        <aside className="sidebar">
          <div className="section-cap">WORKSPACE <span>v0.1</span></div>
          <div className="sidebar-heading"><h2>Matters</h2><span className="counter">{matters.length}</span></div>
          <div className="create-form">
            <label htmlFor="matter-name">New matter name</label>
            <input id="matter-name" value={newName} maxLength={100} onChange={e => setNewName(e.target.value)} />
            <button disabled={busy || !newName.trim()} onClick={() => void createMatter()} className="primary full">+ Create matter</button>
          </div>
          <div className="matter-list" aria-label="Matters">
            {matters.length === 0 && <p className="muted">No demo matters yet.</p>}
            {matters.map(item => <button key={item.id} className={'matter-item ' + (item.id === selectedId ? 'active' : '')}
              onClick={() => { setSelectedId(item.id); setActiveFinding(null); setExportId(null); setContext(initialContext); }}>
              <span className="matter-title">{item.name}</span>
              <span className="matter-meta">{item.status.replaceAll('_',' ')} · r{item.revision}</span>
            </button>)}
          </div>
          <div className="sidebar-foot">
            <div className="mini-logo">LI</div>
            <div>Design reference: <a href="https://github.com/1998x-stack/projects/tree/main/projects/professional/llm-legal-assistant" target="_blank" rel="noreferrer">PRD & architecture</a></div>
          </div>
        </aside>
        <main className="main">
          {error && <div className="feedback error" role="alert"><strong>Action blocked</strong><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
          {notice && <div className="feedback success" role="status">{notice}</div>}
          {!matter ? (
            <div className="welcome">
              <div className="welcome-mark">§</div>
              <div className="eyebrow">REVIEW WORKBENCH</div>
              <h1>Legal work, with<br/>every claim anchored.</h1>
              <p>This prototype connects a source document to synthetic review prompts, explicit human decisions, a simulated approval and a fixed report snapshot.</p>
              <div className="feature-grid">
                <div><span>01</span><strong>Upload & verify</strong><p>Text-native DOCX / PDF; no OCR.</p></div>
                <div><span>02</span><strong>Trace every phrase</strong><p>Document block IDs and exact quotes.</p></div>
                <div><span>03</span><strong>Decide, then export</strong><p>Version-aware simulated review.</p></div>
              </div>
              <p className="muted">Create a matter on the left to begin. Use synthetic documents only.</p>
            </div>
          ) : (
            <>
              <div className="workspace-header">
                <div><div className="eyebrow">MATTER / {matter.matter_id.slice(0, 12)}</div>
                  <h1>{matter.name}</h1>
                  <div className="metadata"><span>{matter.status.replaceAll('_',' ')}</span><span>Revision {matter.revision}</span><span>{matter.playbook}</span></div>
                </div>
                <button className="secondary" onClick={() => void refresh()} disabled={busy}>↻ Refresh</button>
              </div>

              {!matter.document_version_id && (
                <section className="panel intake">
                  <div className="panel-label">STEP 01 / UPLOAD</div>
                  <h2>Start with a source document</h2>
                  <p>English mutual B2B NDA, explicit New York governing-law clause, DOCX or text PDF. Max 10 MB. This upload is stored unencrypted in a local demo database.</p>
                  <input aria-label="Select synthetic NDA document" type="file" accept=".docx,.pdf" onChange={e => setFile(e.target.files?.[0] || null)} />
                  <button className="primary" disabled={busy || !file}
                    onClick={() => void perform('Upload', async () => {
                      if (!selectedId || !file) return;
                      await api.upload(identity, selectedId, file);
                    })}>Upload synthetic document</button>
                </section>
              )}

              {matter.document_version_id && !matter.analysis_id && (
                <section className="panel intake">
                  <div className="panel-label">STEP 02 / SCOPE GATE</div>
                  <h2>Confirm the review scope</h2>
                  <p>These declarations are checked against extracted text. Selecting New York here does not override a conflicting clause in the document.</p>
                  <div className="form-grid">
                    <label>Contract type<input value="Mutual NDA only" readOnly /></label>
                    <label>Language<input value="English only" readOnly /></label>
                    <label>Governing law<input value="NY (document must explicitly confirm)" readOnly /></label>
                    <label>Client perspective
                      <select value={context.client_role} onChange={e => setContext({...context,client_role:e.target.value as ClientRole})}>
                        <option value="both">Both</option><option value="receiving">Receiving</option><option value="disclosing">Disclosing</option>
                      </select>
                    </label>
                    <label>Risk preference
                      <select value={context.risk_posture} onChange={e => setContext({...context,risk_posture:e.target.value as RiskPosture})}>
                        <option value="balanced">Balanced</option><option value="conservative">Conservative</option><option value="fast">Fast</option>
                      </select>
                    </label>
                    <label className="wide">Purpose
                      <textarea rows={2} maxLength={500} value={context.purpose} onChange={e => setContext({...context,purpose:e.target.value})} />
                    </label>
                  </div>
                  <div className="button-row">
                    {!matter.context &&
                      <button className="primary" disabled={busy} onClick={() => void perform('Scope verification',
                        () => api.context(identity, matter.matter_id, context, matter.revision))}>Verify scope</button>}
                    {matter.context && <button className="primary" disabled={busy} onClick={() => void perform('Synthetic analysis',
                      () => api.analyze(identity, matter.matter_id, matter.revision))}>Run synthetic review checks</button>}
                  </div>
                  {matter.context && <div className="inline-ok">Scope accepted for this technical demo. No legal assessment has occurred yet.</div>}
                </section>
              )}

              {matter.analysis_id && (
                <div className="review-shell">
                  <div className="review-top">
                    <div className="panel-label">STEP 03 / EVIDENCE REVIEW</div>
                    <div className="review-stats"><span>{matter.findings.length} prompts</span><span>{pending} pending</span><span>{matter.coverage.length}/3 rule checks</span></div>
                  </div>
                  <div className="review-grid">
                    <section className="pane source-pane" aria-label="Original document">
                      <div className="pane-head"><div><h2>Source text</h2><small>Blocks from current document version</small></div><span className="pane-tag">{matter.blocks.length} blocks</span></div>
                      <div className="pane-scroll">
                        {matter.blocks.map(block => <article id={'block-' + block.block_id} key={block.block_id}
                          className={'source-block ' + (currentFinding?.anchor?.block_id === block.block_id ? 'source-selected' : '')}>
                          <div className="block-label">{block.block_id} {block.page ? '/ p.' + block.page : ''}</div>
                          <p>{block.text}</p>
                        </article>)}
                      </div>
                    </section>
                    <section className="pane findings-pane" aria-label="Review queue">
                      <div className="pane-head"><div><h2>Review queue</h2><small>Synthetic checks, not legal findings</small></div><span className="pane-tag">{pending} open</span></div>
                      <div className="coverage"><div className="coverage-title">Rule coverage</div>
                        {matter.coverage.map(c => <div className="coverage-row" key={c.rule_id}><code>{c.rule_id}</code><span>{c.outcome.replaceAll('_',' ')}</span></div>)}
                      </div>
                      <div className="finding-scroll">
                        {matter.findings.length === 0 && <p className="muted empty-findings">No pattern prompts triggered. This does not mean the NDA is risk-free.</p>}
                        {matter.findings.map(f => <button className={'finding-card ' + (activeFinding === f.id ? 'selected' : '')} key={f.id}
                          onClick={() => openFinding(f)}>
                          <div className="finding-head"><span className="finding-rule">{f.rule_id}</span><span className={complete(f) ? 'done' : 'pending'}>{f.decision.replaceAll('_',' ')}</span></div>
                          <strong>{f.title}</strong><small>{f.anchor ? '↗ View exact source' : '∅ Absence check; no fabricated quote'}</small>
                        </button>)}
                      </div>
                    </section>
                    <section className="pane decision-pane" aria-label="Evidence and reviewer decision">
                      <div className="pane-head"><div><h2>Review details</h2><small>Decision is recorded per finding</small></div></div>
                      {!currentFinding ? <div className="empty-detail">Select a review prompt to see evidence, caveats and actions.</div> :
                        <div className="detail-scroll" key={currentFinding.id}>
                          <span className="finding-rule">{currentFinding.rule_id} / {currentFinding.severity}</span>
                          <h3>{currentFinding.title}</h3>
                          <div className="detail-label">SOURCE EVIDENCE</div>
                          <div className="quote">{currentFinding.anchor ?
                            <><span>{currentFinding.anchor.exact_quote}</span><small>Verified extract · {currentFinding.anchor.block_id}</small></> :
                            <><span>No exact quote exists for absence checks.</span><small>Examined only the extracted blocks in the coverage list.</small></>}
                          </div>
                          <div className="detail-label">DEMONSTRATION SUGGESTION</div>
                          <textarea rows={5} value={decisionText} onChange={e => setDecisionText(e.target.value)} aria-label="Proposed review wording" />
                          <label className="detail-label" htmlFor="decision-reason">DECISION REASON</label>
                          <textarea id="decision-reason" rows={2} value={reason} onChange={e => setReason(e.target.value)} placeholder="Required when dismissing a prompt" />
                          <div className="decision-actions">
                            {(['accepted','edited','dismissed','needs_context','escalated'] as const).map(action =>
                              <button key={action} className={action === 'accepted' ? 'primary' : 'secondary'} disabled={busy}
                                onClick={() => void perform(action, () => api.decision(identity, matter.matter_id, currentFinding.id,
                                  { action, edited_text: decisionText, reason }, matter.revision))}>
                                {action.replaceAll('_',' ')}
                              </button>)}
                          </div>
                          <p className="muted small">Rule: {matter.playbook}. No independent legal validity assessment is represented.</p>
                        </div>}
                    </section>
                  </div>
                  <div className="approval-bar">
                    <div><strong>{matter.status === 'EXPORTED' ? 'Demo report created' : matter.status === 'APPROVED' ? 'Simulated approval recorded' : pending ? pending + ' unresolved prompts' : 'Ready for simulated reviewer approval'}</strong>
                      <small>Current document, context and decisions must match the approved snapshot.</small></div>
                    <div className="button-row">
                      <button className="secondary" disabled={busy || !canApprove} onClick={() => {
                        if (window.confirm('This is a simulated review only; it does not verify lawyer qualification. Continue?')) {
                          void perform('Simulated approval', () => api.approve(identity, matter.matter_id, matter.revision));
                        }
                      }}>Record simulated approval</button>
                      <button className="primary" disabled={busy || identity.role !== 'reviewer' || !['APPROVED','EXPORTED'].includes(matter.status)}
                        onClick={() => void exportMatter()}>Export report (DOCX)</button>
                      {exportId && <button className="secondary" disabled={busy}
                        onClick={() => void perform('Download', () => api.download(identity, matter.matter_id, exportId))}>Download again</button>}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
