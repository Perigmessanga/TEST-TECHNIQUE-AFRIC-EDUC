import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { QRCodeSVG } from 'qrcode.react'

const CameraScanner = lazy(() => import('./CameraScanner'))

type Role = 'agent' | 'responsable' | 'parent'
type Row = {
  [key: string]: unknown
  id?: number
  student_id?: number
  parent_id?: number
  accepted?: number
  duplicates?: number
  server_passages?: number | null
  point_id?: number
  local_event_id?: string
  badge_token?: string
  local_time?: string
  device_id?: string
  local_state?: 'pending' | 'rejected'
  rejection?: string
  name?: string
  role?: Role
  authenticated?: boolean
  password_change_required?: boolean
  first_name?: string
  last_name?: string
  email?: string
  detail?: string
  created_parents?: number
  reused_parents?: number
  linked_children?: number
  credentials?: { username: string; temporary_password: string }[]
  label?: string
  type?: string
  token?: string
  expires_at?: number
  serial?: string
  class_name?: string
  establishment?: string
  badge_state?: string
  state?: string
  student?: string
  username?: string
  point?: string
  issued_at?: string
  server_time?: string
  status?: string
  start_time?: string
  end_time?: string
  days?: string
  date?: string
  kind?: string
  sequence?: number
  parent?: string
  text?: string
  reason?: string
  created_at?: string
  passage_id?: number | null
  origin?: string
  counts?: Record<string, number>
  accepted_events?: string[]
  duplicate_events?: string[]
  rejected?: Row[]
  parents?: Row[]
  links?: Row[]
  recent?: Row[]
  passages?: Row[]
  anomalies?: Row[]
}
type QueueItem = {
  local_event_id: string
  point_id: number
  local_time: string
  device_id: string
  badge_token: string
  local_state?: 'pending' | 'rejected'
  rejection?: string
}

const QUEUE = 'passage-offline-queue-v1'

async function api<T = Row>(path: string, options: RequestInit = {}): Promise<T> {
  const csrfToken = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=').slice(1).join('=')
  const response = await fetch(path, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRFToken': decodeURIComponent(csrfToken) } : {}),
      ...(options.headers || {}),
    },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    throw new Error(typeof detail === 'string' ? detail : 'La requête a échoué. Vérifiez le serveur et réessayez.')
  }
  return data as T
}

function formValues(form: HTMLFormElement): Record<string, string> {
  return Object.fromEntries([...new FormData(form).entries()].map(([key, value]) => [key, String(value)]))
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className="flex items-center gap-3"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[#155eef] text-xl font-black text-white shadow-lg shadow-blue-200">P</div>{!compact && <div><p className="font-black leading-none text-slate-900">PASSAGE</p><p className="mt-1 text-[9px] font-black tracking-[0.18em] text-slate-400">SMART SCHOOL ATTENDANCE</p></div>}</div>
}

function Card({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode }) {
  return <section className="rounded-2xl border border-slate-200/80 bg-white shadow-[0_10px_30px_rgba(15,23,42,.05)]"><div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4"><div><h2 className="text-base font-black text-slate-900">{title}</h2>{subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}</div>{action}</div><div className="p-5">{children}</div></section>
}

function Button({ children, onClick, variant = 'primary', type = 'button', disabled = false }: { children: ReactNode; onClick?: () => void; variant?: 'primary' | 'secondary' | 'danger'; type?: 'button' | 'submit'; disabled?: boolean }) {
  const style = variant === 'primary' ? 'bg-[#155eef] text-white hover:bg-blue-700' : variant === 'danger' ? 'bg-red-50 text-red-700 hover:bg-red-100' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
  return <button type={type} onClick={onClick} disabled={disabled} className={`rounded-xl px-4 py-2.5 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-50 ${style}`}>{children}</button>
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-xs font-black text-slate-600">{label}<div className="mt-1.5">{children}</div></label>
}

const inputClass = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-50'

export default function Dashboard() {
  const [role, setRole] = useState<Role | null>(null)
  const [name, setName] = useState('')
  const [passwordChangeRequired, setPasswordChangeRequired] = useState(false)
  const [error, setError] = useState('')
  const [online, setOnline] = useState(navigator.onLine)
  const [queue, setQueue] = useState<QueueItem[]>(() => {
    try { return JSON.parse(localStorage.getItem(QUEUE) || '[]') as QueueItem[] } catch { return [] }
  })

  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    api('/api/csrf/').catch(() => undefined).then(() => api('/api/me/')).then((data: Row) => {
      if (data.authenticated !== false && data.role) {
        setRole(data.role)
        setName(data.name || '')
        setPasswordChangeRequired(data.password_change_required === true)
      }
    }).catch(() => undefined)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])

  useEffect(() => { localStorage.setItem(QUEUE, JSON.stringify(queue)) }, [queue])

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const form = new FormData(event.currentTarget)
    try {
      await api('/api/csrf/')
      const data = await api<Row>('/api/login/', { method: 'POST', body: JSON.stringify({ login: form.get('login'), password: form.get('password') }) })
      if (!data.role) throw new Error('Rôle manquant dans la réponse du serveur.')
      setRole(data.role)
      setName(data.name || '')
      setPasswordChangeRequired(data.password_change_required === true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Connexion impossible')
    }
  }

  async function logout() {
    try { await api('/api/logout/', { method: 'POST' }) } finally { setRole(null); setName(''); setPasswordChangeRequired(false) }
  }

  if (!role) {
    return <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top_left,#eef5ff,transparent_38%),#f8fafc] p-5"><section className="w-full max-w-md rounded-[28px] border border-white bg-white p-8 shadow-[0_24px_70px_rgba(15,23,42,.12)]"><Brand /><div className="mt-9"><p className="text-xs font-black uppercase tracking-[0.18em] text-[#155eef]">Portail sécurisé</p><h1 className="mt-2 text-3xl font-black text-slate-950">Connexion</h1><p className="mt-2 text-sm text-slate-500">Accès agent, responsable ou parent</p></div><form onSubmit={login} className="mt-7 space-y-4"><Field label="Identifiant"><input name="login" autoComplete="username" required className={inputClass} /></Field><Field label="Mot de passe"><input name="password" type="password" minLength={8} autoComplete="current-password" required className={inputClass} /></Field>{error && <p role="alert" className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</p>}<button className="w-full rounded-xl bg-[#155eef] py-3.5 font-black text-white shadow-lg shadow-blue-200 transition hover:bg-blue-700">Se connecter</button></form></section></main>
  }

  if (passwordChangeRequired) {
    return <PasswordChangeScreen onChanged={() => setPasswordChangeRequired(false)} />
  }

  return <div className="min-h-screen bg-[#f4f7fb] text-slate-900"><header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur"><div className="mx-auto flex h-[76px] max-w-[1320px] items-center px-5"><Brand /><div className="ml-auto flex items-center gap-3"><span className={`rounded-full px-3 py-1.5 text-xs font-black ${online ? 'bg-emerald-50 text-emerald-700' : 'bg-orange-50 text-orange-700'}`}>{online ? 'En ligne' : 'Hors ligne'}</span><Button variant="secondary" onClick={logout}>Déconnexion</Button></div></div></header><main className="mx-auto max-w-[1320px] px-5 py-7"><div className="mb-6"><p className="text-xs font-black uppercase tracking-[0.16em] text-[#155eef]">Espace {role}</p><h1 className="mt-1 text-2xl font-black">Bonjour, {name}</h1></div>{role === 'agent' && <AgentView online={online} queue={queue} setQueue={setQueue} />}{role === 'responsable' && <ResponsibleView />}{role === 'parent' && <ParentView />}</main></div>
}

