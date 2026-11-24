import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import './App.css'

const API='http://127.0.0.1:8001'
const QUEUE='passage-offline-queue-v1'
type Role='agent'|'responsable'|'parent'

function App(){
 const [role,setRole]=useState<Role|null>(null)
 const [name,setName]=useState('')
 const [error,setError]=useState('')
 const [online,setOnline]=useState(navigator.onLine)
 const [queue,setQueue]=useState<any[]>(()=>JSON.parse(localStorage.getItem(QUEUE)||'[]'))
 const [points,setPoints]=useState<any[]>([])
 const [point,setPoint]=useState('')
 const [token,setToken]=useState('')
 const [status,setStatus]=useState('')
 const [summary,setSummary]=useState('')

 useEffect(()=>{const up=()=>setOnline(true),down=()=>setOnline(false);window.addEventListener('online',up);window.addEventListener('offline',down);fetch(API+'/api/me/',{credentials:'include'}).then(r=>r.ok?r.json():null).then(d=>{if(d){setRole(d.role);setName(d.name)}}).catch(()=>{});return()=>{window.removeEventListener('online',up);window.removeEventListener('offline',down)}},[])
 useEffect(()=>{localStorage.setItem(QUEUE,JSON.stringify(queue))},[queue])
 useEffect(()=>{if(role==='agent'||role==='responsable')fetch(API+'/api/control-points/',{credentials:'include'}).then(r=>r.json()).then((d:any[])=>{setPoints(d);setPoint(d[0]?.id?.toString()||'')}).catch(()=>{})},[role])

 async function login(e:FormEvent<HTMLFormElement>){e.preventDefault();setError('');const fd=new FormData(e.currentTarget);const r=await fetch(API+'/api/login/',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({login:fd.get('login'),password:fd.get('password')})});const d=await r.json();if(!r.ok){setError(d.detail||'Identifiants invalides');return}setRole(d.role);setName(d.name)}
 async function logout(){await fetch(API+'/api/logout/',{method:'POST',credentials:'include'});setRole(null)}
 function addScan(){if(token.length<20){setStatus('Jeton temporaire requis.');return}const item={point_id:Number(point),local_time:new Date().toISOString(),device_id:localStorage.deviceId||(localStorage.deviceId=crypto.randomUUID()),badge_token:token,local_event_id:crypto.randomUUID()};setQueue(v=>[...v,item]);setToken('');setStatus('Passage conservé hors ligne.')}
 async function sync(){if(!queue.length)return;const r=await fetch(API+'/api/sync/',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({items:queue})});if(!r.ok)return;const d=await r.json();const handled=new Set([...d.accepted_events,...d.duplicate_events,...d.rejected.map((x:any)=>x.event)]);setQueue(v=>v.filter(x=>!handled.has(x.local_event_id)));setStatus(`${d.accepted} accepté · ${d.duplicates} doublon(s) · ${d.rejected.length} rejet(s)`)}
 async function generate(){const r=await fetch(API+'/api/summaries/',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({class_name:'6eA',date:new Date().toISOString().slice(0,10)})});if(r.ok){const d=await r.json();setSummary(`${d.text} · origine: ${d.origin}`)}}

 if(!role)return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-5"><section className="w-full max-w-md rounded-3xl bg-white p-8 shadow-xl shadow-slate-200"><Brand/><h2 className="mt-8 text-2xl font-bold text-slate-900">Connexion</h2><p className="mt-1 text-sm text-slate-500">Accès agent, responsable ou parent</p><form onSubmit={login} className="mt-6 space-y-4"><Field label="Identifiant" name="login"/><Field label="Mot de passe" name="password" type="password"/><button className="w-full rounded-xl bg-passage px-4 py-3 font-bold text-white">Se connecter</button>{error&&<p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}</form></section></main>

 return <div className="min-h-screen bg-slate-50"><header className="bg-white border-b border-slate-200"><div className="mx-auto flex max-w-6xl items-center px-5 py-4"><Brand/><span className={`ml-auto rounded-full px-3 py-1 text-xs font-bold ${online?'bg-emerald-50 text-emerald-700':'bg-red-50 text-red-700'}`}>{online?'En ligne':'Hors ligne'}</span></div></header><main className="mx-auto max-w-6xl px-5 py-8"><div className="mb-6 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-passage">Tableau de bord</p><h1 className="mt-1 text-2xl font-bold">Bonjour, {name}</h1></div><button onClick={logout} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold">Déconnexion</button></div>
 {role==='agent'&&<div className="grid gap-5 md:grid-cols-2"><Card title="Scan hors ligne"><p className="text-sm text-slate-500">Les passages sont conservés sur cet appareil puis synchronisés automatiquement.</p><label className="mt-5 block text-sm font-bold">Point de contrôle<select value={point} onChange={e=>setPoint(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 p-3">{points.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label><label className="mt-4 block text-sm font-bold">Jeton du badge<input value={token} onChange={e=>setToken(e.target.value)} placeholder="Coller le jeton temporaire" className="mt-2 w-full rounded-xl border border-slate-200 p-3 font-normal"/></label><button onClick={addScan} className="mt-4 w-full rounded-xl bg-passage py-3 font-bold text-white">Ajouter hors ligne</button><p className="mt-3 text-sm text-slate-600">{status}</p></Card><Card title="File locale"><div className="flex items-center justify-between"><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-passage">{queue.length} passage(s)</span></div><div className="mt-4 max-h-48 space-y-2 overflow-auto">{queue.map((x,i)=><div key={i} className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{x.local_event_id.slice(0,8)} · point {x.point_id}</div>)}</div><button onClick={sync} className="mt-4 w-full rounded-xl border border-passage py-3 font-bold text-passage">Synchroniser maintenant</button></Card></div>}
 {role==='responsable'&&<div className="grid gap-5 md:grid-cols-2"><Card title="Anomalies"><p className="text-sm text-slate-500">Déclencher la détection des absences à clôture.</p><button onClick={async()=>{const r=await fetch(API+'/api/anomalies/detect/',{method:'POST',credentials:'include'});setStatus(r.ok?JSON.stringify(await r.json()):'Accès refusé')}} className="mt-4 rounded-xl bg-passage px-4 py-3 font-bold text-white">Détecter maintenant</button><p className="mt-3 text-sm">{status}</p></Card><Card title="Synthèse assistée"><p className="text-sm text-slate-500">Classe 6eA · chiffres calculés côté serveur</p><button onClick={generate} className="mt-4 rounded-xl bg-passage px-4 py-3 font-bold text-white">Générer la synthèse</button>{summary&&<p className="mt-4 rounded-xl border-l-4 border-passage bg-blue-50 p-4 text-sm">{summary}</p>}</Card></div>}
 {role==='parent'&&<Card title="Mes enfants"><p className="text-sm text-slate-500">Seuls les élèves rattachés à votre compte sont accessibles.</p><p className="mt-4 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700">Accès cloisonné activé côté serveur.</p></Card>}
 </main></div>
}
function Brand(){return <div className="flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-passage text-xl font-black text-white">P</div><div><p className="font-black leading-none text-slate-900">PASSAGE</p><p className="mt-1 text-[10px] font-bold text-slate-500">SMART SCHOOL ATTENDANCE</p></div></div>}
function Card({title,children}:{title:string,children:ReactNode}){return <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="mb-3 text-lg font-bold">{title}</h2>{children}</section>}
function Field({label,name,type='text'}:{label:string,name:string,type?:string}){return <label className="block text-sm font-bold text-slate-700">{label}<input name={name} type={type} required minLength={type==='password'?8:undefined} className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 font-normal outline-none focus:border-passage"/></label>}
export default App
