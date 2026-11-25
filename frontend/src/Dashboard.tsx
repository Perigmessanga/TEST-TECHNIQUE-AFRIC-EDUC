import { useEffect, useState, type FormEvent } from 'react'

type Role='agent'|'responsable'|'parent'
const QUEUE='passage-offline-queue-v1'

const api=async(path:string,options:RequestInit={})=>{
 const csrfToken=document.cookie.split('; ').find(cookie=>cookie.startsWith('csrftoken='))?.split('=').slice(1).join('=')
 const {headers,...requestOptions}=options
 const response=await fetch(path,{...requestOptions,credentials:'include',headers:{'Content-Type':'application/json',...(csrfToken?{'X-CSRFToken':decodeURIComponent(csrfToken)}:{}),...(headers||{})}})
 const data=await response.json().catch(()=>({}))
 if(!response.ok) throw new Error(data.detail||'Une erreur est survenue')
 return data
}

function Brand({compact=false}:{compact?:boolean}){
 return <div className="flex items-center gap-3"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[#155eef] text-xl font-black text-white shadow-lg shadow-blue-200">P</div>{!compact&&<div><p className="font-black leading-none text-slate-900">PASSAGE</p><p className="mt-1 text-[9px] font-black tracking-[0.18em] text-slate-400">SMART SCHOOL ATTENDANCE</p></div>}</div>
}

function Card({title,subtitle,action,children}:{title:string;subtitle?:string;action?:React.ReactNode;children:React.ReactNode}){
 return <section className="rounded-2xl border border-slate-200/80 bg-white shadow-[0_10px_30px_rgba(15,23,42,.05)]"><div className="flex items-start justify-between border-b border-slate-100 px-5 py-4"><div><h2 className="text-base font-black text-slate-900">{title}</h2>{subtitle&&<p className="mt-1 text-xs text-slate-500">{subtitle}</p>}</div>{action}</div><div className="p-5">{children}</div></section>
}

export default function Dashboard(){
 const [role,setRole]=useState<Role|null>(null)
 const [name,setName]=useState('')
 const [error,setError]=useState('')
 const [online,setOnline]=useState(navigator.onLine)
 const [queue,setQueue]=useState<any[]>(()=>JSON.parse(localStorage.getItem(QUEUE)||'[]'))

 useEffect(()=>{
  const up=()=>setOnline(true),down=()=>setOnline(false)
  window.addEventListener('online',up);window.addEventListener('offline',down)
    api('/api/csrf/').catch(()=>undefined).then(()=>api('/api/me/')).then(d=>{setRole(d.role);setName(d.name)}).catch(()=>{})
  return()=>{window.removeEventListener('online',up);window.removeEventListener('offline',down)}
 },[])
 useEffect(()=>localStorage.setItem(QUEUE,JSON.stringify(queue)),[queue])

 async function login(event:FormEvent<HTMLFormElement>){
  event.preventDefault();setError('')
  const form=new FormData(event.currentTarget)
  try{const d=await api('/api/login/',{method:'POST',body:JSON.stringify({login:form.get('login'),password:form.get('password')})});setRole(d.role);setName(d.name)}catch(e){setError(e instanceof Error?e.message:'Connexion impossible')}
 }
 async function logout(){try{await api('/api/logout/',{method:'POST'})}finally{setRole(null)}}

 if(!role)return <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top_left,#eef5ff,transparent_38%),#f8fafc] p-5"><section className="w-full max-w-md rounded-[28px] border border-white bg-white p-8 shadow-[0_24px_70px_rgba(15,23,42,.12)]"><Brand/><div className="mt-9"><p className="text-xs font-black uppercase tracking-[0.18em] text-[#155eef]">Portail sécurisé</p><h1 className="mt-2 text-3xl font-black text-slate-950">Connexion</h1><p className="mt-2 text-sm text-slate-500">Accès agent, responsable ou parent</p></div><form onSubmit={login} className="mt-7 space-y-4"><label className="block text-sm font-bold text-slate-700">Identifiant<input name="login" defaultValue="agent" autoComplete="username" required className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition focus:border-[#155eef] focus:bg-white focus:ring-4 focus:ring-blue-50"/></label><label className="block text-sm font-bold text-slate-700">Mot de passe<input name="password" type="password" defaultValue="Test1234" minLength={8} autoComplete="current-password" required className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition focus:border-[#155eef] focus:bg-white focus:ring-4 focus:ring-blue-50"/></label>{error&&<p className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</p>}<button className="w-full rounded-xl bg-[#155eef] py-3.5 font-black text-white shadow-lg shadow-blue-200 transition hover:bg-blue-700">Se connecter</button></form></section></main>

 return <div className="min-h-screen bg-[#f4f7fb] text-slate-900"><header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur"><div className="mx-auto flex h-[76px] max-w-[1320px] items-center px-5"><Brand/><div className="ml-auto flex items-center gap-3"><span className={`rounded-full px-3 py-1.5 text-xs font-black ${online?'bg-emerald-50 text-emerald-700':'bg-orange-50 text-orange-700'}`}><span className={`mr-2 inline-block h-2 w-2 rounded-full ${online?'bg-emerald-500':'bg-orange-500'}`}/>{online?'En ligne':'Hors ligne'}</span><button onClick={logout} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-black hover:bg-slate-50">Déconnexion</button></div></div></header><main className="mx-auto max-w-[1320px] px-5 py-7"><div className="mb-6"><p className="text-xs font-black uppercase tracking-[0.16em] text-[#155eef]">Espace {role}</p><h1 className="mt-1 text-2xl font-black">Bonjour, {name}</h1></div>{role==='agent'&&<AgentView queue={queue} setQueue={setQueue} />} {role==='responsable'&&<ResponsibleView/>} {role==='parent'&&<ParentView/>}</main></div>
}

function AgentView({queue,setQueue}:{queue:any[];setQueue:(v:any[])=>void}){
 const [points,setPoints]=useState<any[]>([]);const [point,setPoint]=useState('');const [token,setToken]=useState('');const [status,setStatus]=useState('Prêt à synchroniser');const [syncInfo,setSyncInfo]=useState<any>(null)
 useEffect(()=>{api('/api/control-points/').then(d=>{setPoints(d);setPoint(d[0]?.id?.toString()||'')}).catch(()=>{});refresh()},[])
 useEffect(()=>{if(navigator.onLine&&queue.length) sync()},[queue.length])
 async function refresh(){try{setSyncInfo(await api('/api/sync/status/'))}catch{return}}
 function addScan(){if(token.trim().length<20){setStatus('Demandez un jeton temporaire au responsable');return}const item={point_id:Number(point),local_time:new Date().toISOString(),device_id:localStorage.deviceId||(localStorage.deviceId=crypto.randomUUID()),badge_token:token.trim(),local_event_id:crypto.randomUUID()};setQueue([...queue,item]);setToken('');setStatus('Passage ajouté à la file locale')}
 async function sync(){if(!queue.length)return;try{setStatus('Synchronisation en cours…');const d=await api('/api/sync/',{method:'POST',body:JSON.stringify({items:queue})});const handled=new Set([...d.accepted_events,...d.duplicate_events,...d.rejected.map((x:any)=>x.event)]);setQueue(queue.filter(x=>!handled.has(x.local_event_id)));setStatus(`${d.accepted} envoyé(s) · ${d.duplicates} doublon(s) évité(s)`);await refresh()}catch(e){setStatus(e instanceof Error?e.message:'Synchronisation impossible')}}
 return <div className="grid gap-5 lg:grid-cols-[1.25fr_.75fr]"><Card title="Scanner un badge" subtitle="Le scan reste utilisable hors connexion"><div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-black">Point de contrôle<select value={point} onChange={e=>setPoint(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3"><option value="">Sélectionner</option>{points.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label><label className="text-sm font-black">Jeton temporaire du badge<input value={token} onChange={e=>setToken(e.target.value)} placeholder="Coller le jeton scanné" className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 font-normal"/></label></div><button onClick={addScan} className="mt-5 w-full rounded-xl bg-[#155eef] py-3.5 font-black text-white shadow-lg shadow-blue-100">Ajouter le passage hors ligne</button></Card><Card title="Synchronisation" subtitle="File locale et serveur"><div className="flex items-center justify-between"><div><p className="text-xs text-slate-500">État</p><p className="mt-1 font-black">{status}</p></div><div className="text-right"><p className="text-xs text-slate-500">En attente</p><p className="mt-1 text-2xl font-black text-[#155eef]">{queue.length}</p></div></div><div className="mt-5 max-h-44 space-y-2 overflow-auto">{queue.map((item,i)=><div key={i} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2.5 text-xs"><span>Point {item.point_id}</span><span className="rounded-full bg-orange-100 px-2 py-1 font-bold text-orange-700">En attente</span></div>)}</div><button onClick={sync} className="mt-5 w-full rounded-xl border-2 border-[#155eef] py-3 font-black text-[#155eef]">Synchroniser maintenant</button><p className="mt-4 text-xs text-slate-500">{syncInfo?.server_passages||0} passage(s) confirmé(s) sur le serveur</p></Card></div>
}

function ResponsibleView(){
 const [tab,setTab]=useState<'dashboard'|'students'|'badges'|'routes'|'anomalies'|'synthesis'>('dashboard');const [students,setStudents]=useState<any[]>([]);const [badges,setBadges]=useState<any[]>([]);const [points,setPoints]=useState<any[]>([]);const [routes,setRoutes]=useState<any[]>([]);const [anomalies,setAnomalies]=useState<any[]>([]);const [synthesis,setSynthesis]=useState<any>(null)
 useEffect(()=>{load()},[])
 async function load(){try{const [s,b,p,r,a]=await Promise.all([api('/api/students/'),api('/api/badges/'),api('/api/control-points/manage/'),api('/api/routes/'),api('/api/anomalies/')]);setStudents(s);setBadges(b);setPoints(p);setRoutes(r);setAnomalies(a)}catch{}}
 async function generate(){try{setSynthesis(await api('/api/summaries/',{method:'POST',body:JSON.stringify({class_name:'6eA',date:new Date().toISOString().slice(0,10)})}))}catch(e){alert(e)}}
 const tabs=[['dashboard','Vue générale'],['students','Élèves'],['badges','Badges'],['routes','Points & itinéraires'],['anomalies','Anomalies'],['synthesis','Synthèse IA']] as const
 return <div><nav className="mb-5 flex gap-2 overflow-auto rounded-2xl border border-slate-200 bg-white p-2">{tabs.map(([id,label])=><button key={id} onClick={()=>setTab(id)} className={`whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-black ${tab===id?'bg-[#155eef] text-white shadow-md shadow-blue-100':'text-slate-600 hover:bg-slate-50'}`}>{label}</button>)}</nav>{tab==='dashboard'&&<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Stat label="Élèves" value={students.length}/><Stat label="Badges actifs" value={badges.filter(b=>b.state==='actif').length}/><Stat label="Points" value={points.length}/><Stat label="Anomalies" value={anomalies.length}/></div>}{tab==='students'&&<Card title="Liste des élèves" subtitle="Gestion des classes et de l'établissement"><DataTable headers={['Nom','Classe','Établissement','Badge']} rows={students.map(s=>[s.name,s.class_name,s.establishment,s.badge_state])}/></Card>}{tab==='badges'&&<Card title="Gestion des badges"><DataTable headers={['Élève','État','Émission']} rows={badges.map(b=>[b.student,b.state,new Date(b.issued_at).toLocaleDateString('fr-FR')])}/></Card>}{tab==='routes'&&<Card title="Points de contrôle & itinéraires"><DataTable headers={['Élève','Point','Fenêtre','Jours']} rows={routes.map(r=>[r.student,r.point,`${r.start_time}–${r.end_time}`,r.days])}/></Card>}{tab==='anomalies'&&<Card title="Anomalies détectées"><DataTable headers={['Élève','Type','Date','État']} rows={anomalies.map(a=>[a.student,a.type,a.date,a.state])}/></Card>}{tab==='synthesis'&&<Card title="Synthèse quotidienne" action={<button onClick={generate} className="rounded-xl bg-[#155eef] px-4 py-2 text-sm font-black text-white">Générer</button>}><p className="text-sm text-slate-500">Classe 6eA · données calculées côté Django</p>{synthesis&&<p className="mt-4 rounded-xl border-l-4 border-[#155eef] bg-blue-50 p-5 font-bold">{synthesis.text}<span className="mt-2 block text-xs font-normal text-slate-500">Origine : {synthesis.origin}</span></p>}</Card>}</div>
}

function Stat({label,value}:{label:string;value:number}){return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-black text-slate-500">{label}</p><p className="mt-2 text-3xl font-black text-slate-950">{value}</p></section>}
function DataTable({headers,rows}:{headers:string[];rows:string[][]}){return <div className="overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{headers.map(h=><th key={h} className="border-b border-slate-100 px-3 py-3 text-xs uppercase text-slate-400">{h}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j} className="border-b border-slate-50 px-3 py-3.5">{j===1&&typeof v==='string'?<span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold">{v}</span>:v}</td>)}</tr>)}</tbody></table>{rows.length===0&&<p className="py-8 text-center text-sm text-slate-400">Aucune donnée disponible</p>}</div>}

function ParentView(){const [children,setChildren]=useState<any[]>([]);useEffect(()=>{api('/api/parent/children/').then(setChildren).catch(()=>{})},[]);return <div className="grid gap-5 lg:grid-cols-3">{children.map(child=><Card key={child.id} title={child.name} subtitle={`${child.class_name} · ${child.establishment}`}><p className="text-xs font-black uppercase text-slate-400">Derniers passages</p><div className="mt-3 space-y-2">{child.passages.map((p:any,i:number)=><div key={i} className="rounded-xl bg-slate-50 p-3 text-sm"><p className="font-bold">{p.point}</p><p className="mt-1 text-xs text-slate-500">{new Date(p.server_time).toLocaleString('fr-FR')}</p></div>)}</div><p className="mt-5 text-xs font-black uppercase text-slate-400">Anomalies</p><div className="mt-3 space-y-2">{child.anomalies.map((a:any)=><div key={a.id} className="rounded-xl border border-orange-100 bg-orange-50 p-3 text-sm"><p className="font-bold text-orange-800">{a.type}</p><p className="mt-1 text-xs text-orange-600">{a.date} · {a.state}</p></div>)}</div></Card>)}</div>}