function AgentView({ online, queue, setQueue }: { online: boolean; queue: QueueItem[]; setQueue: (next: QueueItem[] | ((current: QueueItem[]) => QueueItem[])) => void }) {
  const [points, setPoints] = useState<Row[]>([])
  const [point, setPoint] = useState('')
  const [token, setToken] = useState('')
  const [status, setStatus] = useState('Prêt à scanner')
  const [syncInfo, setSyncInfo] = useState<Row | null>(null)
  const [camera, setCamera] = useState(false)
  const pendingRef = useRef(queue)
  useEffect(() => { pendingRef.current = queue }, [queue])

  const addScan = useCallback((rawToken: string) => {
    const scannedToken = rawToken.trim()
    if (scannedToken.length < 20) { setStatus('QR invalide : aucun jeton de badge reconnu.'); return }
    if (!point) { setStatus('Sélectionnez un point de contrôle avant le scan.'); return }
    const deviceId = localStorage.getItem('passage-device-id') || crypto.randomUUID()
    localStorage.setItem('passage-device-id', deviceId)
    setQueue((current) => {
      if (current.some((item) => item.badge_token === scannedToken && item.local_state !== 'rejected')) {
        setStatus('Ce QR est déjà dans la file de cet appareil.')
        return current
      }
      setStatus(online ? 'Passage mis en file, synchronisation en cours…' : 'Passage enregistré hors ligne.')
      return [...current, {
        point_id: Number(point),
        local_time: new Date().toISOString(),
        device_id: deviceId,
        badge_token: scannedToken,
        local_event_id: crypto.randomUUID(),
        local_state: 'pending',
      }]
    })
    setToken('')
  }, [online, point, setQueue])

  useEffect(() => {
    api<Row[]>('/api/control-points/').then((data) => { setPoints(data); setPoint(data[0]?.id?.toString() || '') }).catch(() => setStatus('Impossible de charger les points de contrôle.'))
    api('/api/sync/status/').then(setSyncInfo).catch(() => undefined)
  }, [])

  const sync = useCallback(async () => {
    const pending = pendingRef.current.filter((item) => item.local_state !== 'rejected')
    if (!navigator.onLine || pending.length === 0) return
    try {
      setStatus('Synchronisation en cours…')
      const result = await api<Row>('/api/sync/', { method: 'POST', body: JSON.stringify({ items: pending.slice(0, 100) }) })
      const accepted = new Set<string>([...(result.accepted_events || []), ...(result.duplicate_events || [])])
      const rejected = new Map<string, string>((result.rejected || []).flatMap((item) =>
        typeof item.event === 'string' && typeof item.reason === 'string'
          ? [[item.event, item.reason] as [string, string]]
          : [],
      ))
      setQueue((current) => current.flatMap((item) => {
        if (accepted.has(item.local_event_id)) return []
        if (rejected.has(item.local_event_id)) return [{ ...item, local_state: 'rejected' as const, rejection: rejected.get(item.local_event_id) }]
        return [item]
      }))
      setStatus(`${result.accepted} passage(s) synchronisé(s), ${result.duplicates} doublon(s) évité(s).`)
      const deviceId = localStorage.getItem('passage-device-id') || ''
      setSyncInfo(await api(`/api/sync/status/?device_id=${encodeURIComponent(deviceId)}`))
    } catch (reason) {
      setStatus(reason instanceof Error ? reason.message : 'Synchronisation impossible')
    }
  }, [setQueue])

  useEffect(() => {
    if (!online || !queue.some((item) => item.local_state !== 'rejected')) return
    const timer = window.setTimeout(() => { void sync() }, 0)
    return () => window.clearTimeout(timer)
  }, [online, queue, sync])
  useEffect(() => {
    const onOnline = () => { void sync() }
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [sync])

  return <div className="grid gap-5 lg:grid-cols-[1.15fr_.85fr]"><Card title="Scanner un badge" subtitle="Les événements sont conservés localement en cas de coupure réseau" action={<Button variant="secondary" onClick={() => setCamera((value) => !value)}>{camera ? 'Fermer caméra' : 'Ouvrir caméra'}</Button>}><div className="grid gap-4 sm:grid-cols-2"><Field label="Point de contrôle"><select value={point} onChange={(event) => setPoint(event.target.value)} className={inputClass}><option value="">Sélectionner</option>{points.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></Field><Field label="Saisie manuelle du jeton QR"><input value={token} onChange={(event) => setToken(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') addScan(token) }} placeholder="Disponible si la caméra ne fonctionne pas" className={inputClass} /></Field></div>{camera && <div className="mt-5"><Suspense fallback={<p className="text-sm text-slate-500">Chargement du lecteur caméra…</p>}><CameraScanner onDecode={addScan} /></Suspense></div>}<Button onClick={() => addScan(token)}>Enregistrer le passage</Button><p role="status" className="mt-3 text-sm text-slate-600">{status}</p></Card><Card title="Synchronisation" subtitle="État de la file sur cet appareil"><div className="flex items-center justify-between"><div><p className="text-xs text-slate-500">À synchroniser</p><p className="mt-1 text-2xl font-black text-[#155eef]">{queue.filter((item) => item.local_state !== 'rejected').length}</p></div><div className="text-right"><p className="text-xs text-slate-500">À corriger</p><p className="mt-1 text-2xl font-black text-red-600">{queue.filter((item) => item.local_state === 'rejected').length}</p></div></div><div className="mt-4 max-h-56 space-y-2 overflow-auto">{queue.map((item) => <div key={item.local_event_id} className="flex items-center justify-between gap-2 rounded-xl bg-slate-50 px-3 py-2.5 text-xs"><span>Point {item.point_id} · {new Date(item.local_time).toLocaleTimeString('fr-FR')}</span><span className={`rounded-full px-2 py-1 font-bold ${item.local_state === 'rejected' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>{item.rejection || 'En attente'}</span></div>)}</div><div className="mt-4 flex gap-2"><Button onClick={() => void sync()} disabled={!online}>Synchroniser</Button><Button variant="secondary" onClick={() => setQueue((items) => items.filter((item) => item.local_state !== 'rejected'))}>Effacer rejets</Button></div><p className="mt-3 text-xs text-slate-500">{syncInfo?.recent?.length || 0} passage(s) récents connus du serveur.</p></Card></div>
}

function ResponsibleView() {
  const [tab, setTab] = useState('overview')
  const [students, setStudents] = useState<Row[]>([])
  const [badges, setBadges] = useState<Row[]>([])
  const [points, setPoints] = useState<Row[]>([])
  const [routes, setRoutes] = useState<Row[]>([])
  const [exceptions, setExceptions] = useState<Row[]>([])
  const [parents, setParents] = useState<Row[]>([])
  const [parentLinks, setParentLinks] = useState<Row[]>([])
  const [anomalies, setAnomalies] = useState<Row[]>([])
  const [passages, setPassages] = useState<Row[]>([])
  const [messages, setMessages] = useState<Row[]>([])
  const [summary, setSummary] = useState<Row | null>(null)
  const [summaryClass, setSummaryClass] = useState('6eA')
  const [summaryDate, setSummaryDate] = useState(new Date().toISOString().slice(0, 10))
  const [notice, setNotice] = useState('')
  const [qr, setQr] = useState<Row | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [studentData, badgeData, pointData, routeData, exceptionData, parentData, anomalyData, passageData, messageData] = await Promise.all([
        api<Row[]>('/api/students/'), api<Row[]>('/api/badges/'), api<Row[]>('/api/control-points/manage/'),
        api<Row[]>('/api/routes/'), api<Row[]>('/api/exceptions/'), api<Row>('/api/parent-links/'), api<Row[]>('/api/anomalies/'), api<Row[]>('/api/passages/'), api<Row[]>('/api/messages/'),
      ])
      setStudents(studentData); setBadges(badgeData); setPoints(pointData); setRoutes(routeData)
      setExceptions(exceptionData); setParents(parentData.parents || []); setParentLinks(parentData.links || [])
      setAnomalies(anomalyData); setPassages(passageData); setMessages(messageData)
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Chargement des données impossible') }
  }, [])
  useEffect(() => {
    const timer = window.setTimeout(() => { void load() }, 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function change(method: string, path: string, body: Row | undefined, success: string) {
    setBusy(true); setNotice('')
    try { await api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }); setNotice(success); await load(); return true }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Opération impossible'); return false }
    finally { setBusy(false) }
  }

  const submit = (path: string, body: Row, success: string) => change('POST', path, body, success)

  async function studentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const ok = await submit('/api/students/', { name: String(form.get('name') || ''), class_name: String(form.get('class_name') || '') }, 'Élève créé avec son badge actif.')
    if (ok) event.currentTarget.reset()
  }

  async function pointSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const ok = await submit('/api/control-points/manage/', { label: String(form.get('label') || ''), type: String(form.get('type') || '') }, 'Point de contrôle créé.')
    if (ok) event.currentTarget.reset()
  }

  async function routeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = formValues(event.currentTarget)
    const ok = await submit('/api/routes/manage/', body, 'Itinéraire ajouté.')
    if (ok) event.currentTarget.reset()
  }

  async function exceptionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = formValues(event.currentTarget)
    const ok = await submit('/api/exceptions/', body, 'Exception de journée enregistrée.')
    if (ok) event.currentTarget.reset()
  }

  async function parentLinkSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = formValues(event.currentTarget)
    const ok = await submit('/api/parent-links/', body, 'Lien parent-enfant enregistré.')
    if (ok) event.currentTarget.reset()
  }

  async function tokenFor(student: Row) {
    try { const data = await api<Row>(`/api/badges/${student.id}/token/`, { method: 'POST', body: '{}' }); setQr({ ...data, student: student.name }) }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : 'QR impossible à générer') }
  }

  async function badgeAction(badge: Row, action: string) {
    if (!window.confirm(`Confirmer l’action « ${action} » pour ${badge.student} ?`)) return
    await submit(`/api/badges/${badge.id}/action/`, { action }, action === 'reissue' ? 'Badge réémis; l’ancien est révoqué.' : 'État du badge mis à jour.')
  }

  async function detectAnomalies() {
    if (await submit('/api/anomalies/detect/', {}, 'Détection terminée.')) await load()
  }

  async function generateSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    try { setSummary(await api<Row>('/api/summaries/', { method: 'POST', body: JSON.stringify({ class_name: summaryClass, date: summaryDate }) })) }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Synthèse indisponible') }
    finally { setBusy(false) }
  }

  const tabs = [
    ['overview', 'Vue générale'], ['students', 'Élèves'], ['badges', 'Badges'], ['routes', 'Points & itinéraires'],
    ['passages', 'Passages'], ['anomalies', 'Anomalies'], ['messages', 'Notifications'], ['summary', 'Synthèse'],
  ]
  return <div>
    <nav className="mb-5 flex gap-2 overflow-auto rounded-2xl border border-slate-200 bg-white p-2">{tabs.map(([id, label]) => <button key={id} onClick={() => setTab(id)} className={`whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-black ${tab === id ? 'bg-[#155eef] text-white shadow-md shadow-blue-100' : 'text-slate-600 hover:bg-slate-50'}`}>{label}</button>)}</nav>
    {notice && <p role="status" className="mb-4 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">{notice}</p>}
    {tab === 'students' && <ParentAccountsCard students={students} parents={parents} onChanged={load} />}
    {tab === 'overview' && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Stat label="Élèves" value={students.length} /><Stat label="Badges actifs" value={badges.filter((badge) => badge.state === 'actif').length} /><Stat label="Passages" value={passages.length} /><Stat label="Anomalies ouvertes" value={anomalies.filter((item) => item.state === 'nouvelle').length} /><div className="sm:col-span-2 lg:col-span-4"><Card title="Actions rapides"><div className="flex flex-wrap gap-2"><Button onClick={() => void detectAnomalies()}>Détecter les absences échues</Button><Button variant="secondary" onClick={() => { setTab('students') }}>Ajouter un élève</Button><Button variant="secondary" onClick={() => { setTab('summary') }}>Générer la synthèse</Button></div></Card></div></div>}
    {tab === 'students' && <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]"><Card title="Inscrire un élève" subtitle="Un badge actif est créé automatiquement"><form onSubmit={studentSubmit} className="space-y-3"><Field label="Nom complet"><input name="name" required minLength={2} className={inputClass} /></Field><Field label="Classe"><input name="class_name" required className={inputClass} /></Field><Button type="submit" disabled={busy}>Créer l’élève</Button></form></Card><Card title="Élèves et classes"><DataTable headers={['Nom', 'Classe', 'Établissement', 'Badge', 'Actions']} rows={students.map((student) => [student.name, student.class_name, student.establishment, student.badge_state, <Button key={student.id} variant="secondary" onClick={() => { const name = window.prompt('Nom complet', student.name); const className = name === null ? null : window.prompt('Classe', student.class_name); if (name && className) void change('PATCH', `/api/students/${student.id}/`, { name, class_name: className }, 'Élève modifié.') }}>Modifier</Button>])} /></Card><Card title="Rattacher un enfant à un parent"><form onSubmit={parentLinkSubmit} className="grid gap-3 sm:grid-cols-3"><Field label="Compte parent"><select name="parent_id" required className={inputClass}>{parents.map((parent) => <option key={parent.id} value={parent.id}>{parent.username}</option>)}</select></Field><Field label="Élève"><select name="student_id" required className={inputClass}>{students.map((student) => <option key={student.id} value={student.id}>{student.name}</option>)}</select></Field><div className="self-end"><Button type="submit" disabled={busy}>Rattacher</Button></div></form><DataTable headers={['Parent', 'Enfant', 'Action']} rows={parentLinks.map((link) => [link.parent, link.student, <Button key={link.id} variant="danger" onClick={() => void change('DELETE', `/api/parent-links/${link.id}/`, undefined, 'Rattachement supprimé.')}>Retirer</Button>])} /></Card></div>}
    {tab === 'badges' && <Card title="Cycle de vie des badges" subtitle="Jeton QR signé, usage unique et expiration configurée côté serveur"><DataTable headers={['Élève', 'État', 'Émis le', 'Actions']} rows={badges.map((badge) => [badge.student, badge.state, new Date(badge.issued_at || '').toLocaleDateString('fr-FR'), <div className="flex flex-wrap gap-1" key={badge.id}>{badge.state === 'actif' && <><Button onClick={() => void tokenFor({ id: badge.student_id, name: badge.student })}>QR provisoire</Button><Button variant="secondary" onClick={() => void badgeAction(badge, 'reissue')}>Réémettre</Button><Button variant="danger" onClick={() => void badgeAction(badge, 'suspend')}>Suspendre</Button></>}{badge.state === 'suspendu' && <Button onClick={() => void badgeAction(badge, 'activate')}>Réactiver</Button>}{badge.state !== 'révoqué' && badge.state !== 'actif' && <Button variant="danger" onClick={() => void badgeAction(badge, 'revoke')}>Révoquer</Button>}</div>])} /></Card>}
    {tab === 'routes' && <div className="grid gap-5 lg:grid-cols-2"><Card title="Créer un point de contrôle"><form onSubmit={pointSubmit} className="grid gap-3 sm:grid-cols-3"><Field label="Libellé"><input name="label" required className={inputClass} /></Field><Field label="Type"><select name="type" className={inputClass}><option value="portail">Portail</option><option value="autobus">Autobus</option></select></Field><div className="self-end"><Button type="submit" disabled={busy}>Ajouter</Button></div></form><div className="mt-4 space-y-2">{points.map((point) => <div key={point.id} className="flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm"><span>{point.label} · {point.type}</span><div className="flex gap-2"><Button variant="secondary" onClick={() => { const label = window.prompt('Libellé', point.label); if (label) void change('PATCH', `/api/control-points/manage/${point.id}/`, { label }, 'Point modifié.') }}>Modifier</Button><Button variant="danger" onClick={() => void change('DELETE', `/api/control-points/manage/${point.id}/`, undefined, 'Point supprimé.')}>Supprimer</Button></div></div>)}</div></Card><Card title="Affecter un itinéraire"><form onSubmit={routeSubmit} className="grid gap-3 sm:grid-cols-2"><Field label="Élève"><select name="student_id" required className={inputClass}>{students.map((student) => <option key={student.id} value={student.id}>{student.name}</option>)}</select></Field><Field label="Point"><select name="point_id" required className={inputClass}>{points.map((point) => <option key={point.id} value={point.id}>{point.label}</option>)}</select></Field><Field label="Ordre"><input name="sequence" type="number" min="1" defaultValue="1" className={inputClass} /></Field><Field label="Jours (ex. LMMJV)"><input name="days" defaultValue="LMMJV" className={inputClass} /></Field><Field label="Début"><input name="start_time" type="time" defaultValue="07:00" className={inputClass} /></Field><Field label="Fin"><input name="end_time" type="time" defaultValue="07:45" className={inputClass} /></Field><Button type="submit" disabled={busy}>Enregistrer l’itinéraire</Button></form><DataTable headers={['Élève', 'Point', 'Fenêtre', 'Jours', 'Action']} rows={routes.map((route) => [route.student, route.point, `${route.start_time}–${route.end_time}`, route.days, <Button key={route.id} variant="danger" onClick={() => void change('DELETE', `/api/routes/manage/${route.id}/`, undefined, 'Itinéraire supprimé.')}>Supprimer</Button>])} /></Card><Card title="Déclarer une exception"><form onSubmit={exceptionSubmit} className="grid gap-3 sm:grid-cols-3"><Field label="Élève"><select name="student_id" required className={inputClass}>{students.map((student) => <option key={student.id} value={student.id}>{student.name}</option>)}</select></Field><Field label="Date"><input name="date" type="date" required className={inputClass} /></Field><Field label="Motif"><select name="kind" className={inputClass}><option value="absence_justifiée">Absence justifiée</option><option value="jour_ferie">Jour férié</option><option value="sortie_autorisee">Sortie autorisée</option></select></Field><Button type="submit" disabled={busy}>Ajouter l’exception</Button></form><DataTable headers={['Élève', 'Date', 'Motif']} rows={exceptions.map((item) => [item.student, item.date, item.kind])} /></Card></div>}
    {tab === 'passages' && <Card title="Passages enregistrés"><DataTable headers={['Élève', 'Point', 'Heure appareil', 'Heure serveur', 'Appareil', 'État']} rows={passages.map((passage) => [passage.student, passage.point, new Date(passage.local_time || '').toLocaleString('fr-FR'), new Date(passage.server_time || '').toLocaleString('fr-FR'), passage.device_id, passage.state])} /></Card>}
    {tab === 'anomalies' && <Card title="Anomalies" subtitle="Détection manuelle des absences échues; les scans génèrent les autres anomalies"><div className="mb-4 flex gap-2"><Button onClick={() => void detectAnomalies()} disabled={busy}>Détecter les absences</Button></div><DataTable headers={['Élève', 'Type', 'Date', 'État', 'Actions']} rows={anomalies.map((anomaly) => [anomaly.student, anomaly.type, anomaly.date, anomaly.state, <div key={anomaly.id} className="flex gap-2"><Button onClick={() => void submit(`/api/anomalies/${anomaly.id}/state/`, { state: 'traitée' }, 'Anomalie traitée.')}>Traiter</Button><Button variant="secondary" onClick={() => void submit(`/api/anomalies/${anomaly.id}/notify/`, {}, 'Notification ajoutée à la file.')}>Notifier le parent</Button></div>])} /></Card>}
    {tab === 'messages' && <Card title="Notifications sortantes" subtitle="« En attente » signifie enregistrée mais pas encore livrée"><DataTable headers={['Parent', 'Élève', 'Message', 'État', 'Motif']} rows={messages.map((message) => [message.parent, message.student, message.text, message.state, message.reason || '—'])} /></Card>}
    {tab === 'summary' && <Card title="Synthèse quotidienne assistée"><form onSubmit={generateSummary} className="mb-5 flex flex-wrap items-end gap-3"><Field label="Classe"><input value={summaryClass} onChange={(event) => setSummaryClass(event.target.value)} required className={inputClass} /></Field><Field label="Jour"><input type="date" value={summaryDate} onChange={(event) => setSummaryDate(event.target.value)} required className={inputClass} /></Field><Button type="submit" disabled={busy}>Calculer la synthèse</Button></form>{summary ? <div className="rounded-xl border-l-4 border-[#155eef] bg-blue-50 p-5"><p className="font-bold">{summary.text}</p><p className="mt-2 text-xs text-slate-500">Origine : {summary.origin} · Tous les nombres proviennent des passages et itinéraires enregistrés.</p><div className="mt-3 flex flex-wrap gap-2">{Object.entries(summary.counts || {}).map(([key, value]) => <span key={key} className="rounded-full bg-white px-3 py-1 text-xs font-bold">{key}: {String(value)}</span>)}</div></div> : <p className="text-sm text-slate-500">Choisissez une classe et une date pour calculer les indicateurs.</p>}</Card>}
    {qr && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/60 p-4" role="dialog" aria-modal="true"><div className="w-full max-w-sm rounded-2xl bg-white p-6 text-center shadow-2xl"><h2 className="text-lg font-black">QR temporaire · {qr.student}</h2><p className="my-4 text-xs text-slate-500">À présenter à l’agent. Jeton à usage unique, expiration affichée en heure locale.</p><div className="inline-block rounded-xl border p-3"><QRCodeSVG value={qr.token || ''} size={230} /></div><p className="mt-3 text-xs text-slate-500">Expire à {new Date((qr.expires_at || 0) * 1000).toLocaleTimeString('fr-FR')}</p><Button variant="secondary" onClick={() => setQr(null)}>Fermer</Button></div></div>}
  </div>
}

