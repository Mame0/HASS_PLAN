// HassPlan — modules B: Intelligence, Harvest, Labor, Logistics, Transport, Alerts
const HP_B = window.HP;

/* ===================== M4 — Intelligence ===================== */
function Intelligence() {
  const { navigate, toast } = useRouter();
  const ro = esCampanaCerrada();
  const campanaId = HP_B.activeCampaign && HP_B.activeCampaign.id;
  // Solo se pueden predecir sectores con variables completas (sin pendientes).
  const predecibles = HP_B.SECTORS.filter(s => (s.pendientes || 0) === 0);
  const [sel, setSel] = useState(() => predecibles.map(s => s.id));
  const [running, setRunning] = useState(false);
  const ready = predecibles.length;
  const confs = HP_B.SECTORS.filter(s => s.confianza != null).map(s => s.confianza);
  const confMedia = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null;
  const togg = (id) => setSel(sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id]);

  async function execute() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (!campanaId) { toast('No hay campaña activa'); return; }
    if (!sel.length) { toast('Selecciona al menos un sector'); return; }
    setRunning(true);
    let ok = 0, ood = 0, err = 0;
    for (const id of sel) {
      try {
        const r = await HP_B.api.predecirLote(id, campanaId);
        ok++;
        if (r && r.es_extrapolacion) ood++;
      } catch (e) { err++; }
    }
    await HP_B.api.refrescar();
    setRunning(false);
    toast(`Predicción ejecutada · ${ok} sector(es)` + (ood ? ` · ${ood} OOD` : '') + (err ? ` · ${err} con error` : ''));
    if (ok) navigate('intelligence_res');
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="M4 · Inteligencia agrícola"
        title="Predicción de rendimiento"
        sub="Selecciona los sectores con variables completas y ejecuta el modelo. El rendimiento del clima en La Joya extrapola (OOD): el modelo es soporte, la columna vertebral es edad + riego."
        actions={
          <>
            <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>MODELO IA · Random Forest</span>
            <button className="btn primary" disabled={running || ro} onClick={execute}>
              {running ? 'Procesando…' : <><Icon name="play" size={14}/> Ejecutar predicción ({sel.length})</>}
            </button>
          </>
        }
      />

      <div className="row-3" style={{ marginBottom: 16 }}>
        <InfoCard icon="sectors" label="Sectores con datos completos" big={`${ready} / ${HP_B.SECTORS.length}`} small="Los demás esperan resync climático o variables manuales" />
        <div className="card card-pad hstack" style={{ gap: 16, alignItems: 'center' }}>
          <Donut pct={confMedia || 0} label="confianza" />
          <div>
            <div className="page-eyebrow" style={{ marginBottom: 6 }}>Confianza media del modelo</div>
            <div style={{ fontSize: 12, color: 'var(--ink-3)' }}>Dispersión entre árboles del Random Forest</div>
          </div>
        </div>
        <InfoCard icon="harvest" label="Producción estimada total" big={`${HP_B.fmtNum(HP_B.estimadoTn || 0, 0)} Tn`} small="Σ de Tn/Ha × Área por sector predicho" />
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Sectores a predecir</h3>
          <div className="right hstack" style={{ gap: 8, fontSize: 12, color: 'var(--ink-3)' }}>
            <button className="btn ghost sm" onClick={() => setSel(predecibles.map(s => s.id))}>Seleccionar predecibles</button>
            <button className="btn ghost sm" onClick={() => setSel([])}>Limpiar</button>
          </div>
        </div>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 32 }}></th>
            <th>Sector</th><th className="num">Área</th>
            <th>Variables</th>
            <th className="num">Rend. estimado</th>
            <th className="num">Rango p10–p90</th>
            <th>Confianza</th>
          </tr></thead>
          <tbody>
            {HP_B.SECTORS.map(s => {
              const checked = sel.includes(s.id);
              const incompletas = (s.pendientes || 0) > 0;
              const conf = s.confianza;
              return (
                <tr key={s.id} onClick={() => !incompletas && togg(s.id)} style={{ cursor: incompletas ? 'not-allowed' : 'pointer', opacity: incompletas ? 0.55 : 1 }}>
                  <td><input type="checkbox" checked={checked} disabled={incompletas} readOnly /></td>
                  <td><span className="mono" style={{ color: 'var(--ink-3)' }}>L{s.id}</span> · <span className="strong">{s.name}</span></td>
                  <td className="num">{HP_B.fmtNum(s.area, 1)} Ha</td>
                  <td>{incompletas ? <Badge tone="warn">{s.pendientes} pendiente(s)</Badge> : <Badge tone="olive">Completas</Badge>}</td>
                  <td className="num strong">{s.expectedYieldHa != null ? HP_B.fmtNum(s.expectedYieldHa, 1) + ' Tn/Ha' : '—'}</td>
                  <td className="num">{s.intervalo ? <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{HP_B.fmtNum(s.intervalo.p10, 1)}–{HP_B.fmtNum(s.intervalo.p90, 1)}</span> : <span style={{ color: 'var(--muted)' }}>—</span>}</td>
                  <td>
                    {conf != null ? (
                      <div className="hstack" style={{ gap: 8 }}>
                        <div className="prog" style={{ width: 110 }}><span style={{ width: (conf*100)+'%' }}></span></div>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{Math.round(conf*100)}%</span>
                      </div>
                    ) : <span style={{ color: 'var(--muted)' }}>—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function IntelligenceResult() {
  const { navigate, toast } = useRouter();
  const conPred = HP_B.SECTORS.filter(s => s.expectedYieldHa != null);
  const totalTons = conPred.reduce((a, s) => a + s.expectedYieldHa * s.area, 0);
  const areaTotal = conPred.reduce((a, s) => a + s.area, 0);
  const rendProm = areaTotal ? totalTons / areaTotal : 0;
  const confs = conPred.filter(s => s.confianza != null).map(s => s.confianza);
  const confMedia = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null;
  const campNombre = (HP_B.activeCampaign && HP_B.activeCampaign.nombre) || 'Campaña';
  const maxRend = conPred.length ? Math.max(...conPred.map(s => s.expectedYieldHa)) : 1;

  return (
    <div className="page">
      <PageHeader
        eyebrow="M4 · Resultados de predicción"
        title={`Producción estimada · ${campNombre}`}
        sub="Predicción a nivel de sector. La confianza mide la dispersión entre los árboles del Random Forest; el clima de La Joya marca extrapolación (OOD)."
        actions={
          <>
            <button className="btn ghost" onClick={() => navigate('intelligence')}>Volver</button>
            <button className="btn terra" onClick={() => navigate('harvest')}>
              <Icon name="check" size={14}/> Ir a Planificación de Cosecha
            </button>
          </>
        }
      />

      <div className="row-3" style={{ marginBottom: 16 }}>
        <InfoCard icon="harvest" label="Total estimado" big={`${HP_B.fmtNum(totalTons, 0)} Tn`} small={`${conPred.length} sector(es) predicho(s)`} />
        <InfoCard icon="sectors" label="Rendimiento promedio" big={`${HP_B.fmtNum(rendProm, 1)} Tn/Ha`} small="Ponderado por área · La Joya: 14–24 Tn/Ha" />
        <div className="card card-pad hstack" style={{ gap: 16, alignItems: 'center' }}>
          <Donut pct={confMedia || 0} label="confianza" />
          <div>
            <div className="page-eyebrow" style={{ marginBottom: 6 }}>Confianza media</div>
            <div style={{ fontSize: 12, color: 'var(--ink-3)' }}>Dispersión entre árboles del Random Forest</div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3>Por sector</h3></div>
        {conPred.length === 0 ? (
          <div className="card-pad" style={{ color: 'var(--muted)', fontSize: 13 }}>
            Aún no hay predicciones en esta campaña. Ejecuta el modelo en la pantalla anterior.
          </div>
        ) : (
          <table className="tbl">
            <thead><tr>
              <th>Sector</th><th className="num">Área</th>
              <th className="num">Tn/Ha predicha</th>
              <th className="num">Rango p10–p90</th>
              <th className="num">Tn totales</th>
              <th>Confianza</th>
            </tr></thead>
            <tbody>
              {conPred.map(s => (
                <tr key={s.id}>
                  <td><span className="mono" style={{ color: 'var(--ink-3)' }}>L{s.id}</span> · <span className="strong">{s.name}</span></td>
                  <td className="num">{HP_B.fmtNum(s.area, 1)} Ha</td>
                  <td className="num strong">{HP_B.fmtNum(s.expectedYieldHa, 1)}</td>
                  <td className="num">{s.intervalo ? <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{HP_B.fmtNum(s.intervalo.p10, 1)}–{HP_B.fmtNum(s.intervalo.p90, 1)}</span> : <span style={{ color: 'var(--muted)' }}>—</span>}</td>
                  <td className="num strong">{HP_B.fmtNum(s.expectedYieldHa * s.area, 1)} Tn</td>
                  <td>{s.confianza != null ? <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{Math.round(s.confianza*100)}%</span> : <span style={{ color:'var(--muted)' }}>—</span>}</td>
                </tr>
              ))}
              <tr style={{ background: 'var(--surface-2)' }}>
                <td className="strong">Total campaña</td>
                <td className="num strong">{HP_B.fmtNum(areaTotal, 1)} Ha</td>
                <td className="num">{HP_B.fmtNum(rendProm, 1)}</td>
                <td>—</td>
                <td className="num strong">{HP_B.fmtNum(totalTons, 0)} Tn</td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      {/* Rendimiento predicho por sector (datos reales; el histórico por lote se cableará aparte) */}
      {conPred.length > 0 && (
        <div className="card">
          <div className="card-head"><h3>Rendimiento predicho por sector</h3>
            <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>Tn/Ha</div>
          </div>
          <div className="card-pad">
            <div style={{ display: 'grid', gap: 10 }}>
              {conPred.map(s => (
                <div key={s.id} style={{ display:'grid', gridTemplateColumns:'160px 1fr', gap: 14, alignItems:'center' }}>
                  <div>
                    <div style={{ fontSize: 12.5, color: 'var(--ink)' }}>{s.name}</div>
                    <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>L{s.id} · {HP_B.fmtNum(s.area,1)} Ha</div>
                  </div>
                  <CmpBar pct={s.expectedYieldHa/maxRend} lbl={`${HP_B.fmtNum(s.expectedYieldHa,1)} Tn/Ha`} kind="now" />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CmpBar({ pct, lbl, kind }) {
  const colors = {
    now:  'linear-gradient(90deg, var(--primary), #6B9A1F)',
    prev: 'linear-gradient(90deg, var(--terra), #C9762E)',
    prev2:'linear-gradient(90deg, #9B8255, #B8A475)',
  };
  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 130px', gap:8, alignItems:'center' }}>
      <div style={{ position:'relative', height: 12, background:'var(--surface-2)', borderRadius: 3, border: '1px solid var(--border)' }}>
        <div style={{ position:'absolute', inset: 0, width: (pct*100)+'%', background: colors[kind], borderRadius: 2 }}></div>
      </div>
      <div className="mono" style={{ fontSize: 11, color: kind === 'now' ? 'var(--ink)' : 'var(--ink-3)' }}>{lbl}</div>
    </div>
  );
}

function DeltaCmp({ v }) {
  if (v == null) return <span style={{ color: 'var(--muted)' }}>—</span>;
  const up = v >= 0;
  return (
    <span className={'delta mono ' + (up ? 'up' : 'down')} style={{ fontSize: 12 }}>
      {up ? '▲' : '▼'} {HP_B.fmtNum(Math.abs(v), 1)}%
    </span>
  );
}

/* ===================== M5 — Harvest ===================== */
// Curvas de reparto, iguales al backend (services/planificacion.py · _pesos_*):
// devuelven los pesos (Σ=1) por semana. Sirven para la VISTA PREVIA; el plan real
// lo calcula el backend con la misma fórmula.
function curvaPesos(tipo, n) {
  let crudos;
  if (tipo === 'uniforme') crudos = Array.from({ length: n }, () => 1);
  else if (tipo === 'creciente') crudos = Array.from({ length: n }, (_, i) => i + 1);
  else if (tipo === 'decreciente') crudos = Array.from({ length: n }, (_, i) => n - i);
  else crudos = Array.from({ length: n }, (_, i) => Math.sin(Math.PI * (i + 0.5) / n)); // campana
  const s = crudos.reduce((a, b) => a + b, 0) || 1;
  return crudos.map(w => w / s);
}

function Harvest() {
  const { navigate, toast } = useRouter();
  const ro = esCampanaCerrada();
  const plan = HP_B.plan;                       // plan real de la campaña (o null)
  const estimado = HP_B.estimadoTn || 0;        // Σ predicciones de los lotes (Tn)
  const campanaId = HP_B.activeCampaign && HP_B.activeCampaign.id;
  const campStart = (HP_B.activeCampaign && HP_B.activeCampaign.fecha_inicio) || '';

  const [weeks, setWeeks] = useState(() => (plan && plan.semanas_total) || 16);
  const [start, setStart] = useState(() => (plan && plan.fecha_inicio) || campStart);
  const [curva, setCurva] = useState(() => (plan && plan.curva) || 'campana');
  const [busy, setBusy] = useState(false);

  // Distribución prevista según la curva y el nº de semanas elegidos → % por semana.
  const dist = curvaPesos(curva, weeks).map(w => +(w * 100).toFixed(1));
  const total = plan ? plan.tn_total : estimado;       // base para repartir
  const semanaTn = dist.map(p => (p / 100) * total);
  const picoTn = Math.max(0, ...semanaTn);
  const picoIdx = semanaTn.indexOf(picoTn);
  const promedio = weeks ? total / weeks : 0;
  const cierre = (start && weeks)
    ? new Date(new Date(start).getTime() + (weeks * 7 - 1) * 864e5).toISOString().slice(0, 10)
    : '—';

  async function generar() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (!campanaId) { toast('No hay campaña activa'); return; }
    if (!start) { toast('Indica la fecha de inicio'); return; }
    if (estimado <= 0 && !plan) { toast('Primero predice los lotes (no hay producción estimada)'); return; }
    setBusy(true);
    try {
      await HP_B.api.generarPlanCosecha(campanaId, { fecha_inicio: start, semanas_total: weeks, curva });
      await HP_B.api.refrescar();
      toast('Plan de cosecha generado ✓');
      navigate('harvest_cal');
    } catch (e) {
      toast('Error al generar el plan: ' + (e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="M5 · Planificación de cosecha"
        title="Parámetros del plan"
        sub={`Fecha de inicio y duración. La producción estimada (${HP_B.fmtNum(estimado)} Tn, Σ de las predicciones) se reparte en una curva tipo campana.`}
        actions={
          <>
            <button className="btn ghost" onClick={() => navigate('harvest_cal')}><Icon name="calendar" size={14}/> Ver calendario</button>
            <button className="btn primary" disabled={ro || busy} onClick={generar}>
              {busy ? 'Generando…' : (plan ? 'Regenerar plan' : 'Generar plan')} <Icon name="chev" size={14}/>
            </button>
          </>
        }
      />

      <div className="card card-pad" style={{ marginBottom: 16 }}>
          <div className="row-2">
            <div className="field"><label>Fecha de inicio</label><input type="date" value={start} disabled={ro} onChange={e=>setStart(e.target.value)} /></div>
            <div className="field"><label>Semanas de cosecha</label><input type="number" min="2" max="21" value={weeks} disabled={ro} onChange={e=>setWeeks(Math.max(2, Math.min(21, parseInt(e.target.value) || 2)))} /></div>
          </div>
          <div className="field"><label>Curva de distribución</label>
            <select value={curva} disabled={ro} onChange={e=>setCurva(e.target.value)}>
              <option value="campana">Campana (seno, pico al centro)</option>
              <option value="uniforme">Uniforme (igual cada semana)</option>
              <option value="creciente">Creciente (pico al final)</option>
              <option value="decreciente">Decreciente (pico al inicio)</option>
            </select>
            <span className="hint" style={{ fontSize: 11, color: 'var(--muted)' }}>El backend reparte el 100% con la curva elegida; siempre cuadra con el total.</span>
          </div>
          <div className="divider-h"></div>
          <div className="hstack" style={{ justifyContent:'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>Distribución semanal prevista (Tn)</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--ok)' }}>Σ {HP_B.fmtNum(total)} Tn ✓</span>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap: 8 }}>
            {semanaTn.map((tn, i) => (
              <div className="field" key={i} style={{ margin: 0 }}>
                <label style={{ textAlign:'center' }}>S{String(i+1).padStart(2,'0')}</label>
                <input className="mono" style={{ textAlign:'center' }} value={HP_B.fmtNum(tn, 1)} readOnly />
                <span style={{ display:'block', textAlign:'center', fontSize: 10, color: 'var(--muted)' }}>{dist[i]}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3>Resumen del plan</h3></div>
          <div className="card-pad">
            <div style={{ display:'grid', gap:14 }}>
              <SummaryRow label={plan ? 'Producción del plan' : 'Producción estimada'} v={`${HP_B.fmtNum(total)} Tn`} />
              <SummaryRow label="Duración" v={`${weeks} semanas`} />
              <SummaryRow label="Pico semanal" v={`${HP_B.fmtNum(picoTn)} Tn (S${String(picoIdx+1).padStart(2,'0')})`} warn />
              <SummaryRow label="Promedio semanal" v={`${HP_B.fmtNum(promedio)} Tn`} />
              <SummaryRow label="Fecha de cierre" v={cierre} />
            </div>
            <div className="divider-h"></div>
            <div className="page-eyebrow" style={{ marginBottom: 6 }}>Vista previa de curva</div>
            <div style={{ display:'flex', alignItems:'flex-end', gap:3, height:120, padding: '6px 0' }}>
              {dist.map((d, i) => (
                <div key={i} title={`S${i+1}: ${d}%`} style={{ flex:1, background: 'linear-gradient(180deg, var(--primary), #6B9A1F)', height: (d/Math.max(...dist))*100+'%', borderRadius: '3px 3px 0 0', minHeight: 4 }}></div>
              ))}
            </div>
            <div className="hstack" style={{ justifyContent:'space-between', fontFamily:'Geist Mono', fontSize:10, color:'var(--muted)' }}>
              <span>S01</span><span>S{String(Math.ceil(weeks/2)).padStart(2,'0')}</span><span>S{String(weeks).padStart(2,'0')}</span>
            </div>
          </div>
        </div>
    </div>
  );
}

function SummaryRow({ label, v, warn }) {
  return (
    <div className="hstack" style={{ justifyContent:'space-between' }}>
      <span style={{ color:'var(--ink-3)', fontSize: 13 }}>{label}</span>
      <span className={'mono strong ' + (warn ? '' : '')} style={{ color: warn ? 'var(--warn)' : 'var(--ink)', fontSize: 13 }}>{v}</span>
    </div>
  );
}

// Fila de semana con Tn editable: al guardar reprograma la semana (redistribuye el resto).
// La columna "Tn real" registra la cosecha ejecutada (F7) sin tocar el plan ni la cascada.
function WeekPlanRow({ w, total, isPeak, ro, toast }) {
  const [val, setVal] = useState(w.planned);
  const [real, setReal] = useState(w.real != null ? w.real : '');
  const [busy, setBusy] = useState(false);
  const pct = total ? (w.planned / total * 100) : (w.pct * 100);

  async function guardar() {
    const nuevo = parseFloat(val);
    if (isNaN(nuevo) || nuevo === w.planned) { setVal(w.planned); return; }
    setBusy(true);
    try {
      await window.HP.api.reprogramarSemana(w.id, nuevo);
      await window.HP.api.refrescar();
      toast('Semana ' + w.label + ' reprogramada ✓ (cascada recalculada)');
    } catch (e) {
      setVal(w.planned);
      toast('Error al reprogramar: ' + (e.message || e));
    } finally { setBusy(false); }
  }

  async function guardarReal() {
    const txt = String(real).trim();
    const nuevo = txt === '' ? null : parseFloat(txt);
    const previo = w.real != null ? w.real : null;
    if (nuevo !== null && isNaN(nuevo)) { setReal(previo != null ? previo : ''); return; }
    if (nuevo === previo) return;
    setBusy(true);
    try {
      await window.HP.api.registrarCosechaReal(w.id, nuevo);
      await window.HP.api.refrescar();
      toast('Cosecha real de ' + w.label + (nuevo === null ? ' borrada ✓' : ' registrada ✓'));
    } catch (e) {
      setReal(previo != null ? previo : '');
      toast('Error al registrar cosecha real: ' + (e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <tr style={isPeak ? { background: 'rgba(181,83,11,0.06)' } : null}>
      <td className="strong mono">{w.label}</td>
      <td>{w.dates}</td>
      <td className="num strong">
        <input className="mono" style={{ width: 84, textAlign: 'right' }} value={val} disabled={ro || busy}
          onChange={e => setVal(e.target.value)} onBlur={guardar}
          onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }} />
      </td>
      <td className="num">{pct.toFixed(1)}%</td>
      <td className="num">
        <input className="mono" style={{ width: 84, textAlign: 'right' }} value={real} disabled={ro || busy}
          placeholder="—" onChange={e => setReal(e.target.value)} onBlur={guardarReal}
          onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }} />
      </td>
      <td>{isPeak ? <Badge tone="warn">Pico</Badge> : <Badge tone="neut">Planificado</Badge>}</td>
    </tr>
  );
}

function HarvestCalendar() {
  const { navigate, toast } = useRouter();
  const ro = esCampanaCerrada();
  const plan = HP_B.plan;
  const totalPlan = plan ? plan.tn_total : HP_B.WEEKS.reduce((a, w) => a + (w.planned || 0), 0);
  const maxTn = HP_B.WEEKS.length ? Math.max(...HP_B.WEEKS.map(x => x.planned)) : 0;
  const rangoFechas = HP_B.WEEKS.length
    ? (HP_B.WEEKS[0].dates.split(' – ')[0] + ' → ' + (HP_B.WEEKS[HP_B.WEEKS.length-1].dates.split(' – ')[1] || ''))
    : '—';
  return (
    <div className="page">
      <PageHeader
        eyebrow="M5 · Calendario de cosecha"
        title="Plan semanal por sector"
        sub="Vista Gantt simplificada. Cada barra es la ventana de cosecha planificada del sector. Al confirmar se activan los módulos de mano de obra, logística y transporte."
        actions={
          <>
            <button className="btn ghost" onClick={() => navigate('harvest')}>Ajustar parámetros</button>
            <button className="btn" disabled={ro}><Icon name="edit" size={14}/> Ajuste manual por semana</button>
            <button className="btn terra" disabled={ro} onClick={() => { if (ro) return; toast('Plan confirmado — módulos dependientes activados'); navigate('labor'); }}>
              <Icon name="check" size={14}/> Confirmar plan
            </button>
          </>
        }
      />

      {/* Weekly table */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3>Plan semanal — campaña</h3>
          <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>
            Total {HP_B.fmtNum(totalPlan)} Tn · {HP_B.WEEKS.length} semanas
          </div>
        </div>
        {HP_B.WEEKS.length === 0 ? (
          <div className="card-pad" style={{ color: 'var(--muted)', fontSize: 13 }}>
            Aún no hay plan de cosecha para esta campaña. Genéralo en <b>Ajustar parámetros</b>.
          </div>
        ) : (
          <table className="tbl">
            <thead><tr>
              <th>Semana</th><th>Fechas</th>
              <th className="num">Tn plan {ro ? '' : '(editable)'}</th><th className="num">% del total</th>
              <th className="num">Tn real {ro ? '' : '(editable)'}</th><th>Estado</th>
            </tr></thead>
            <tbody>
              {HP_B.WEEKS.map((w) => (
                <WeekPlanRow key={w.id || w.week} w={w} total={totalPlan}
                  isPeak={w.planned === maxTn} ro={ro} toast={toast} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Gantt */}
      <div className="card">
        <div className="card-head"><h3>Gantt por sector</h3>
          <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{rangoFechas}</div>
        </div>
        <div className="card-pad">
          <div className="gantt">
            <div className="gantt-head">
              <div></div>
              {HP_B.WEEKS.map((w,i) => <div className="cell" key={i}>{w.label}</div>)}
            </div>
            {HP_B.SECTORS.map((s, i) => {
              // generate a 4-7 week window
              const startW = (i % 6) + 1;
              const span = 3 + (i % 4);
              const cls = s.status === 'crit' ? 'amber' : s.status === 'warn' ? 'terra' : '';
              return (
                <div className="gantt-row" key={s.id}>
                  <div className="name">
                    <span style={{ color: 'var(--ink)' }}>{s.name}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 6 }}>{s.id}</span>
                  </div>
                  {Array.from({length: 12}).map((_, k) => (
                    <div className="cell" key={k}>
                      {k === startW - 1 && (
                        <div className={'gantt-bar ' + cls} style={{ left: 2, width: `calc(${span*100}% + ${(span-1)*1}px - 4px)` }}>
                          {HP_B.fmtNum(s.expectedYieldHa * s.area / span, 0)} Tn/sem
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ===================== F7 — Validación (predicho vs real) ===================== */
// Cierre de la tesis: se ingresa la cosecha REAL (Tn/Ha) por lote y el sistema la
// compara contra la predicción del RF (error absoluto y %), con MAE/MAPE de campaña.
function Validacion() {
  const { toast } = useRouter();
  const ro = esCampanaCerrada();
  const campanaId = HP_B.activeCampaign && HP_B.activeCampaign.id;
  const [data, setData] = useState(null);     // {por_lote, resumen}
  const [loading, setLoading] = useState(true);

  const cargar = useCallback(async () => {
    if (!campanaId) { setData(null); setLoading(false); return; }
    setLoading(true);
    try { setData(await window.HP.api.resultadosCampana(campanaId)); }
    catch (e) { toast('Error: ' + e.message); setData(null); }
    finally { setLoading(false); }
  }, [campanaId, toast]);
  useEffect(() => { cargar(); }, [cargar]);

  const f2 = (n) => (n == null ? '—' : Number(n).toFixed(2));
  const f1 = (n) => (n == null ? '—' : Number(n).toFixed(1));
  const r = data && data.resumen;

  if (!campanaId) {
    return (
      <div className="page">
        <PageHeader eyebrow="F7 · Validación del modelo" title="Predicho vs Real" />
        <div className="card card-pad"><div className="empty">No hay campaña activa. Selecciona o crea una campaña.</div></div>
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: 1180 }}>
      <PageHeader eyebrow="F7 · Validación del modelo" title="Predicho vs Real"
        sub="Ingresa la cosecha real (Tn/Ha) de cada lote para validar el modelo contra La Joya. El error se calcula automáticamente." />

      {r && (
        <div className="kpi-grid" style={{ marginBottom: 16 }}>
          <Kpi icon="sectors" label="Lotes con cosecha real" value={r.n_con_real + ' / ' + r.n_lotes} unit=""
            foot={<span>{r.n_comparables} comparables (con predicción)</span>} />
          <Kpi icon="leaf" label="MAE" value={f2(r.mae)} unit="Tn/Ha" foot={<span>error absoluto medio</span>} />
          <Kpi icon="brain" label="MAPE" value={f1(r.mape)} unit="%" foot={<span>error relativo medio</span>} />
          <Kpi icon="check" label="Precisión" value={r.mape != null ? f1(100 - r.mape) : '—'} unit="%" foot={<span>100 − MAPE</span>} />
        </div>
      )}

      <div className="card">
        <div className="card-head"><h3>Cosecha real por lote</h3>
          <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>rendimiento en Tn/Ha</div>
        </div>
        {loading ? (
          <div className="empty">Cargando…</div>
        ) : !data || !data.por_lote.length ? (
          <div className="empty">La campaña no tiene lotes. Agrégalos en “Lotes”.</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Lote</th><th className="num">Predicho</th><th className="num">Real (editable)</th>
                <th className="num">Frutos/árbol</th><th className="num">Peso fruto (g)</th>
                <th className="num">Error</th><th className="num">Error %</th><th></th>
              </tr>
            </thead>
            <tbody>
              {data.por_lote.map((row) => (
                <ResultadoRow key={row.lote_id} row={row} campanaId={campanaId} ro={ro} toast={toast} onSaved={cargar} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="hint" style={{ marginTop: 10 }}>
        <b>MAE</b> = error absoluto medio (Tn/Ha) · <b>MAPE</b> = error relativo medio (%). El semáforo del error marca
        ≤10% verde, ≤25% ámbar, &gt;25% rojo. <b>Frutos/árbol</b> y <b>peso de fruto</b> se registran como referencia
        agronómica: NO entran al modelo (se conocen solo tras cosechar) pero documentan la cosecha.
      </div>
    </div>
  );
}

function ResultadoRow({ row, campanaId, ro, toast, onSaved }) {
  const [real, setReal] = useState(row.tn_ha_real != null ? String(row.tn_ha_real) : '');
  const [frutos, setFrutos] = useState(row.frutos_arbol != null ? String(row.frutos_arbol) : '');
  const [peso, setPeso] = useState(row.peso_fruto != null ? String(row.peso_fruto) : '');
  const [busy, setBusy] = useState(false);
  const f2 = (n) => (n == null ? '—' : Number(n).toFixed(2));
  const inp = { width: 78, textAlign: 'right' };

  async function guardar() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (String(real).trim() === '') { toast('Ingresa el rendimiento real (Tn/Ha) de ' + row.lote); return; }
    setBusy(true);
    try {
      await window.HP.api.guardarResultado(row.lote_id, campanaId, {
        tn_ha_real: parseFloat(real),
        frutos_arbol: String(frutos).trim() === '' ? null : parseFloat(frutos),
        peso_fruto: String(peso).trim() === '' ? null : parseFloat(peso),
      });
      toast('Cosecha real de ' + row.lote + ' guardada ✓');
      await onSaved();
    } catch (e) { toast('Error: ' + (e.message || e)); }
    finally { setBusy(false); }
  }
  async function borrar() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    setBusy(true);
    try {
      await window.HP.api.borrarResultado(row.lote_id, campanaId);
      toast('Cosecha real de ' + row.lote + ' borrada');
      await onSaved();
    } catch (e) { toast('Error: ' + (e.message || e)); }
    finally { setBusy(false); }
  }

  return (
    <tr>
      <td className="strong">{row.lote}</td>
      <td className="num mono">{row.tn_ha_predicho != null ? f2(row.tn_ha_predicho)
        : <span style={{ color: 'var(--muted)' }}>sin pred.</span>}</td>
      <td className="num"><input className="mono" style={inp} value={real} disabled={ro || busy} placeholder="—"
        onChange={(e) => setReal(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') guardar(); }} /></td>
      <td className="num"><input className="mono" style={inp} value={frutos} disabled={ro || busy} placeholder="—"
        onChange={(e) => setFrutos(e.target.value)} /></td>
      <td className="num"><input className="mono" style={inp} value={peso} disabled={ro || busy} placeholder="—"
        onChange={(e) => setPeso(e.target.value)} /></td>
      <td className="num mono">{f2(row.error_abs)}</td>
      <td className="num"><ErrBadge pct={row.error_pct} /></td>
      <td className="hstack">
        <button className="btn sm" onClick={guardar} disabled={ro || busy}>Guardar</button>
        {row.tiene_real && <button className="btn sm ghost" onClick={borrar} disabled={ro || busy}>Borrar</button>}
      </td>
    </tr>
  );
}

function ErrBadge({ pct }) {
  if (pct == null) return <span style={{ color: 'var(--muted)' }}>—</span>;
  const tone = pct <= 10 ? 'ok' : pct <= 25 ? 'warn' : 'crit';
  return <Badge tone={tone}>{pct.toFixed(1)}%</Badge>;
}

/* ===================== M6 — Labor ===================== */
function Labor() {
  const { toast } = useRouter();
  const ro = esCampanaCerrada();
  const mo = HP_B.manoObra;                       // config + semanas reales (o null)
  const hayPlan = HP_B.WEEKS.length > 0;
  const campanaId = HP_B.activeCampaign && HP_B.activeCampaign.id;

  // Parámetros: del backend si ya se configuró; si no, referencia La Joya (docs).
  // El rendimiento por jornal (Tn/día) NO se pide directo: el agricultor piensa en
  // "jabas que llena una persona al día" × "kg por jaba" → Tn/día = jabas·kg/1000.
  const [kgJaba, setKgJaba] = useState(() => 20);                       // canasta típica 20–25 kg
  const [jabasDia, setJabasDia] = useState(() => {
    const tn = (mo && mo.rendimiento_jornal) || 0.10;                   // 0.10 Tn ≈ 5 jabas de 20 kg
    return +((tn * 1000) / 20).toFixed(2);
  });
  const yieldPerDay = +(((jabasDia || 0) * (kgJaba || 0)) / 1000).toFixed(4);   // Tn/día derivado
  const [crewSize, setCrewSize] = useState(() => (mo && mo.tam_cuadrilla) || 6);
  const [avail, setAvail] = useState(() => (mo && mo.cuadrillas_disponibles) || 6);
  const [dias, setDias] = useState(() => (mo && mo.dias_cosecha_semana) || 6);
  const [busy, setBusy] = useState(false);

  // Filas REALES calculadas por el backend (jornales/cuadrillas/déficit por semana).
  const rows = (mo && mo.semanas) || [];
  const totalJornales = rows.reduce((a, r) => a + (r.jornales_req || 0), 0);
  const peak = rows.length ? Math.max(...rows.map(r => r.cuadrillas_req || 0)) : 0;
  const semDeficit = rows.filter(r => (r.deficit || 0) > 0).length;

  // Preview en vivo (client-side) del impacto de los parámetros sobre las semanas del
  // plan, ANTES de pulsar "Calcular". Misma fórmula que el backend (derivados.py M6).
  const denom = (crewSize || 0) * (dias || 0);
  const prev = HP_B.WEEKS.map(w => {
    const jornales = yieldPerDay > 0 ? (w.planned || 0) / yieldPerDay : 0;
    const cuadrillas = denom > 0 ? Math.ceil(jornales / denom - 1e-6) : 0;
    return { jornales, cuadrillas, deficit: Math.max(0, cuadrillas - (avail || 0)) };
  });
  const prevJornales = prev.reduce((a, p) => a + p.jornales, 0);
  const prevPeak = prev.length ? Math.max(...prev.map(p => p.cuadrillas)) : 0;
  const prevDeficit = prev.filter(p => p.deficit > 0).length;
  const crewDeficit = prevPeak > avail;
  const crewUtil = avail > 0 ? prevPeak / avail : (prevPeak > 0 ? 1 : 0);   // uso del personal en el pico
  const maxCuad = rows.length ? (Math.max(...rows.map(r => r.cuadrillas_req || 0)) || 1) : 1;

  async function calcular() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (!hayPlan) { toast('Genera primero el plan de cosecha (M5)'); return; }
    if (yieldPerDay <= 0) { toast('Indica jabas/día y kg por jaba (> 0)'); return; }
    setBusy(true);
    try {
      await HP_B.api.configManoObra(campanaId, {
        rendimiento_jornal: yieldPerDay, tam_cuadrilla: crewSize,
        cuadrillas_disponibles: avail, dias_cosecha_semana: dias,
      });
      await HP_B.api.refrescar();
      toast('Mano de obra recalculada ✓');
    } catch (e) {
      toast('Error: ' + (e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="M6 · Planificación de mano de obra"
        title="Mano de obra para cosecha"
        sub="A partir del plan semanal de cosecha, calcula jornales y cuadrillas necesarias. Compara contra las cuadrillas disponibles."
        actions={
          <button className="btn primary" disabled={ro || busy || !hayPlan} onClick={calcular}>
            {busy ? 'Calculando…' : 'Calcular requerimientos'} <Icon name="chev" size={14}/>
          </button>
        }
      />
      {!hayPlan && (
        <div className="card card-pad" style={{ marginBottom: 16, color: 'var(--muted)', fontSize: 13 }}>
          Esta campaña aún no tiene plan de cosecha. Genera el plan en <b>Planificación de cosecha</b> para calcular la mano de obra.
        </div>
      )}
      <div className="row-2" style={{ marginBottom: 16 }}>
        <div className="card card-pad">
          <div className="page-eyebrow" style={{ marginBottom: 10 }}>Parámetros de productividad</div>
          <div className="row-2">
            <div className="field"><label>Jabas por jornal al día</label><input type="number" min="0" step="0.5" value={jabasDia} disabled={ro} onChange={e=>setJabasDia(parseFloat(e.target.value))} /></div>
            <div className="field"><label>Kg por jaba</label><input type="number" min="0" step="1" value={kgJaba} disabled={ro} onChange={e=>setKgJaba(parseFloat(e.target.value))} /></div>
          </div>
          <div className="hint" style={{ marginBottom: 12 }}>
            Rendimiento por jornal: <b style={{ color: 'var(--ink)' }}>{yieldPerDay.toFixed(3)} Tn/día</b>
            {' '}({HP_B.fmtNum((jabasDia || 0) * (kgJaba || 0), 0)} kg/día por persona) — se calcula solo a partir de las jabas.
          </div>
          <div className="row-2">
            <div className="field"><label>Tamaño de cuadrilla</label><input type="number" value={crewSize} disabled={ro} onChange={e=>setCrewSize(parseInt(e.target.value))} /></div>
            <div className="field"><label>Cuadrillas disponibles</label><input type="number" value={avail} disabled={ro} onChange={e=>setAvail(parseInt(e.target.value))} /></div>
          </div>
          <div className="field"><label>Días de cosecha por semana</label><input type="number" min="1" max="7" value={dias} disabled={ro} onChange={e=>setDias(parseInt(e.target.value))} /></div>
          {hayPlan && (
            <div className="card-pad" style={{ background: 'var(--surface-2, #f6f5ef)', borderRadius: 8, fontSize: 12.5, marginBottom: 10 }}>
              <span style={{ color: 'var(--muted)' }}>Previsto con estos valores: </span>
              <b>{HP_B.fmtNum(prevJornales, 0)}</b> jornales · pico <b>{prevPeak}</b> cuadrillas
              {' · '}<b style={{ color: prevDeficit > 0 ? 'var(--crit, #c0392b)' : 'var(--ok)' }}>{prevDeficit}</b> semanas con déficit
              <span style={{ color: 'var(--muted)' }}> (pulsa Calcular para confirmar)</span>
            </div>
          )}
          <div className="hint">Referencia La Joya: ~5 jabas de 20 kg por jornal·día (≈0.10 Tn), cuadrillas de 6, 6 días/semana.</div>
        </div>

        <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="hstack" style={{ justifyContent: 'space-between' }}>
            <span className="page-eyebrow">Cuadrillas en la semana pico</span>
            {hayPlan && <Badge tone={crewDeficit ? 'crit' : 'olive'} dot>{crewDeficit ? 'Faltan cuadrillas' : 'Personal suficiente'}</Badge>}
          </div>
          <div className="hstack" style={{ justifyContent: 'center', gap: 18, padding: '6px 0' }}>
            <div style={{ textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 38, fontWeight: 600, lineHeight: 1, color: crewDeficit ? 'var(--crit,#9B2C1F)' : 'var(--primary,#4D7C0F)' }}>{prevPeak}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>requeridas (pico)</div>
            </div>
            <span style={{ color: crewDeficit ? 'var(--crit,#9B2C1F)' : 'var(--primary,#4D7C0F)' }}><Icon name="workers" size={40} /></span>
            <div style={{ textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 38, fontWeight: 600, lineHeight: 1, color: 'var(--ink)' }}>{avail}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>disponibles</div>
            </div>
          </div>
          <ResourceIcons need={prevPeak} avail={avail} icon="workers" />
          <div>
            <div className="hstack" style={{ justifyContent: 'space-between', fontSize: 12, color: 'var(--ink-3)', marginBottom: 6 }}>
              <span>Uso del personal (semana pico)</span>
              <span className="mono">{Math.round(crewUtil * 100)}%</span>
            </div>
            <div className="prog" style={{ width: '100%' }}>
              <span style={{ width: Math.min(100, crewUtil * 100) + '%', background: crewDeficit ? 'var(--crit,#9B2C1F)' : undefined }}></span>
            </div>
            <div className="hint" style={{ marginTop: 6 }}>{crewSize} personas por cuadrilla · {dias} días de cosecha/semana</div>
          </div>
        </div>
      </div>

      {/* KPIs (previsión en vivo) */}
      <div className="row-3" style={{ marginBottom: 16 }}>
        <Kpi label="Total jornales campaña" value={hayPlan ? HP_B.fmtNum(prevJornales, 0) : '—'} unit="jornales" foot={<span>{prev.length ? HP_B.fmtNum(prevJornales / prev.length, 0) + ' jornales/semana promedio' : 'sin plan'}</span>} />
        <Kpi label="Pico de cuadrillas/semana" value={hayPlan ? HP_B.fmtNum(prevPeak) : '—'} unit="cuadrillas" foot={crewDeficit ? <><span className="delta down">DÉFICIT</span><span>{prevPeak} req. / {avail} disp.</span></> : <span>dentro de capacidad</span>} />
        <Kpi label="Semanas con déficit" value={hayPlan ? String(prevDeficit) : '—'} unit={'de ' + prev.length} foot={<span>{avail} cuadrillas disponibles</span>} />
      </div>

      {/* Gráfico de cuadrillas por semana (datos guardados) */}
      {rows.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-head"><h3>Cuadrillas por semana</h3>
            <div className="right hstack" style={{ gap: 14, fontSize: 12, color: 'var(--ink-3)' }}>
              <Sem level="ok" label="Suficiente" /><Sem level="crit" label="Déficit" />
            </div>
          </div>
          <div className="card-pad">
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 150 }}>
              {rows.map(r => {
                const def = (r.deficit || 0) > 0;
                return (
                  <div key={r.semana_id} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end' }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>{r.cuadrillas_req}</span>
                    <div title={`S${r.numero_semana}: ${r.cuadrillas_req} cuadrillas · ${HP_B.fmtNum(r.jornales_req, 0)} jornales`}
                         style={{ width: '70%', height: ((r.cuadrillas_req || 0) / maxCuad * 100) + '%', minHeight: 4, borderRadius: '4px 4px 0 0',
                                  background: def ? 'var(--crit,#9B2C1F)' : 'linear-gradient(180deg,var(--primary),#6B9A1F)' }}></div>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>S{String(r.numero_semana).padStart(2,'0')}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-head"><h3>Requerimientos semanales</h3>
          <div className="right hstack" style={{ gap: 14, fontSize: 12, color: 'var(--ink-3)' }}>
            <Sem level="ok" label="Suficiente" />
            <Sem level="crit" label="Déficit" />
          </div>
        </div>
        {rows.length === 0 ? (
          <div className="card-pad" style={{ color: 'var(--muted)', fontSize: 13 }}>
            Aún no hay cálculo de mano de obra. Ajusta los parámetros y pulsa <b>Calcular requerimientos</b>.
          </div>
        ) : (
          <table className="tbl">
            <thead><tr>
              <th>Semana</th>
              <th className="num">Tn plan</th><th className="num">Jornales</th>
              <th className="num">Cuadrillas req.</th><th className="num">Disponibles</th>
              <th>Cobertura</th><th>Estado</th>
            </tr></thead>
            <tbody>
              {rows.map(r => {
                const def = r.deficit || 0;
                const pct = r.cuadrillas_req ? Math.min(100, (avail / r.cuadrillas_req) * 100) : 100;
                const level = def > 0 ? 'crit' : 'ok';
                return (
                  <tr key={r.semana_id} className={def > 0 ? 'def' : ''}>
                    <td className="strong mono">S{String(r.numero_semana).padStart(2,'0')}</td>
                    <td className="num">{HP_B.fmtNum(r.tn_planificada, 1)}</td>
                    <td className="num strong">{HP_B.fmtNum(r.jornales_req, 0)}</td>
                    <td className="num">{r.cuadrillas_req}</td>
                    <td className="num">{avail}</td>
                    <td>
                      <div className="hstack" style={{ gap: 8 }}>
                        <div className={'prog ' + (level === 'crit' ? 'crit' : '')} style={{ width: 120 }}>
                          <span style={{ width: pct + '%' }}></span>
                        </div>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{Math.round(pct)}%</span>
                      </div>
                    </td>
                    <td>
                      {def > 0 ? <Badge tone="crit" dot>Déficit {def}</Badge> : <Badge tone="olive" dot>OK</Badge>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ===================== M7 — Logistics ===================== */
function Logistics() {
  const { toast } = useRouter();
  const ro = esCampanaCerrada();
  const campanaId = HP_B.activeCampaign && HP_B.activeCampaign.id;
  const log = HP_B.logistica;                 // requerimiento por semana (real) o null
  const [tab, setTab] = useState('inventario');
  const [inv, setInv] = useState(() => HP_B.INVENTORY.map(it => ({ ...it })));
  const [busy, setBusy] = useState(false);

  function update(i, key, val) {
    const next = [...inv];
    next[i] = { ...next[i], [key]: key === 'item' || key === 'unit' ? val : (parseFloat(val) || 0) };
    setInv(next);
  }
  function addItem() {
    setInv([...inv, { item: '', unit: 'und', avail: 0, consumoPorTn: 0, required: 0, requiredTotal: 0 }]);
  }
  function removeItem(i) { setInv(inv.filter((_, k) => k !== i)); }

  async function guardar() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    const items = inv.filter(it => (it.item || '').trim()).map(it => ({
      material: it.item, cantidad_disponible: it.avail,
      unidad: it.unit, consumo_por_tn: it.consumoPorTn,
    }));
    setBusy(true);
    try {
      await HP_B.api.setInventario(campanaId, items);
      await HP_B.api.refrescar();
      toast('Inventario guardado ✓ (requerimientos recalculados)');
    } catch (e) {
      toast('Error: ' + (e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="M7 · Planificación logística"
        title="Materiales e insumos de cosecha"
        sub="Inventario disponible vs requerimientos calculados desde el plan de cosecha. El consumo por Tn define cuánto se gasta; el pico semanal manda."
        actions={
          <button className="btn primary" disabled={ro || busy} onClick={guardar}>
            {busy ? 'Guardando…' : 'Guardar inventario'} <Icon name="check" size={14}/>
          </button>
        }
      />
      <Tabs value={tab} onChange={setTab} items={[
        { id:'inventario', label:'Inventario' },
        { id:'requerimientos', label:'Requerimientos por semana' },
      ]}/>

      {tab === 'inventario' && (
        <>
          {inv.some(it => (it.item || '').trim()) && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-head"><h3>Cobertura de stock (pico semanal)</h3>
                <div className="right hstack" style={{ gap: 14, fontSize: 12, color: 'var(--ink-3)' }}>
                  <Sem level="ok" label="Suficiente" /><Sem level="warn" label="Bajo" /><Sem level="crit" label="Déficit" />
                </div>
              </div>
              <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
                {inv.filter(it => (it.item || '').trim()).map((it, i) => {
                  const req = it.required || 0;
                  const ratio = req ? it.avail / req : null;
                  const level = ratio == null ? 'neut' : ratio >= 1 ? 'ok' : ratio >= 0.75 ? 'warn' : 'crit';
                  const color = level === 'crit' ? 'var(--crit,#9B2C1F)' : level === 'warn' ? 'var(--warn,#B5530B)' : level === 'ok' ? 'var(--ok,#2F7D32)' : 'var(--muted)';
                  return (
                    <div key={i} style={{ border: '1px solid var(--line,#E5DFC9)', borderRadius: 10, padding: 12 }}>
                      <div className="hstack" style={{ gap: 8, marginBottom: 8 }}>
                        <span style={{ color }}><Icon name="crate" size={20} /></span>
                        <b style={{ fontSize: 13 }}>{it.item}</b>
                      </div>
                      <div className="prog" style={{ width: '100%' }}>
                        <span style={{ width: (ratio == null ? 0 : Math.min(100, ratio * 100)) + '%', background: color }}></span>
                      </div>
                      <div className="hstack" style={{ justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--ink-3)' }}>
                        <span className="mono">{HP_B.fmtNum(it.avail)} {it.unit || ''} disp.</span>
                        <span className="mono">{req ? HP_B.fmtNum(req) + ' req.' : 'sin cálculo'}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          <div className="card">
          <div className="card-head"><h3>Stock disponible</h3>
            <div className="right"><button className="btn ghost sm" disabled={ro} onClick={addItem}><Icon name="plus" size={12}/> Agregar ítem</button></div>
          </div>
          <table className="tbl">
            <thead><tr>
              <th>Ítem</th><th>Unidad</th>
              <th className="num">Consumo/Tn</th>
              <th className="num">Disponible</th>
              <th className="num">Req. pico/sem</th><th className="num">Diferencia</th>
              <th>Estado</th><th></th>
            </tr></thead>
            <tbody>
              {inv.map((it, i) => {
                const diff = it.avail - it.required;
                const ratio = it.required ? it.avail / it.required : 1;
                const level = ratio >= 1 ? 'ok' : ratio >= 0.75 ? 'warn' : 'crit';
                return (
                  <tr key={i}>
                    <td><input style={{ width: 130 }} value={it.item} disabled={ro} placeholder="material" onChange={e => update(i, 'item', e.target.value)} /></td>
                    <td><input className="mono" style={{ width: 64 }} value={it.unit} disabled={ro} onChange={e => update(i, 'unit', e.target.value)} /></td>
                    <td className="num"><input className="mono" style={{ width: 80, textAlign: 'right' }} value={it.consumoPorTn} disabled={ro} onChange={e => update(i, 'consumoPorTn', e.target.value)} /></td>
                    <td className="num"><input className="mono" style={{ width: 100, textAlign: 'right' }} value={it.avail} disabled={ro} onChange={e => update(i, 'avail', e.target.value)} /></td>
                    <td className="num">{HP_B.fmtNum(it.required)}</td>
                    <td className={'num strong ' + (diff < 0 ? 'delta down' : 'delta up')}>{diff >= 0 ? '+' : ''}{HP_B.fmtNum(diff)}</td>
                    <td>
                      {level === 'crit' && <Badge tone="crit" dot>Déficit crítico</Badge>}
                      {level === 'warn' && <Badge tone="warn" dot>Stock bajo</Badge>}
                      {level === 'ok'   && <Badge tone="olive" dot>OK</Badge>}
                    </td>
                    <td>{!ro && <button className="btn sm ghost" onClick={() => removeItem(i)} title="Quitar"><Icon name="trash" size={12}/></button>}</td>
                  </tr>
                );
              })}
              {inv.length === 0 && <tr><td colSpan={8} style={{ color: 'var(--muted)', fontSize: 13 }}>Sin materiales. Agrega ítems y guarda.</td></tr>}
            </tbody>
          </table>
          <div className="card-pad hint">Tras guardar, el backend reparte el consumo por las semanas del plan y marca déficit donde el pico supera el stock.</div>
          </div>
        </>
      )}

      {tab === 'requerimientos' && (
        <div className="card">
          <div className="card-head"><h3>Requerimiento de materiales por semana</h3>
            <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>
              {log && log.semanas ? `${log.semanas.length} semanas` : 'sin plan'}
            </div>
          </div>
          {!log || !log.semanas || !log.semanas.length ? (
            <div className="card-pad" style={{ color: 'var(--muted)', fontSize: 13 }}>
              No hay requerimientos: falta el plan de cosecha o el inventario. Genera el plan y guarda materiales.
            </div>
          ) : (
            <>
            <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14 }}>
              {(log.semanas[0].materiales || []).map((m0, mi) => {
                const serie = log.semanas.map(s => {
                  const mm = (s.materiales || []).find(x => x.material === m0.material) || {};
                  return { semana: s.numero_semana, req: mm.cantidad_requerida || 0, def: (mm.deficit || 0) > 0 };
                });
                const maxR = Math.max(...serie.map(x => x.req), 1);
                const totalReq = serie.reduce((a, x) => a + x.req, 0);
                return (
                  <div key={mi} style={{ border: '1px solid var(--line,#E5DFC9)', borderRadius: 10, padding: 12 }}>
                    <div className="hstack" style={{ gap: 8, marginBottom: 8, justifyContent: 'space-between' }}>
                      <span className="hstack" style={{ gap: 6 }}><Icon name="crate" size={16} /><b style={{ fontSize: 13 }}>{m0.material}</b></span>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>Σ {HP_B.fmtNum(totalReq, 0)}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 70 }}>
                      {serie.map((x, k) => (
                        <div key={k} title={`S${x.semana}: ${HP_B.fmtNum(x.req, 0)}${x.def ? ' (déficit)' : ''}`}
                             style={{ flex: 1, height: (x.req / maxR * 100) + '%', minHeight: 3, borderRadius: '2px 2px 0 0',
                                      background: x.def ? 'var(--crit,#9B2C1F)' : 'linear-gradient(180deg,var(--primary),#6B9A1F)' }}></div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <table className="tbl">
              <thead><tr>
                <th>Semana</th><th className="num">Tn plan</th>
                {(log.semanas[0].materiales || []).map((m, k) => <th key={k} className="num">{m.material}</th>)}
              </tr></thead>
              <tbody>
                {log.semanas.map(s => (
                  <tr key={s.semana_id} className={(s.materiales || []).some(m => (m.deficit||0) > 0) ? 'def' : ''}>
                    <td className="strong mono">S{String(s.numero_semana).padStart(2,'0')}</td>
                    <td className="num">{HP_B.fmtNum(s.tn_planificada, 1)}</td>
                    {(s.materiales || []).map((m, k) => (
                      <td key={k} className="num">
                        {HP_B.fmtNum(m.cantidad_requerida, 0)}
                        {(m.deficit || 0) > 0 && <span className="delta down mono" style={{ fontSize: 10, marginLeft: 6 }}>−{HP_B.fmtNum(m.deficit,0)}</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            </>
          )}
          <div className="card-pad hint">El número rojo es el déficit de esa semana (requerido − disponible). Esos déficits alimentan las alertas (M9).</div>
        </div>
      )}
    </div>
  );
}

/* ===================== M8 — Transport ===================== */
// Camión "cargable": el cajón se llena según la utilización de la flota en la
// semana pico (0–100%). Si hay déficit (pico > disponibles) se pinta en rojo.
function TruckGraphic({ fill = 0, deficit = false }) {
  const innerTop = 30, innerH = 52, innerX = 18, innerW = 120;
  const fh = Math.max(0, Math.min(1, fill));
  const rectY = innerTop + innerH - innerH * fh;
  const load = deficit ? 'var(--crit, #9B2C1F)' : 'var(--primary, #4D7C0F)';
  return (
    <svg width="100%" viewBox="0 0 240 130" style={{ maxWidth: 300 }}>
      <ellipse cx="118" cy="116" rx="104" ry="7" fill="rgba(0,0,0,0.08)" />
      {/* cajón de carga */}
      <rect x="12" y="24" width="132" height="64" rx="6" fill="#fff" stroke="var(--ink-3,#6A6347)" strokeWidth="2.5" />
      <clipPath id="truckLoadClip"><rect x={innerX} y={innerTop} width={innerW} height={innerH} rx="3" /></clipPath>
      <g clipPath="url(#truckLoadClip)">
        <rect x={innerX} y={rectY} width={innerW} height={innerH * fh} fill={load} opacity="0.9"
              style={{ transition: 'y .5s ease, height .5s ease, fill .3s ease' }} />
        <path d={`M${innerX} ${innerTop + innerH * 0.5} H${innerX + innerW}`} stroke="#fff" strokeWidth="1.5" opacity="0.45" />
      </g>
      {/* cabina */}
      <path d="M150 88 L150 48 Q150 44 154 44 L176 44 L198 70 L198 88 Z"
            fill="var(--primary-tint,#E8EFD3)" stroke="var(--ink-3,#6A6347)" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M176 50 L191 67 L176 67 Z" fill="#CFE0F5" stroke="var(--ink-3,#6A6347)" strokeWidth="1.5" strokeLinejoin="round" />
      {/* chasis + ruedas */}
      <rect x="12" y="88" width="186" height="6" rx="2" fill="var(--ink-3,#6A6347)" />
      {[58, 170].map(cx => (
        <g key={cx}>
          <circle cx={cx} cy="99" r="14" fill="#2C2C2C" />
          <circle cx={cx} cy="99" r="6" fill="#9A9A9A" />
        </g>
      ))}
    </svg>
  );
}

// Recurso (camiones/cuadrillas) como íconos: verde = disponible, rojo = requerido
// sin cubrir (déficit), gris = sin uso. Reutilizable en M6 y M8.
function ResourceIcons({ need, avail, icon = 'truck', size = 24 }) {
  const total = Math.max(need || 0, avail || 0, 1);
  const shown = Math.min(total, 16);
  const out = [];
  for (let i = 0; i < shown; i++) {
    const within = i < (avail || 0);
    const isShort = i >= (avail || 0) && i < (need || 0);
    const color = isShort ? 'var(--crit,#9B2C1F)' : (within ? 'var(--primary,#4D7C0F)' : 'var(--line,#DCD6C2)');
    out.push(
      <span key={i} title={isShort ? 'requerido (déficit)' : within ? 'disponible' : 'sin uso'} style={{ color, lineHeight: 0 }}>
        <Icon name={icon} size={size} />
      </span>
    );
  }
  return (
    <div className="hstack" style={{ flexWrap: 'wrap', gap: 7 }}>
      {out}
      {total > shown && <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>+{total - shown}</span>}
    </div>
  );
}

function Transport() {
  const { toast } = useRouter();
  const ro = esCampanaCerrada();
  const tr = HP_B.transporte;                  // config + semanas reales (o null)
  const hayPlan = HP_B.WEEKS.length > 0;
  const campanaId = HP_B.activeCampaign && HP_B.activeCampaign.id;

  // Parámetros: del backend si ya se configuró; si no, referencia La Joya (docs).
  const [cap, setCap] = useState(() => (tr && tr.cap_camion_tn) || 3.5);
  const [cost, setCost] = useState(() => (tr && tr.costo_por_viaje) || 250);
  const [trucks, setTrucks] = useState(() => (tr && tr.camiones_disponibles) || 2);
  const [tripsWk, setTripsWk] = useState(() => (tr && tr.viajes_por_camion_semana) || 12);
  const [busy, setBusy] = useState(false);

  // Filas REALES (guardadas por el backend) para la tabla y el gráfico.
  const rows = (tr && tr.semanas) || [];
  const totalCost = tr ? tr.costo_total : 0;
  const maxViajes = rows.length ? Math.max(...rows.map(r => r.viajes || 0)) || 1 : 1;

  // Previsión EN VIVO (client-side) con la MISMA fórmula del backend (derivados.py M8):
  // viajes = ceil(tn/cap) · camiones = ceil(viajes/viajes_sem) · déficit vs disponibles.
  const _ceil = (x) => Math.ceil(Math.round(x * 1e6) / 1e6);
  const prev = HP_B.WEEKS.map(w => {
    const tn = w.planned || 0;
    const viajes = cap > 0 && tn > 0 ? _ceil(tn / cap) : 0;
    const camiones = tripsWk > 0 && viajes > 0 ? _ceil(viajes / tripsWk) : 0;
    return { tn, viajes, camiones, costo: viajes * cost, deficit: Math.max(0, camiones - trucks) };
  });
  const prevTrips = prev.reduce((a, p) => a + p.viajes, 0);
  const prevCost = prev.reduce((a, p) => a + p.costo, 0);
  const prevPeak = prev.length ? Math.max(...prev.map(p => p.camiones)) : 0;
  const prevPeakTn = prev.length ? Math.max(...prev.map(p => p.tn)) : 0;
  const prevDeficit = prev.filter(p => p.deficit > 0).length;
  const capSemana = (trucks || 0) * (tripsWk || 0) * (cap || 0);    // Tn/semana que mueve la flota
  const util = capSemana > 0 ? prevPeakTn / capSemana : 0;
  const hayDeficit = prevPeak > trucks;

  async function calcular() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (!hayPlan) { toast('Genera primero el plan de cosecha (M5)'); return; }
    setBusy(true);
    try {
      await HP_B.api.configTransporte(campanaId, {
        cap_camion_tn: cap, costo_por_viaje: cost,
        camiones_disponibles: trucks, viajes_por_camion_semana: tripsWk,
      });
      await HP_B.api.refrescar();
      toast('Transporte recalculado ✓');
    } catch (e) {
      toast('Error: ' + (e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="M8 · Planificación de transporte"
        title="Despachos a packing"
        sub="Camiones, viajes y costo calculados a partir del plan de cosecha y los parámetros de la flota."
        actions={
          <button className="btn primary" disabled={ro || busy || !hayPlan} onClick={calcular}>
            {busy ? 'Calculando…' : 'Calcular despachos'} <Icon name="chev" size={14}/>
          </button>
        }
      />
      {!hayPlan && (
        <div className="card card-pad" style={{ marginBottom: 16, color: 'var(--muted)', fontSize: 13 }}>
          Esta campaña aún no tiene plan de cosecha. Genera el plan en <b>Planificación de cosecha</b> para calcular el transporte.
        </div>
      )}

      {/* Parámetros + camión cargable (previsión en vivo) */}
      <div className="row-2" style={{ marginBottom: 16 }}>
        <div className="card card-pad">
          <div className="page-eyebrow" style={{ marginBottom: 10 }}>Parámetros de la flota</div>
          <div className="row-2">
            <div className="field"><label>Capacidad por camión (Tn)</label><input type="number" step="0.5" value={cap} disabled={ro} onChange={e=>setCap(parseFloat(e.target.value) || 1)} /></div>
            <div className="field"><label>Costo por viaje (S/)</label><input type="number" value={cost} disabled={ro} onChange={e=>setCost(parseFloat(e.target.value) || 0)} /></div>
          </div>
          <div className="row-2">
            <div className="field"><label>Camiones disponibles</label><input type="number" value={trucks} disabled={ro} onChange={e=>setTrucks(parseInt(e.target.value) || 0)} /></div>
            <div className="field"><label>Viajes por camión/semana</label><input type="number" value={tripsWk} disabled={ro} onChange={e=>setTripsWk(parseInt(e.target.value) || 1)} /></div>
          </div>
          {hayPlan && (
            <div className="card-pad" style={{ background: 'var(--surface-2)', borderRadius: 8, fontSize: 12.5, marginTop: 4, marginBottom: 10 }}>
              <span style={{ color: 'var(--muted)' }}>Previsto: </span>
              <b>{HP_B.fmtNum(prevTrips)}</b> viajes · pico <b>{prevPeak}</b> camiones · <b>S/ {HP_B.fmtNum(prevCost)}</b>
              {' · '}<b style={{ color: prevDeficit > 0 ? 'var(--crit)' : 'var(--ok)' }}>{prevDeficit}</b> sem. con déficit
              <span style={{ color: 'var(--muted)' }}> (pulsa Calcular para guardar)</span>
            </div>
          )}
          <div className="hint">Referencia La Joya: camiones de 3–4 Tn (cap. 3.5), ~12 viajes/camión·semana.</div>
        </div>

        <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="hstack" style={{ justifyContent: 'space-between' }}>
            <span className="page-eyebrow">Flota en la semana pico</span>
            {hayPlan && <Badge tone={hayDeficit ? 'crit' : 'olive'} dot>{hayDeficit ? 'Déficit de camiones' : 'Flota suficiente'}</Badge>}
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
            <TruckGraphic fill={util} deficit={hayDeficit} />
          </div>
          <div>
            <div className="hstack" style={{ justifyContent: 'space-between', fontSize: 12, color: 'var(--ink-3)', marginBottom: 6 }}>
              <span>Uso de la flota (semana pico)</span>
              <span className="mono">{Math.round(util * 100)}%</span>
            </div>
            <div className="prog" style={{ width: '100%' }}>
              <span style={{ width: Math.min(100, util * 100) + '%', background: hayDeficit ? 'var(--crit,#9B2C1F)' : undefined }}></span>
            </div>
            <div className="hint" style={{ marginTop: 6 }}>
              Pico {HP_B.fmtNum(prevPeakTn, 1)} Tn/sem · capacidad flota {HP_B.fmtNum(capSemana, 1)} Tn/sem ({trucks}×{tripsWk}×{cap})
            </div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--ink-3)', marginBottom: 6 }}>
              Camiones: <b style={{ color: 'var(--ink)' }}>{prevPeak}</b> requeridos / {trucks} disponibles
            </div>
            <ResourceIcons need={prevPeak} avail={trucks} icon="truck" />
          </div>
        </div>
      </div>

      {/* KPIs (previsión en vivo) */}
      <div className="row-3" style={{ marginBottom: 16 }}>
        <Kpi label="Viajes totales campaña" value={hayPlan ? HP_B.fmtNum(prevTrips) : '—'} unit="viajes" foot={<span>{prev.length ? HP_B.fmtNum(prevTrips/prev.length,0) + ' promedio semanal' : 'sin plan'}</span>} />
        <Kpi label="Costo total estimado" value={hayPlan ? `S/ ${HP_B.fmtNum(prevCost)}` : '—'} unit="" foot={<span>S/ {HP_B.fmtNum(cost)} por viaje</span>} />
        <Kpi label="Camiones pico semanal" value={hayPlan ? String(prevPeak) : '—'} unit="camiones" foot={hayDeficit ? <><span className="delta down">DÉFICIT</span><span>{prevPeak} req. / {trucks} disp.</span></> : <span>{prevDeficit} semana(s) con déficit</span>} />
      </div>

      {/* Gráfico de viajes por semana (datos guardados) */}
      {rows.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-head"><h3>Viajes por semana</h3>
            <div className="right hstack" style={{ gap: 14, fontSize: 12, color: 'var(--ink-3)' }}>
              <Sem level="ok" label="Suficiente" /><Sem level="crit" label="Déficit" />
            </div>
          </div>
          <div className="card-pad">
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 150 }}>
              {rows.map(r => {
                const def = (r.deficit || 0) > 0;
                return (
                  <div key={r.semana_id} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end' }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>{r.viajes}</span>
                    <div title={`S${r.numero_semana}: ${r.viajes} viajes · ${r.camiones} camión(es)`}
                         style={{ width: '70%', height: ((r.viajes || 0) / maxViajes * 100) + '%', minHeight: 4, borderRadius: '4px 4px 0 0',
                                  background: def ? 'var(--crit,#9B2C1F)' : 'linear-gradient(180deg,var(--primary),#6B9A1F)' }}></div>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>S{String(r.numero_semana).padStart(2,'0')}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Tabla detalle (datos guardados) */}
      <div className="card">
        <div className="card-head"><h3>Plan semanal de transporte</h3>
          <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{trucks} camiones · {tripsWk} viajes/camión·sem</div>
        </div>
        {rows.length === 0 ? (
          <div className="card-pad" style={{ color: 'var(--muted)', fontSize: 13 }}>
            Aún no hay cálculo de transporte. Ajusta los parámetros y pulsa <b>Calcular despachos</b>.
          </div>
        ) : (
          <table className="tbl">
            <thead><tr>
              <th>Semana</th>
              <th className="num">Tn a despachar</th>
              <th className="num">Viajes</th>
              <th className="num">Camiones</th>
              <th className="num">Costo (S/)</th>
              <th>Estado</th>
            </tr></thead>
            <tbody>
              {rows.map(r => {
                const def = r.deficit || 0;
                return (
                  <tr key={r.semana_id} className={def > 0 ? 'def' : ''}>
                    <td className="strong mono">S{String(r.numero_semana).padStart(2,'0')}</td>
                    <td className="num strong">{HP_B.fmtNum(r.tn_despachadas, 1)}</td>
                    <td className="num">{r.viajes}</td>
                    <td className="num">{r.camiones}</td>
                    <td className="num strong">{HP_B.fmtNum(r.costo, 0)}</td>
                    <td>{def > 0 ? <Badge tone="crit" dot>Déficit {def}</Badge> : <Badge tone="olive" dot>OK</Badge>}</td>
                  </tr>
                );
              })}
              <tr style={{ background: 'var(--surface-2)' }}>
                <td className="strong">Total campaña</td>
                <td className="num strong">{HP_B.fmtNum(rows.reduce((a,r)=>a+(r.tn_despachadas||0),0), 1)}</td>
                <td className="num strong">{HP_B.fmtNum(rows.reduce((a,r)=>a+(r.viajes||0),0))}</td>
                <td className="num">—</td>
                <td className="num strong">S/ {HP_B.fmtNum(totalCost)}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ===================== M9 — Alerts ===================== */
function Alerts() {
  const { navigate, toast } = useRouter();
  const [filterMod, setFilterMod] = useState('todos');
  const [filterSev, setFilterSev] = useState('todas');
  const [resolved, setResolved] = useState({});

  const list = HP_B.ALERTS.filter(a => (filterMod === 'todos' || a.module === filterMod) && (filterSev === 'todas' || a.sev === filterSev));
  const active = list.filter(a => !resolved[a.id]);

  return (
    <div className="page">
      <PageHeader
        eyebrow="M9 · Sistema de alertas"
        title="Alertas activas"
        sub="Notificaciones de todos los módulos. Cada alerta sugiere una acción y queda asociada al sector o módulo de origen."
        actions={
          <>
            <select value={filterMod} onChange={e => setFilterMod(e.target.value)} style={{ height: 34, padding: '0 10px', border:'1px solid var(--border-2)', borderRadius: 8, background:'var(--surface)', fontFamily: 'inherit', fontSize: 13 }}>
              <option value="todos">Todos los módulos</option>
              {['Predicción IA','Mano de obra','Logística','Sectores','Transporte','Cosecha','Campañas'].map(m => <option key={m}>{m}</option>)}
            </select>
            <select value={filterSev} onChange={e => setFilterSev(e.target.value)} style={{ height: 34, padding: '0 10px', border:'1px solid var(--border-2)', borderRadius: 8, background:'var(--surface)', fontFamily: 'inherit', fontSize: 13 }}>
              <option value="todas">Todas las severidades</option>
              <option value="crit">Crítica</option><option value="warn">Atención</option><option value="info">Informativa</option>
            </select>
          </>
        }
      />

      <div className="row-3" style={{ marginBottom: 16 }}>
        <Kpi label="Críticas" value={HP_B.ALERTS.filter(a => a.sev === 'crit').length} unit="" foot={<span style={{ color: 'var(--crit)' }}>Requieren acción inmediata</span>} />
        <Kpi label="Atención" value={HP_B.ALERTS.filter(a => a.sev === 'warn').length} unit="" foot={<span style={{ color: 'var(--warn)' }}>Revisar en el día</span>} />
        <Kpi label="Resueltas hoy" value={Object.keys(resolved).length} unit="" foot={<span>{Object.keys(resolved).length === 0 ? 'Ninguna aún' : 'Buen trabajo'}</span>} />
      </div>

      <div className="card">
        {active.length === 0 ? (
          <div className="empty">Sin alertas activas con los filtros actuales.</div>
        ) : active.map(a => (
          <div key={a.id} className={'alert-item ' + a.sev}>
            <div className="stripe"></div>
            <div className="ico"><Icon name={a.sev === 'crit' ? 'bell' : a.sev === 'warn' ? 'leaf' : 'eye'} size={16} /></div>
            <div>
              <div className="hstack" style={{ gap: 10 }}>
                <div className="ttl">{a.title}</div>
                <Badge tone={a.sev === 'crit' ? 'crit' : a.sev === 'warn' ? 'warn' : 'neut'} dot>
                  {a.sev === 'crit' ? 'Crítica' : a.sev === 'warn' ? 'Atención' : 'Informativa'}
                </Badge>
                <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{a.id}</span>
              </div>
              <div className="desc">{a.desc}</div>
              <div className="meta">
                <span><span style={{ color: 'var(--ink-3)' }}>Módulo:</span> {a.module}</span>
                {a.sector !== '—' && <span><span style={{ color: 'var(--ink-3)' }}>Sector:</span> {a.sector}</span>}
                <span>{a.date}</span>
                <span><span style={{ color: 'var(--ink-3)' }}>Sugerencia:</span> {a.action}</span>
              </div>
            </div>
            <div className="hstack" style={{ gap: 6, alignSelf: 'center' }}>
              <button className="btn sm">{a.action}</button>
              <button className="btn sm ghost" onClick={() => { setResolved({ ...resolved, [a.id]: true }); toast('Alerta resuelta'); }}>
                <Icon name="check" size={12}/> Resolver
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, {
  Intelligence, IntelligenceResult,
  Harvest, HarvestCalendar,
  Labor, Logistics, Transport, Alerts,
});