function Stat({ label, value }: { label: string; value: number }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-black text-slate-500">{label}</p><p className="mt-2 text-3xl font-black text-slate-950">{value}</p></section>
}

function parseCsv(source: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let value = ''
  let quoted = false
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index]
    if (character === '"') {
      if (quoted && source[index + 1] === '"') {
        value += '"'
        index += 1
      } else {
        quoted = !quoted
      }
    } else if (character === ',' && !quoted) {
      row.push(value.trim())
      value = ''
    } else if ((character === '\n' || character === '\r') && !quoted) {
      if (character === '\r' && source[index + 1] === '\n') index += 1
      row.push(value.trim())
      if (row.some(Boolean)) rows.push(row)
      row = []
      value = ''
    } else {
      value += character
    }
  }
  if (quoted) throw new Error('Le fichier CSV contient un guillemet non fermé.')
  row.push(value.trim())
  if (row.some(Boolean)) rows.push(row)
  return rows
}

function ParentAccountsCard({ students, parents, onChanged }: { students: Row[]; parents: Row[]; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [credentials, setCredentials] = useState<{ username: string; temporary_password: string }[]>([])
  const [summary, setSummary] = useState('')

  async function importRows(rows: Row[]) {
    setBusy(true)
    setMessage('')
    setCredentials([])
    setSummary('')
    try {
      const result = await api<Row>('/api/parents/import/', {
        method: 'POST',
        body: JSON.stringify({ rows }),
      })
      setCredentials(result.credentials || [])
      setSummary(`${result.created_parents || 0} nouveau(x) compte(s), ${result.reused_parents || 0} compte(s) existant(s) réutilisé(s), ${result.linked_children || 0} rattachement(s) traité(s).`)
      setMessage(result.detail || 'Import terminé.')
      await onChanged()
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Import impossible.')
    } finally {
      setBusy(false)
    }
  }

  async function resetParentPassword(parent: Row) {
    const username = String(parent.username || '')
    if (!window.confirm(`Réinitialiser le mot de passe de ${username} ? Son prochain accès exigera un changement de mot de passe.`)) return
    setBusy(true)
    setMessage('')
    setCredentials([])
    setSummary('')
    try {
      const result = await api<Row>(`/api/parents/${parent.id}/reset-password/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      if (typeof result.username !== 'string' || typeof result.temporary_password !== 'string') {
        throw new Error('Le serveur n’a pas retourné les nouveaux identifiants.')
      }
      setCredentials([{ username: result.username, temporary_password: result.temporary_password }])
      setSummary(`Mot de passe temporaire réinitialisé pour ${result.username}.`)
      setMessage(result.detail || 'Transmettez le nouveau mot de passe par un canal privé.')
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Réinitialisation impossible.')
    } finally {
      setBusy(false)
    }
  }

  async function createParent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    const studentIds = [...form.querySelectorAll<HTMLSelectElement>('select[name="student_ids"]')[0].selectedOptions]
      .map((option) => Number(option.value))
    if (!studentIds.length) {
      setMessage('Sélectionnez au moins un enfant.')
      return
    }
    const username = String(values.get('parent_username') || '').trim()
    const shared = {
      parent_username: username,
      parent_email: String(values.get('parent_email') || '').trim(),
      first_name: String(values.get('first_name') || '').trim(),
      last_name: String(values.get('last_name') || '').trim(),
    }
    await importRows(studentIds.map((student_id) => ({ ...shared, student_id })))
    form.reset()
  }

  async function uploadCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const file = new FormData(form).get('csv')
    if (!(file instanceof File) || file.size === 0) {
      setMessage('Choisissez un fichier CSV.')
      return
    }
    try {
      const parsed = parseCsv(await file.text())
      const headers = parsed.shift()?.map((header) => header.replace(/^\uFEFF/, '').toLowerCase()) || []
      const required = ['parent_username', 'parent_email', 'first_name', 'last_name', 'student_id']
      if (required.some((header) => !headers.includes(header))) {
        throw new Error(`Colonnes requises : ${required.join(', ')}`)
      }
      const rows = parsed.map((line, index) => {
        const values = Object.fromEntries(headers.map((header, column) => [header, line[column] || '']))
        const studentId = Number(values.student_id)
        if (!values.parent_username?.trim() || !Number.isInteger(studentId) || studentId < 1) {
          throw new Error(`Ligne ${index + 2} : identifiant parent ou élève invalide.`)
        }
        return {
          parent_username: values.parent_username.trim(),
          parent_email: values.parent_email.trim(),
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          student_id: studentId,
        }
      })
      if (!rows.length) throw new Error('Le fichier ne contient aucune ligne de données.')
      await importRows(rows)
      form.reset()
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Lecture du CSV impossible.')
    }
  }

  function downloadCredentials() {
    const escapeCell = (value: string) => `"${value.replace(/"/g, '""')}"`
    const csv = [
      'username,temporary_password',
      ...credentials.map((item) => `${escapeCell(item.username)},${escapeCell(item.temporary_password)}`),
    ].join('\r\n')
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'identifiants-temporaires-parents.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function downloadTemplate() {
    const url = URL.createObjectURL(new Blob([
      'parent_username,parent_email,first_name,last_name,student_id\r\nparent.martin,martin@example.com,Marie,Martin,1\r\n',
    ], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'modele-rattachements-parents.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function downloadStudentRoster() {
    const escapeCell = (value: string) => `"${value.replace(/"/g, '""')}"`
    const csv = [
      'student_id,student_name,class_name',
      ...students.map((student) => [
        String(student.id || ''),
        escapeCell(String(student.name || '')),
        escapeCell(String(student.class_name || '')),
      ].join(',')),
    ].join('\r\n')
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'liste-eleves-passage.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return <div className="mb-5 grid gap-5 lg:grid-cols-2">
    <Card title="Créer un compte parent" subtitle="L’identifiant est le nom d’utilisateur choisi (ex. marie.martin). Le mot de passe est généré au hasard, jamais Test1234, et doit être changé au premier accès.">
      <form onSubmit={createParent} className="grid gap-3 sm:grid-cols-2">
        <Field label="Identifiant de connexion (nom d’utilisateur)"><input name="parent_username" placeholder="ex. marie.martin" required maxLength={150} className={inputClass} /></Field>
        <Field label="E-mail"><input name="parent_email" type="email" className={inputClass} /></Field>
        <Field label="Prénom"><input name="first_name" className={inputClass} /></Field>
        <Field label="Nom"><input name="last_name" className={inputClass} /></Field>
        <Field label="Enfant(s) à rattacher">
          <select name="student_ids" multiple required size={Math.min(Math.max(students.length, 3), 7)} className={inputClass}>
            {students.map((student) => <option key={student.id} value={student.id}>{student.name} · {student.class_name}</option>)}
          </select>
        </Field>
        <div className="self-end"><Button type="submit" disabled={busy || students.length === 0}>Créer et rattacher</Button></div>
      </form>
    </Card>
    <Card title="Import en lot (CSV)" subtitle="Utile pour les grands effectifs; plusieurs lignes peuvent partager le même identifiant parent.">
      <form onSubmit={uploadCsv} className="space-y-3">
        <p className="text-xs leading-5 text-slate-600">Colonnes : <code>parent_username,parent_email,first_name,last_name,student_id</code>. Les parents existants sont réutilisés; leurs mots de passe ne changent pas.</p>
        <input name="csv" type="file" accept=".csv,text/csv" required className={`${inputClass} file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:font-bold file:text-blue-700`} />
        <div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}>Importer le CSV</Button><Button variant="secondary" onClick={downloadTemplate}>Télécharger le modèle</Button><Button variant="secondary" onClick={downloadStudentRoster}>Exporter la liste des élèves</Button></div>
      </form>
    </Card>
    <div className="lg:col-span-2">
      <Card title="Comptes parents existants" subtitle="Un compte déjà existant est réutilisé sans modifier son mot de passe. Réinitialisez-le ici si son mot de passe temporaire a été perdu.">
        <DataTable headers={['Identifiant de connexion', 'Action']} rows={parents.map((parent) => [
          parent.username,
          <Button key={parent.id} variant="secondary" disabled={busy} onClick={() => void resetParentPassword(parent)}>Réinitialiser le mot de passe</Button>,
        ])} />
      </Card>
    </div>
    {(message || credentials.length > 0) && <div className="lg:col-span-2">
      <Card title="Résultat de l'import">
        {summary && <p className="mb-2 font-bold text-slate-800">{summary}</p>}
        {message && <p role="status" className="mb-3 text-sm text-slate-600">{message}</p>}
        {credentials.length > 0 && <>
          <p className="mb-3 rounded-xl bg-amber-50 p-3 text-sm font-semibold text-amber-900">Copiez et transmettez ces mots de passe temporaires par un canal privé. Ils sont affichés une seule fois; le parent devra en choisir un nouveau à sa première connexion.</p>
          <DataTable headers={['Identifiant', 'Mot de passe temporaire']} rows={credentials.map((item) => [item.username, <code key={item.username}>{item.temporary_password}</code>])} />
          <Button onClick={downloadCredentials}>Télécharger les identifiants</Button>
        </>}
      </Card>
    </div>}
  </div>
}

function PasswordChangeScreen({ onChanged }: { onChanged: () => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)
    const form = event.currentTarget
    const values = new FormData(form)
    try {
      await api('/api/password/change/', {
        method: 'POST',
        body: JSON.stringify({
          current_password: values.get('current_password'),
          new_password: values.get('new_password'),
        }),
      })
      onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Changement de mot de passe impossible.')
    } finally {
      setBusy(false)
    }
  }
  return <main className="grid min-h-screen place-items-center bg-slate-50 p-5"><Card title="Sécurisez votre compte" subtitle="Votre compte a été créé avec un mot de passe temporaire. Choisissez un mot de passe personnel d'au moins 12 caractères."><form onSubmit={submit} className="space-y-4"><Field label="Mot de passe temporaire"><input name="current_password" type="password" autoComplete="current-password" required className={inputClass} /></Field><Field label="Nouveau mot de passe"><input name="new_password" type="password" minLength={12} autoComplete="new-password" required className={inputClass} /></Field>{error && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}<Button type="submit" disabled={busy}>Changer le mot de passe</Button></form></Card></main>
}

function DataTable({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return <div className="overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{headers.map((header) => <th key={header} className="border-b border-slate-100 px-3 py-3 text-xs uppercase text-slate-400">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((value, cell) => <td key={cell} className="border-b border-slate-50 px-3 py-3.5 align-top">{value}</td>)}</tr>)}</tbody></table>{rows.length === 0 && <p className="py-8 text-center text-sm text-slate-400">Aucune donnée disponible</p>}</div>
}

function ParentView() {
  const [children, setChildren] = useState<Row[]>([])
  const [messages, setMessages] = useState<Row[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    Promise.all([api<Row[]>('/api/parent/children/'), api<Row[]>('/api/messages/')])
      .then(([childData, messageData]) => { setChildren(childData); setMessages(messageData) })
      .catch((reason) => setError(reason instanceof Error ? reason.message : 'Chargement impossible'))
  }, [])
  return <div className="space-y-5">
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <div className="grid gap-5 lg:grid-cols-2">
      {children.map((child) => {
        const passages = child.passages || []
        const anomalies = child.anomalies || []
        return <Card key={child.id} title={child.name || 'Élève'} subtitle={`${child.class_name || ''} · ${child.establishment || ''}`}>
          <p className="text-xs font-black uppercase text-slate-400">Derniers passages</p>
          <div className="mt-3 space-y-2">
            {passages.map((passage) => <div key={passage.id} className="rounded-xl bg-slate-50 p-3 text-sm">
              <p className="font-bold">{passage.point}</p>
              <p className="mt-1 text-xs text-slate-500">{new Date(passage.server_time || '').toLocaleString('fr-FR')}</p>
            </div>)}
          </div>
          {passages.length === 0 && <p className="mt-2 text-sm text-slate-500">Aucun passage enregistré.</p>}
          <p className="mt-5 text-xs font-black uppercase text-slate-400">Anomalies</p>
          <div className="mt-3 space-y-2">
            {anomalies.map((anomaly) => <div key={anomaly.id} className="rounded-xl border border-orange-100 bg-orange-50 p-3 text-sm">
              <p className="font-bold text-orange-800">{anomaly.type}</p>
              <p className="mt-1 text-xs text-orange-600">{anomaly.date} · {anomaly.state}</p>
            </div>)}
          </div>
        </Card>
      })}
    </div>
    <Card title="Notifications" subtitle="État réel de la file d’envoi">
      <DataTable headers={['Enfant', 'Information', 'Statut', 'Date']} rows={messages.map((message) => [message.student, message.text, message.state, new Date(message.created_at || '').toLocaleString('fr-FR')])} />
    </Card>
  </div>
}
