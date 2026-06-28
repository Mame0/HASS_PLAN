// HassPlan — modules A: Dashboard, Campaigns, Sectors, Intelligence, Harvest
const { SECTORS, CAMPAIGNS, WEEKS, ALERTS, INVENTORY, SECTOR_VARS, fmtNum } = window.HP;

/* ===================== M1 — Panel de Control Global (fundo) ===================== */
function GlobalDashboard() {
  const { navigate, toast } = useRouter();
  const f = window.HP.fundo;
  const fincas = window.HP.fincasList || [];
  // Clic en una finca = enfocar el panel en ella (cambia el contexto, como el selector
  // de la cabecera). Si ya es la activa, abre su gestión (CRUD). No altera datos.
  function abrirFinca(x) {
    if (x.id === window.HP.selectedFincaId) { navigate('fincas'); return; }
    window.HP.api.seleccionarFinca(x.id)
      .then(() => toast('Finca activa: ' + x.nombre))
      .catch((e) => toast('Error: ' + e.message));
  }
  // Sin fincas y sin datos del fundo: no hay nada que mostrar -> guía inicial.
  if ((!f || !f.n_campanas) && !fincas.length) {
    return (
      <div className="page">
        <PageHeader eyebrow="M1 · Panel de control global" title="Visión del fundo"
          sub="Analítica histórica consolidada de la unidad productiva." />
        <div className="card card-pad" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ marginBottom: 12, color: 'var(--muted)' }}><Icon name="dashboard" size={32} /></div>
          <h3 style={{ marginBottom: 6 }}>Aún no hay datos del fundo</h3>
          <p className="hint" style={{ marginBottom: 16 }}>Crea tu finca y campañas, registra lotes/predicciones y verás aquí la analítica histórica.</p>
          <div className="hstack" style={{ justifyContent: 'center', gap: 8 }}>
            <button className="btn primary" onClick={() => navigate('fincas')}><Icon name="map" size={14}/> Crear finca</button>
            <button className="btn ghost" onClick={() => navigate('campaigns')}><Icon name="campaign" size={14}/> Ir a campañas</button>
          </div>
        </div>
      </div>
    );
  }
  const ff = f || {};
  const nombre = (ff.fundo && ff.fundo.nombre) || 'Fundo';
  const distrito = (ff.fundo && ff.fundo.distrito) || '';
  const tend = ff.tendencia || [];
  const maxTn = Math.max(1, ...tend.map(t => t.tn_total || 0));
  const rec = ff.recursos || {};
  const nCamp = ff.n_campanas || 0;
  const selId = window.HP.selectedFincaId;
  // Mapa consolidado: dibuja TODAS las fincas reales desde su geometría/centroide.
  const fincasMapa = fincas.map(x => ({
    geometria: x.geometria, name: x.nombre,
    lat: x.centro_lat, lon: x.centro_lon, status: 'ok',
  }));
  const conGeo = fincasMapa.some(x => x.geometria || (x.lat != null && x.lon != null));

  return (
    <div className="page">
      <PageHeader
        eyebrow="M1 · Panel de control global"
        title={`${nombre} — visión del fundo`}
        sub={`${distrito ? distrito + ' · ' : ''}Métricas consolidadas a través de ${nCamp} ${nCamp === 1 ? 'campaña' : 'campañas'}.`}
        actions={<>
          <button className="btn ghost sm" onClick={() => navigate('fincas')}><Icon name="map" size={14}/> Fincas</button>
          <button className="btn ghost sm" onClick={() => navigate('campaigns')}><Icon name="campaign" size={14}/> Campañas</button>
        </>}
      />

      {/* KPIs consolidados */}
      <div className="kpi-grid" style={{ marginBottom: 16 }}>
        <Kpi icon="map" label="Área total de cultivo" value={fmtNum(ff.area_total_ha, 1)} unit="Ha" foot={<span>lotes operativos del fundo</span>} />
        <Kpi icon="harvest" label="Histórico de producción" value={fmtNum(ff.historico_tn)} unit="Tn" foot={<span>real + proyectada, todas las campañas</span>} />
        <Kpi icon="leaf" label="Rendimiento global" value={ff.tn_ha_global != null ? fmtNum(ff.tn_ha_global, 1) : '—'} unit="Tn/Ha" foot={<span>promedio histórico de la tierra</span>} />
        <Kpi icon="campaign" label="Campañas registradas" value={`${nCamp}`} unit="" foot={<span>periodos fiscales</span>} />
      </div>

      {/* Fincas del productor — foto visual del fundo (datos reales de /fincas) */}
      <div className="row-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>Mapa del fundo</h3>
            <div className="right mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
              {fincas.length} {fincas.length === 1 ? 'finca' : 'fincas'}
            </div>
          </div>
          <div className="card-pad">
            {conGeo
              ? <LeafletMap height={300} lotes={fincasMapa} />
              : <div className="empty">Dibuja el contorno de tus fincas (en “Fincas”) para verlas en el mapa.</div>}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>Fincas</h3>
            <div className="right">
              <button className="btn ghost sm" onClick={() => navigate('fincas')}>Gestionar <Icon name="chev" size={12} /></button>
            </div>
          </div>
          <div className="finca-grid">
            {fincas.map(x => (
              <div key={x.id} className={'finca-card' + (x.id === selId ? ' sel' : '')}
                   onClick={() => abrirFinca(x)} title={x.id === selId ? 'Gestionar fincas' : 'Ver esta finca'}>
                <div className="fc-ico"><Icon name="map" size={16} /></div>
                <div style={{ minWidth: 0 }}>
                  <div className="fc-name">
                    {x.nombre}{x.id === selId && <span className="fc-badge">activa</span>}
                  </div>
                  <div className="fc-sub"><Icon name="map" size={11} /> {x.distrito || 'Sin distrito'}</div>
                </div>
                <div className="fc-stats">
                  <div className="fc-stat"><b>{x.area_total_ha != null ? fmtNum(x.area_total_ha, 1) : '—'}</b><span>Ha</span></div>
                  <div className="fc-stat"><b>{x.n_lotes != null ? x.n_lotes : '—'}</b><span>lotes</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="row-2">
        {/* Tendencia multicampaña */}
        <div className="card">
          <div className="card-head">
            <h3>Tendencia de producción por campaña</h3>
            <div className="right" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              <span className="hstack" style={{ gap: 14 }}>
                <span className="hstack" style={{ gap: 6 }}>
                  <span style={{ display:'inline-block', width:12, height:8, background:'linear-gradient(90deg,var(--primary),#6B9A1F)', borderRadius:2 }}></span>
                  Real
                </span>
                <span className="hstack" style={{ gap: 6 }}>
                  <span style={{ display:'inline-block', width:12, height:8, background:'repeating-linear-gradient(45deg,#D6CFB4 0 4px,#C9C1A1 4px 8px)' }}></span>
                  Proyectada
                </span>
              </span>
            </div>
          </div>
          <div className="card-pad">
            {tend.length ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {tend.map(t => (
                  <div className="bar-row" key={t.campana_id}>
                    <span className="lbl" title={t.nombre} style={{ width: 120 }}>{t.nombre}</span>
                    <div className="bar-cell">
                      <span className={t.tipo === 'real' ? 'real' : 'planned'} style={{ width: `${((t.tn_total || 0) / maxTn) * 100}%` }}></span>
                    </div>
                    <span className="tnum mono" style={{ fontSize: 11, color: 'var(--ink-3)', textAlign: 'right' }}>
                      <span style={{ color: 'var(--ink)' }}>{fmtNum(t.tn_total)} Tn</span>
                      {t.tn_ha != null && <> · {fmtNum(t.tn_ha, 1)} Tn/Ha</>}
                    </span>
                  </div>
                ))}
              </div>
            ) : <div className="empty">Sin campañas para comparar todavía.</div>}
            <div className="hint" style={{ marginTop: 10 }}>Las campañas sin cosecha cerrada se muestran con su producción <b>proyectada</b> (modelo).</div>
          </div>
        </div>

        {/* Consolidado de recursos del fundo — totales históricos (sin barra: no son
            un ratio disponible/requerido, así que se muestran como cifra directa). */}
        <div className="card">
          <div className="card-head"><h3>Consolidado de recursos del fundo</h3></div>
          <div style={{ padding: '6px' }}>
            <div className="fundo-stat-row">
              <span><Icon name="workers" size={14} /> Mano de obra contratada (histórico)</span>
              <b>{fmtNum(rec.jornales_acumulados || 0, 0)} <span>jornales</span></b>
            </div>
            <div className="fundo-stat-row">
              <span><Icon name="truck" size={14} /> Costo logístico/transporte acumulado</span>
              <b><span>S/</span> {fmtNum(rec.costo_logistico_acumulado || 0)}</b>
            </div>
            <div className="hint" style={{ padding: '10px 12px' }}>Acumulado de jornales y costos de transporte imputados a las {nCamp} {nCamp === 1 ? 'campaña' : 'campañas'} de la finca.</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============== Resumen de Campaña (ex-Dashboard, ahora en el contexto de campaña) ============== */
function ViewCampaignSummary() {
  const { navigate } = useRouter();
  // Sin campañas, o ninguna activa: no hay datos que resumir -> empty state guía.
  const activa = window.HP.activeCampaign || CAMPAIGNS.find(c => c.status === 'Activa');
  if (!CAMPAIGNS.length || !activa) {
    return (
      <div className="page">
        <PageHeader eyebrow="M2 · Resumen de campaña" title="Resumen de campaña"
          sub="Esta vista muestra producción, avance, recursos y alertas de la campaña seleccionada." />
        <div className="card card-pad" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ marginBottom: 12, color: 'var(--muted)' }}><Icon name="campaign" size={32} /></div>
          <h3 style={{ marginBottom: 6 }}>{CAMPAIGNS.length ? 'No hay ninguna campaña activa' : 'Aún no hay campañas'}</h3>
          <p className="hint" style={{ marginBottom: 16 }}>
            {CAMPAIGNS.length
              ? 'Activa una campaña en la sección Campañas para ver aquí sus KPIs, lotes y alertas.'
              : 'Crea tu primera campaña para empezar a registrar lotes y variables.'}
          </p>
          <div className="hstack" style={{ justifyContent: 'center', gap: 8 }}>
            {CAMPAIGNS.length
              ? <button className="btn primary" onClick={() => navigate('campaigns')}><Icon name="campaign" size={14}/> Ir a campañas</button>
              : <button className="btn primary" onClick={() => navigate('campaign_new')}><Icon name="plus" size={14}/> Crear campaña</button>}
          </div>
        </div>
      </div>
    );
  }
  // KPIs derivados de los datos reales (window.HP, ya cargado por api.js).
  const projected = Math.round(WEEKS.reduce((a, w) => a + (w.planned || 0), 0));
  const harvested = Math.round(WEEKS.reduce((a, w) => a + (w.real || 0), 0));
  const advance = projected ? Math.round((harvested / projected) * 100) : 0;
  const avgYield = SECTORS.length
    ? (SECTORS.reduce((a, s) => a + (s.expectedYieldHa || 0), 0) / SECTORS.length)
    : 0;
  // Panel "Recursos al pico" desde el dashboard real (M6/M7/M8).
  const dash = window.HP.dashboard || {};
  const mo = dash.mano_obra || {};
  const tr = dash.transporte || {};
  const rLevel = (d, r) => { const x = r ? d / r : 1; return x >= 1 ? 'ok' : x >= 0.85 ? 'warn' : 'crit'; };
  const rPct = (d, r) => (r ? Math.min(100, Math.round((d / r) * 100)) : 100);

  // --- Metadatos de cabecera (datos ya reales: campaña activa + lotes) ---
  const estado = activa.status || (activa.estado ? activa.estado[0].toUpperCase() + activa.estado.slice(1) : '—');
  const estadoTone = estado === 'Activa' ? 'olive' : estado === 'Cerrada' ? 'neut' : 'warn';
  const ventana = `${activa.start || activa.fecha_inicio || '—'} → ${activa.end || activa.fecha_fin || '—'}`;
  const areaTotal = SECTORS.reduce((a, s) => a + (s.area || 0), 0);
  const semanasPlan = (dash.cosecha && dash.cosecha.semanas_total) || WEEKS.length;
  // Conteo de alertas activas por severidad (real: lista ALERTS ya adaptada de /api).
  const sevCount = ALERTS.reduce((acc, a) => { acc[a.sev] = (acc[a.sev] || 0) + 1; return acc; }, {});
  const peakWeek = dash.cosecha ? dash.cosecha.semana_pico : null;
  // Escala del gráfico: una sola pasada, con piso 1 para no dividir entre cero.
  const maxTn = Math.max(1, ...WEEKS.map(x => x.planned || 0));

  return (
    <div className="page">
      <PageHeader
        eyebrow="M2 · Resumen de campaña"
        title={`Resumen — ${activa.name || activa.nombre || 'campaña activa'}`}
        sub="Producción, avance, recursos y alertas de la campaña seleccionada en la cabecera."
        actions={<button className="btn ghost sm" onClick={() => navigate('campaigns')}><Icon name="campaign" size={14} /> Gestionar campañas</button>}
      />

      {/* Tira de metadatos de la campaña (estado · ventana · lotes · área · semanas) */}
      <div className="summary-meta">
        <div className="m-item">
          <span className="m-k">Estado</span>
          <span className="m-v"><Badge tone={estadoTone} dot={estado === 'Activa'}>{estado}</Badge></span>
        </div>
        <div className="m-item">
          <span className="m-k">Ventana</span>
          <span className="m-v"><span className="mono">{ventana}</span></span>
        </div>
        <div className="m-item">
          <span className="m-k">Lotes en producción</span>
          <span className="m-v">{SECTORS.length} <span className="mono" style={{ color: 'var(--muted)' }}>· {fmtNum(areaTotal, 1)} Ha</span></span>
        </div>
        <div className="m-item">
          <span className="m-k">Plan de cosecha</span>
          <span className="m-v">{semanasPlan} <span className="mono" style={{ color: 'var(--muted)' }}>semanas</span></span>
        </div>
        <div className="m-item">
          <span className="m-k">Alertas activas</span>
          <span className="m-v">
            {ALERTS.length
              ? <span className="hstack" style={{ gap: 6 }}>
                  {sevCount.crit ? <Badge tone="crit">{sevCount.crit} crít.</Badge> : null}
                  {sevCount.warn ? <Badge tone="warn">{sevCount.warn} med.</Badge> : null}
                  {sevCount.info ? <Badge tone="neut">{sevCount.info} baja</Badge> : null}
                </span>
              : <Badge tone="ok" dot>Sin alertas</Badge>}
          </span>
        </div>
      </div>

      {/* KPIs */}
      <div className="kpi-grid" style={{ marginBottom: 16 }}>
        <Kpi icon="harvest" label="Producción proyectada" value={fmtNum(projected)} unit="Tn" foot={<span>Σ del plan semanal de cosecha</span>} />
        <Kpi icon="crate" label="Producción cosechada" value={fmtNum(harvested)} unit="Tn" foot={<span>real registrada hasta hoy</span>} />
        <div className="kpi hstack" style={{ gap: 14, alignItems: 'center' }}>
          <Donut pct={advance / 100} label="avance" color={advance >= 100 ? 'var(--ok,#2F7D32)' : 'var(--primary,#4D7C0F)'} />
          <div>
            <div className="k-label">Avance de campaña</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 4 }}>{fmtNum(harvested)} / {fmtNum(projected)} Tn</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{projected ? 'cosechado vs. plan' : 'sin plan de cosecha aún'}</div>
          </div>
        </div>
        <Kpi icon="leaf" label="Rendimiento promedio" value={avgYield.toFixed(1)} unit="Tn/Ha" foot={<span>promedio de los lotes predichos</span>} />
      </div>

      <div className="row-2" style={{ marginBottom: 16 }}>
        {/* Bar chart */}
        <div className="card">
          <div className="card-head">
            <h3>Semanas de cosecha — real vs planificado</h3>
            <div className="right" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              <span className="hstack" style={{ gap: 14 }}>
                <span className="hstack" style={{ gap: 6 }}>
                  <span style={{ display:'inline-block', width:12, height:8, background:'repeating-linear-gradient(45deg,#D6CFB4 0 4px,#C9C1A1 4px 8px)' }}></span>
                  Plan
                </span>
                <span className="hstack" style={{ gap: 6 }}>
                  <span style={{ display:'inline-block', width:12, height:8, background:'linear-gradient(90deg,var(--primary),#6B9A1F)', borderRadius: 2 }}></span>
                  Real
                </span>
              </span>
            </div>
          </div>
          <div className="card-pad">
            {WEEKS.length ? (
              <>
                <div style={{ display: 'grid', gap: 8 }}>
                  {WEEKS.map(w => {
                    const pPct = ((w.planned || 0) / maxTn) * 100;
                    const realPct = w.real ? (w.real / maxTn) * 100 : 0;
                    const isPeak = peakWeek != null && w.week === peakWeek;
                    return (
                      <div className={'bar-row' + (isPeak ? ' is-peak' : '')} key={w.week}>
                        <span className="lbl">{w.label}{isPeak && <span className="peak-tag">pico</span>}</span>
                        <div className="bar-cell">
                          <span className="planned" style={{ width: `${pPct}%` }}></span>
                          {w.real != null && <span className="real" style={{ width: `${realPct}%` }}></span>}
                        </div>
                        <span className="tnum mono" style={{ fontSize: 11, color: 'var(--ink-3)', textAlign:'right' }}>
                          {w.real != null ? `${w.real} / ` : '— / '}<span style={{ color: 'var(--ink)' }}>{w.planned} Tn</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="chart-foot">
                  <span>Plan total <b>{fmtNum(projected)} Tn</b></span>
                  <span>Cosechado <b>{fmtNum(harvested)} Tn</b></span>
                  <span>Avance <b>{advance}%</b></span>
                </div>
              </>
            ) : (
              <div className="empty">Genera el plan de cosecha (M5) para ver el desglose semanal real vs. planificado.</div>
            )}
          </div>
        </div>

        {/* Alerts panel */}
        <div className="card">
          <div className="card-head">
            <h3>Alertas activas{ALERTS.length ? ` (${ALERTS.length})` : ''}</h3>
            <div className="right">
              <button className="btn ghost sm" onClick={() => navigate('alerts')}>Ver todas <Icon name="chev" size={12} /></button>
            </div>
          </div>
          <div>
            {ALERTS.length ? ALERTS.slice(0, 5).map(a => (
              <div key={a.id} className={'alert-item ' + a.sev} onClick={() => navigate('alerts')} style={{ cursor: 'pointer' }}>
                <div className="stripe"></div>
                <div className="ico"><Icon name={a.sev === 'crit' ? 'bell' : a.sev === 'warn' ? 'leaf' : 'eye'} size={16} /></div>
                <div>
                  <div className="ttl">{a.title}</div>
                  {a.desc && <div className="desc">{a.desc}</div>}
                  <div className="meta">
                    <span>{a.module}</span><span>·</span><span>{a.date}</span>
                  </div>
                </div>
                <span className="pill" style={{ alignSelf: 'center' }}>{a.action}</span>
              </div>
            )) : (
              <div className="empty">Sin alertas activas. La campaña está dentro de sus parámetros operativos ✓</div>
            )}
          </div>
        </div>
      </div>

      <div className="row-2">
        {/* Map */}
        <div className="card">
          <div className="card-head">
            <h3>Lotes en producción</h3>
            <div className="right" style={{ color: 'var(--ink-3)', fontSize: 12 }}>
              <span className="mono">{SECTORS.length} lotes · {fmtNum(areaTotal, 1)} Ha</span>
            </div>
          </div>
          <div className="card-pad">
            {SECTORS.length
              ? <LeafletMap height={320} lotes={SECTORS} />
              : <div className="empty">Aún no hay lotes en esta campaña. Agrégalos desde la sección de lotes.</div>}
          </div>
        </div>

        {/* Resources */}
        <div className="card">
          <div className="card-head">
            <h3>Recursos para el pico{dash.cosecha && peakWeek != null ? ` (S${String(peakWeek).padStart(2, '0')})` : ''}</h3>
            <div className="right mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
              {dash.cosecha ? `${fmtNum(dash.cosecha.tn_pico, 1)} Tn` : '—'}</div>
          </div>
          <div style={{ padding: '8px 6px' }}>
            {mo.cuadrillas_pico != null && (
              <ResourceRow label="Cuadrillas" detail={`${mo.cuadrillas_disponibles} disp. / ${mo.cuadrillas_pico} req.`}
                level={rLevel(mo.cuadrillas_disponibles, mo.cuadrillas_pico)} pct={rPct(mo.cuadrillas_disponibles, mo.cuadrillas_pico)} />
            )}
            {tr.camiones_pico != null && (
              <ResourceRow label="Camiones" detail={`${tr.camiones_disponibles} disp. / ${tr.camiones_pico} req.`}
                level={rLevel(tr.camiones_disponibles, tr.camiones_pico)} pct={rPct(tr.camiones_disponibles, tr.camiones_pico)} />
            )}
            {INVENTORY.map(it => (
              <ResourceRow key={it.item} label={it.item} detail={`${fmtNum(it.avail)} / ${fmtNum(it.required)} req.`}
                level={rLevel(it.avail, it.required)} pct={rPct(it.avail, it.required)} />
            ))}
            {(mo.cuadrillas_pico == null && !INVENTORY.length) && (
              <div className="empty">Configura mano de obra, logística y transporte para ver los recursos.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, unit, foot, icon }) {
  return (
    <div className="kpi">
      <div className="hstack" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div className="k-label">{label}</div>
        {icon && <span style={{ color: 'var(--primary,#4D7C0F)', flexShrink: 0 }}><Icon name={icon} size={15} /></span>}
      </div>
      <div className="k-value">{value}<span className="unit">{unit}</span></div>
      <div className="k-foot">{foot}</div>
    </div>
  );
}

// Anillo de progreso (confianza / avance / uso). SVG puro, sin dependencias.
function Donut({ pct = 0, size = 66, stroke = 8, color = 'var(--primary,#4D7C0F)', label }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(1, pct || 0));
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2,#F3ECDB)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
                strokeDasharray={`${c * p} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
                style={{ transition: 'stroke-dasharray .5s ease' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span className="mono" style={{ fontSize: size * 0.24, fontWeight: 600, color: 'var(--ink)' }}>{Math.round(p * 100)}%</span>
        {label && <span style={{ fontSize: 9, color: 'var(--muted)' }}>{label}</span>}
      </div>
    </div>
  );
}

function ResourceRow({ label, detail, level, pct }) {
  return (
    <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
      <div className="hstack" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, color: 'var(--ink)', fontWeight: 500 }}>{label}</span>
        <Sem level={level} label={detail} />
      </div>
      <div className={'prog ' + (level === 'crit' ? 'crit' : level === 'warn' ? 'warn' : '')}><span style={{ width: pct + '%' }}></span></div>
    </div>
  );
}

function SectorMap() {
  // Coordinates as % of map area
  const lots = [
    { id:'S-01', x: 18, y: 28, w: 18, h: 22, sem:'ok' },
    { id:'S-02', x: 38, y: 18, w: 14, h: 20, sem:'ok' },
    { id:'S-03', x: 56, y: 22, w: 20, h: 24, sem:'warn' },
    { id:'S-04', x: 22, y: 56, w: 22, h: 22, sem:'ok' },
    { id:'S-05', x: 48, y: 52, w: 14, h: 18, sem:'ok' },
    { id:'S-06', x: 66, y: 56, w: 18, h: 24, sem:'crit' },
  ];
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position:'absolute', inset:0, width:'100%', height:'100%' }}>
      {lots.map(l => {
        const fill = l.sem === 'crit' ? 'rgba(155,44,31,0.55)' : l.sem === 'warn' ? 'rgba(201,122,33,0.55)' : 'rgba(77,124,15,0.55)';
        const stroke = l.sem === 'crit' ? '#7A1F12' : l.sem === 'warn' ? '#8C520F' : '#2C4E03';
        // slight irregular polygon
        const pts = [
          [l.x, l.y + 2],
          [l.x + l.w - 3, l.y],
          [l.x + l.w, l.y + l.h - 4],
          [l.x + 3, l.y + l.h],
        ].map(p => p.join(',')).join(' ');
        return (
          <g key={l.id}>
            <polygon points={pts} fill={fill} stroke={stroke} strokeWidth="0.4" />
            <text x={l.x + l.w/2} y={l.y + l.h/2} textAnchor="middle" fontSize="2.6" fill="#FBF7E9" fontFamily="Geist Mono" style={{ fontWeight: 500 }}>{l.id}</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ===================== M2 — Campaigns ===================== */
function Campaigns() {
  const { navigate, toast } = useRouter();
  function abrir(c) { window.HP.selectedCampaignId = c.id; navigate('campaign_det'); }
  async function activar(e, c) {
    e.stopPropagation();
    try { await window.HP.api.activarCampana(c.id); await window.HP.api.refrescar(); toast('Campaña activada ✓'); navigate('campaigns'); }
    catch (err) { toast('Error al activar: ' + err.message); }
  }
  async function eliminar(e, c) {
    e.stopPropagation();
    if (!confirm('¿Eliminar la campaña "' + c.name + '"? Se borrarán sus registros, predicciones y planes.')) return;
    try { await window.HP.api.eliminarCampana(c.id); await window.HP.api.refrescar(); toast('Campaña eliminada ✓'); navigate('campaigns'); }
    catch (err) { toast('Error al eliminar: ' + err.message); }
  }
  return (
    <div className="page">
      <PageHeader
        eyebrow="M2 · Gestión de campañas"
        title="Campañas"
        sub="Solo una campaña puede estar activa a la vez. Las campañas cerradas son consultables como histórico."
        actions={
          <>
            <button className="btn ghost"><Icon name="filter" size={14}/> Filtrar</button>
            <button className="btn primary" onClick={() => navigate('campaign_new')}><Icon name="plus" size={14}/> Nueva campaña</button>
          </>
        }
      />
      <div className="card">
        <table className="tbl">
          <thead><tr>
            <th>Código</th><th>Nombre</th><th>Inicio</th><th>Cierre</th>
            <th className="num">Lotes</th><th className="num">Área (Ha)</th>
            <th className="num">Plan (Tn)</th><th className="num">Cosechado (Tn)</th>
            <th>Estado</th><th className="num">Acciones</th>
          </tr></thead>
          <tbody>
            {CAMPAIGNS.map(c => (
              <tr key={c.id} onClick={() => abrir(c)} style={{ cursor: 'pointer' }}>
                <td className="mono" style={{ color: 'var(--ink-3)' }}>{c.id}</td>
                <td className="strong">{c.name}</td>
                <td className="mono">{c.start || '—'}</td>
                <td className="mono">{c.end || '—'}</td>
                <td className="num">{c.sectors || '—'}</td>
                <td className="num">{c.area ? fmtNum(c.area, 1) : '—'}</td>
                <td className="num">{c.plannedTons ? fmtNum(c.plannedTons) : '—'}</td>
                <td className="num">{c.harvestedTons ? fmtNum(c.harvestedTons) : '—'}</td>
                <td>
                  {c.status === 'Activa' && <Badge tone="olive" dot>Activa</Badge>}
                  {c.status === 'Cerrada' && <Badge tone="neut">Cerrada</Badge>}
                  {c.status === 'Borrador' && <Badge tone="warn">Borrador</Badge>}
                </td>
                <td className="num" onClick={e => e.stopPropagation()}>
                  <div className="hstack" style={{ justifyContent: 'flex-end', gap: 6 }}>
                    {c.status !== 'Activa' && (
                      <button className="btn sm ghost" onClick={e => activar(e, c)}><Icon name="check" size={12}/> Activar</button>
                    )}
                    <button className="btn sm ghost" onClick={e => eliminar(e, c)} title="Eliminar"><Icon name="trash" size={12}/></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CampaignNew() {
  const { navigate, toast } = useRouter();
  // Modo edición si hay una campaña marcada para editar (reusa esta misma vista).
  const editId = window.HP.editingCampaignId;
  const editC = editId ? CAMPAIGNS.find(x => x.id === editId) : null;
  const [name, setName] = useState(editC ? editC.name : 'Campaña Hass 2026–27');
  const [start, setStart] = useState(editC ? editC.start : '2026-09-01');
  const [end, setEnd] = useState(editC ? editC.end : '2027-04-30');
  const [saving, setSaving] = useState(false);

  function limpiarEdicion() { window.HP.editingCampaignId = null; }
  function cancelar() { limpiarEdicion(); navigate('campaigns'); }

  async function guardar() {
    if (!name.trim()) { toast('Falta el nombre'); return; }
    setSaving(true);
    try {
      const body = { nombre: name.trim(), fecha_inicio: start, fecha_fin: end };
      if (editC) {
        await window.HP.api.editarCampana(editC.id, body);
        await window.HP.api.refrescar();
        limpiarEdicion();
        toast('Campaña actualizada ✓');
        navigate('campaign_det');
      } else {
        await window.HP.api.crearCampana(body);
        await window.HP.api.refrescar();
        toast('Borrador creado ✓');
        navigate('campaigns');
      }
    } catch (e) {
      toast('Error al guardar: ' + e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <PageHeader eyebrow={editC ? 'M2 · Editar campaña' : 'M2 · Nueva campaña'}
        title={editC ? 'Editar campaña' : 'Crear campaña'}
        sub={editC ? 'Modifica el nombre y la ventana de la campaña.' : 'La campaña queda en estado Borrador hasta que la actives.'} />
      <div className="card card-pad">
        <div className="field">
          <label>Nombre</label>
          <input value={name} onChange={e => setName(e.target.value)} />
        </div>
        <div className="row-2">
          <div className="field">
            <label>Fecha de inicio</label>
            <input type="date" value={start} onChange={e => setStart(e.target.value)} />
          </div>
          <div className="field">
            <label>Fecha de cierre</label>
            <input type="date" value={end} onChange={e => setEnd(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Notas</label>
          <textarea placeholder="Objetivos, supuestos, contexto climático esperado…"></textarea>
        </div>
        <div className="hstack" style={{ justifyContent: 'flex-end', marginTop: 8 }}>
          <button className="btn ghost" onClick={cancelar}>Cancelar</button>
          <button className="btn primary" onClick={guardar} disabled={saving}>
            {saving ? 'Guardando…' : (editC ? 'Guardar cambios' : 'Crear borrador')}
          </button>
        </div>
      </div>
    </div>
  );
}

function CampaignDetail() {
  const { navigate, toast } = useRouter();
  const c = CAMPAIGNS.find(x => x.id === window.HP.selectedCampaignId)
    || CAMPAIGNS.find(x => x.status === 'Activa') || CAMPAIGNS[0];
  if (!c) {
    return <div className="page"><div className="empty">No hay campañas. Crea una en la sección Campañas.</div></div>;
  }
  const dias = (c.start && c.end) ? Math.round((new Date(c.end) - new Date(c.start)) / 86400000) : null;
  const areaLotes = SECTORS.reduce((a, s) => a + (s.area || 0), 0);
  const esActiva = c.status === 'Activa';

  function editar() { window.HP.editingCampaignId = c.id; navigate('campaign_new'); }
  async function activar() {
    try { await window.HP.api.activarCampana(c.id); await window.HP.api.refrescar(); toast('Campaña activada ✓'); navigate('campaign_det'); }
    catch (e) { toast('Error al activar: ' + e.message); }
  }
  async function cerrar() {
    try { await window.HP.api.cerrarCampana(c.id); await window.HP.api.refrescar(); toast('Campaña cerrada ✓'); navigate('campaign_det'); }
    catch (e) { toast('Error al cerrar: ' + e.message); }
  }
  async function eliminar() {
    if (!confirm('¿Eliminar la campaña "' + c.name + '"? Se borrarán sus registros, predicciones y planes.')) return;
    try { await window.HP.api.eliminarCampana(c.id); await window.HP.api.refrescar(); toast('Campaña eliminada ✓'); navigate('campaigns'); }
    catch (e) { toast('Error al eliminar: ' + e.message); }
  }

  const sub = esActiva
    ? 'Campaña actualmente activa. Solo una campaña puede estar en este estado simultáneamente.'
    : c.status === 'Cerrada' ? 'Campaña cerrada — histórico consultable. Actívala para volver a trabajar sobre ella.'
      : 'Campaña en borrador. Actívala para empezar a cargar lotes y variables.';
  return (
    <div className="page">
      <PageHeader
        eyebrow="M2 · Detalle de campaña"
        title={c.name}
        sub={sub}
        actions={
          <>
            <button className="btn ghost" onClick={editar}><Icon name="edit" size={14}/> Editar</button>
            {!esActiva && <button className="btn primary" onClick={activar}><Icon name="check" size={14}/> Activar</button>}
            {esActiva && <button className="btn" onClick={cerrar}><Icon name="x" size={14}/> Cerrar campaña</button>}
            <button className="btn ghost" onClick={eliminar}><Icon name="trash" size={14}/> Eliminar</button>
            {esActiva && <Badge tone="olive" dot>Campaña activa</Badge>}
            {c.status === 'Cerrada' && <Badge tone="neut">Cerrada</Badge>}
            {c.status === 'Borrador' && <Badge tone="warn">Borrador</Badge>}
          </>
        }
      />

      <div className="row-3" style={{ marginBottom: 16 }}>
        <InfoCard label="Periodo" big={`${c.start || '—'} → ${c.end || '—'}`} small={dias ? `${dias} días · ${Math.round(dias / 7)} semanas` : '—'} />
        <InfoCard label="Lotes asociados" big={`${SECTORS.length}`} small={`${fmtNum(areaLotes, 1)} Ha total`} />
        <InfoCard label="Producción plan vs real" big={`${fmtNum(c.harvestedTons || 0)} / ${fmtNum(c.plannedTons || 0)} Tn`} small={`${c.plannedTons ? Math.round((c.harvestedTons || 0) / c.plannedTons * 100) : 0}% de avance`} />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3>Lotes en la campaña</h3>
          <div className="right"><button className="btn ghost sm" onClick={() => navigate('sectors')}>Ir a lotes <Icon name="chev" size={12} /></button></div>
        </div>
        <table className="tbl">
          <thead><tr>
            <th>Lote</th><th className="num">Área</th><th>Variedad</th>
            <th className="num">Rend. esperado</th><th className="num">Rend. anterior</th><th>Estado</th>
          </tr></thead>
          <tbody>
            {SECTORS.slice(0, 6).map(s => (
              <tr key={s.id}>
                <td><span className="mono" style={{ color: 'var(--ink-3)' }}>{s.id}</span> · <span className="strong">{s.name}</span></td>
                <td className="num">{fmtNum(s.area, 1)} Ha</td>
                <td>{s.variety}</td>
                <td className="num">{fmtNum(s.expectedYieldHa, 1)} Tn/Ha</td>
                <td className="num">{s.lastYieldHa ? fmtNum(s.lastYieldHa, 1) + ' Tn/Ha' : '—'}</td>
                <td><Sem level={s.status} label={s.status === 'ok' ? 'Óptimo' : s.status === 'warn' ? 'Atención' : 'Crítico'} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InfoCard({ label, big, small, icon, tone }) {
  const accent = tone === 'crit' ? 'var(--crit,#9B2C1F)' : tone === 'warn' ? 'var(--warn,#B5530B)' : 'var(--primary,#4D7C0F)';
  const tint = tone === 'crit' ? 'var(--crit-tint,#F1D4CE)' : tone === 'warn' ? 'var(--warn-tint,#F5E2C6)' : 'var(--primary-tint,#E8EFD3)';
  return (
    <div className="card card-pad">
      <div className="hstack" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <div className="page-eyebrow">{label}</div>
        {icon && <span style={{ color: accent, background: tint, borderRadius: 8, width: 30, height: 30, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon name={icon} size={16} /></span>}
      </div>
      <div className="serif" style={{ fontSize: 22, lineHeight: 1.15, color: 'var(--ink)', letterSpacing: '-0.01em' }}>{big}</div>
      <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>{small}</div>
    </div>
  );
}

/* ===================== M3 — Sectors ===================== */
function Sectors() {
  const { navigate, toast } = useRouter();
  const [q, setQ] = useState('');
  const ro = esCampanaCerrada();
  async function eliminarLote(e, s) {
    e.stopPropagation();
    if (ro) return;
    if (!confirm('¿Eliminar el lote "' + s.name + '"? Se borrarán sus registros y predicciones.')) return;
    try { await window.HP.api.eliminarLote(s.id); await window.HP.api.refrescar(); toast('Lote eliminado ✓'); navigate('sectors'); }
    catch (err) { toast('Error al eliminar: ' + err.message); }
  }
  // s.id es numérico (id del lote): convertir a String antes de filtrar (evita crash).
  const filt = SECTORS.filter(s => String(s.name || '').toLowerCase().includes(q.toLowerCase()) || String(s.id).includes(q));
  const totalArea = SECTORS.reduce((a, s) => a + (s.area || 0), 0);
  // Resumen visual (mismos datos de la tabla, agregados).
  const predichos = SECTORS.filter(s => s.lastYield != null);
  const rendProm = predichos.length ? predichos.reduce((a, s) => a + (s.lastYield || 0), 0) / predichos.length : 0;
  const sync = SECTORS.filter(s => s.syncOk).length;
  return (
    <div className="page">
      <PageHeader
        eyebrow="M3 · Gestión de lotes"
        title="Lotes de la campaña activa"
        sub={`${SECTORS.length} lotes · ${fmtNum(totalArea, 1)} Ha · variedad Hass. Las variables manuales se capturan en campo; las climáticas vienen por API.`}
        actions={
          <>
            <div className="hstack" style={{ background:'var(--surface)', border:'1px solid var(--border-2)', borderRadius:8, padding:'0 10px', height:34 }}>
              <Icon name="search" size={14} />
              <input style={{ border:0, outline:0, background:'transparent', height:32, fontSize:13, width:200 }} placeholder="Buscar lote…" value={q} onChange={e => setQ(e.target.value)} />
            </div>
            <button className="btn primary" disabled={ro} onClick={() => !ro && navigate('sector_new')}><Icon name="plus" size={14} /> Nuevo lote</button>
          </>
        }
      />
      {SECTORS.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 16 }}>
          <InfoCard icon="sectors" label="Lotes en la campaña" big={String(SECTORS.length)} small={`${fmtNum(totalArea, 1)} Ha en total`} />
          <InfoCard icon="harvest" label="Rend. promedio predicho" big={rendProm ? `${fmtNum(rendProm, 1)} Tn/Ha` : '—'} small="La Joya: 14–24 Tn/Ha" />
          <InfoCard icon="brain" label="Lotes predichos" big={`${predichos.length} / ${SECTORS.length}`} small="con rendimiento estimado" />
          <InfoCard icon="cloud" label="Clima sincronizado" big={`${sync} / ${SECTORS.length}`} small="lotes con datos de API" tone={sync < SECTORS.length ? 'warn' : undefined} />
        </div>
      )}
      <div className="card">
        <table className="tbl">
          <thead><tr>
            <th>Lote</th><th>Nombre</th><th className="num">Área</th>
            <th className="num">Edad campo</th><th className="num">Edad prod.</th>
            <th className="num">Tn/Ha pred.</th><th className="num">Tn/Ha prom.</th>
            <th>API clima</th><th>Estado</th><th className="num">Acciones</th>
          </tr></thead>
          <tbody>
            {filt.map(s => (
              <tr key={s.id} onClick={() => { window.HP.selectedLoteId = s.id; navigate('sector_det'); }} style={{ cursor: 'pointer' }}>
                <td className="mono" style={{ color: 'var(--ink-3)' }}>L{s.id}</td>
                <td className="strong">{s.name}</td>
                <td className="num">{fmtNum(s.area, 1)} Ha</td>
                <td className="num">{s.edadCampo} a</td>
                <td className="num">{s.edadProd} a</td>
                <td className="num strong">{s.lastYield ? fmtNum(s.lastYield, 1) : '—'}</td>
                <td className="num">{fmtNum(s.avgYield, 1)}</td>
                <td>{s.syncOk ? <Badge tone="olive" dot>Sincronizado</Badge> : <Badge tone="crit" dot>Sin datos</Badge>}</td>
                <td><Sem level={s.status} label={s.status === 'ok' ? 'Óptimo' : s.status === 'warn' ? 'Atención' : 'Crítico'} /></td>
                <td className="num" onClick={e => e.stopPropagation()}>
                  <button className="btn sm ghost" disabled={ro} onClick={e => eliminarLote(e, s)} title={ro ? 'Campaña cerrada' : 'Eliminar lote'}><Icon name="trash" size={12}/></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SectorNew() {
  const { navigate, toast } = useRouter();
  // Modo edición si hay un lote marcado para editar (reusa esta misma vista).
  const editId = window.HP.editingLoteId;
  const editS = editId ? SECTORS.find(x => x.id === editId) : null;
  const [nombre, setNombre] = useState(editS ? editS.name : '');
  const [area, setArea] = useState(editS && editS.area != null ? String(editS.area) : '');
  const [variedad, setVariedad] = useState(editS ? (editS.variety || 'Hass') : 'Hass');
  const [ano, setAno] = useState(editS && editS.anoPlantacion ? editS.anoPlantacion : 2022);
  const [densidad, setDensidad] = useState(editS && editS.densidadPlantasHa != null ? String(editS.densidadPlantasHa) : '');
  const [geom, setGeom] = useState(null);   // null en edición => conserva la geometría actual
  const [saving, setSaving] = useState(false);

  function limpiarEdicion() { window.HP.editingLoteId = null; }
  function cancelar() { limpiarEdicion(); navigate(editS ? 'sector_det' : 'sectors'); }

  async function guardar() {
    if (esCampanaCerrada()) { toast('Campaña cerrada — solo lectura'); return; }
    if (!nombre.trim()) { toast('Falta el nombre del lote'); return; }
    const esPoligono = geom && geom.type === 'Polygon';
    // Al crear, exigir geometría o área. Al editar sin redibujar, se conserva el área actual.
    if (!editS && !esPoligono && !(Number(area) > 0)) { toast('Dibuja el contorno, o marca el centroide e ingresa el área'); return; }
    setSaving(true);
    try {
      const body = { nombre: nombre.trim(), variedad, ano_plantacion: Number(ano) || 0 };
      // Densidad opcional (plantas/Ha): solo se envía si el productor la ingresó.
      if (String(densidad).trim() !== '') body.densidad_plantas_ha = Number(densidad) || null;
      if (geom) body.geometria = geom;          // polígono (área auto) o punto (centroide)
      // área a mano: punto, o sin geometría (al crear); al editar solo si se ingresó un valor
      if (!esPoligono && Number(area) > 0) body.area_ha = Number(area);
      if (editS) {
        await window.HP.api.editarLote(editS.id, body);
        await window.HP.api.refrescar();
        limpiarEdicion();
        toast('Lote actualizado ✓');
        navigate('sector_det');
      } else {
        // Lote bajo la finca seleccionada del productor; solo si no hay ninguna, se crea una genérica.
        const fincaId = window.HP.selectedFincaId || await window.HP.api.asegurarFinca();
        await window.HP.api.crearLote(fincaId, body);
        await window.HP.api.refrescar();
        toast('Lote guardado ✓');
        navigate('sectors');
      }
    } catch (e) {
      toast('Error al guardar: ' + e.message);
    } finally {
      setSaving(false);
    }
  }

  const [buscar, setBuscar] = useState('');
  const [buscando, setBuscando] = useState(false);
  const [flyTo, setFlyTo] = useState(null);
  async function irABuscar() {
    if (!buscar.trim()) return;
    setBuscando(true);
    try {
      const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(buscar));
      const d = await r.json();
      if (d && d[0]) setFlyTo([+d[0].lat, +d[0].lon, Date.now()]);
      else toast('No se encontró ese lugar.');
    } catch (e) { toast('Sin conexión para buscar.'); }
    finally { setBuscando(false); }
  }

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <PageHeader eyebrow="M3 · Nuevo lote" title="Registrar lote"
        sub="Escribe tu zona en el buscador del mapa para ubicarte; luego dibuja el contorno (área automática) o marca el centroide (📍). O ingresa el área a mano." />
      <div className="stack">
        {/* Datos del lote */}
        <div className="card card-pad">
          <div className="row-2">
            <div className="field"><label>Nombre</label>
              <input value={nombre} onChange={e => setNombre(e.target.value)} placeholder="Ej. Lote 5 — Norte" /></div>
            <div className="field"><label>Variedad</label>
              <select value={variedad} onChange={e => setVariedad(e.target.value)}>
                <option>Hass</option><option>Lamb Hass</option><option>Fuerte</option>
              </select>
            </div>
          </div>
          <div className="row-2">
            <div className="field"><label>Año plantación</label>
              <input type="number" value={ano} onChange={e => setAno(e.target.value)} /></div>
            <div className="field"><label>Densidad (plantas/Ha)</label>
              <input type="number" value={densidad} onChange={e => setDensidad(e.target.value)} placeholder="opcional · por defecto 350" />
              <div className="hint">Marco de plantación del lote. Si lo dejas vacío se usa 350 plantas/Ha para estimar el nº de árboles.</div>
            </div>
          </div>
          <div className="row-2">
            <div className="field"><label>Área (Ha)</label>
              <input type="number" value={area} onChange={e => setArea(e.target.value)} placeholder="0.0"
                disabled={geom && geom.type === 'Polygon'} />
              <div className="hint">{
                !geom ? 'Dibuja el contorno (área automática), marca el centroide (📍), o ingresa el área a mano.'
                  : geom.type === 'Polygon' ? 'Polígono dibujado ✓ — área y centroide se calculan al guardar.'
                    : 'Centroide marcado ✓ — ingresa el área manualmente.'
              }</div>
            </div>
          </div>
        </div>

        {/* Mapa a todo el ancho, con buscador claro */}
        <div className="card">
          <div className="card-head"><h3>Ubica y dibuja el lote</h3>
            <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>satélite Esri</div>
          </div>
          <div className="card-pad">
            <div className="hstack" style={{ marginBottom: 10 }}>
              <div className="hstack grow" style={{ background: 'var(--surface)', border: '1px solid var(--border-2)', borderRadius: 8, padding: '0 10px', height: 38, gap: 8 }}>
                <Icon name="search" size={16} />
                <input style={{ border: 0, outline: 0, background: 'transparent', height: 36, fontSize: 14, width: '100%' }}
                  placeholder="Buscar tu zona (ej. La Joya, Arequipa) y presiona Enter…"
                  value={buscar} onChange={e => setBuscar(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); irABuscar(); } }} />
              </div>
              <button className="btn primary" onClick={irABuscar} disabled={buscando}>
                <Icon name="search" size={14} /> {buscando ? 'Buscando…' : 'Ir'}</button>
            </div>
            <LeafletMap height={440} draw onPolygon={setGeom} flyTo={flyTo} />
          </div>
        </div>

        <div className="hstack" style={{ justifyContent: 'flex-end' }}>
          <button className="btn ghost" onClick={() => navigate('sectors')}>Cancelar</button>
          <button className="btn primary" onClick={guardar} disabled={saving}>
            {saving ? 'Guardando…' : 'Crear lote'}</button>
        </div>
      </div>
    </div>
  );
}

function SectorDetail() {
  const { navigate, toast } = useRouter();
  const s = SECTORS.find(x => x.id === window.HP.selectedLoteId) || SECTORS[0];
  const [tab, setTab] = useState('overview');
  if (!s) {
    return <div className="page"><div className="empty">No hay lotes. Crea uno en la sección Lotes.</div></div>;
  }
  // Última campaña real del historial (la más reciente con valor); null si aún no hay.
  const ult = s.history.length ? s.history[s.history.length - 1] : null;
  const nCamp = s.history.length;
  const ro = esCampanaCerrada();
  function editar() { if (ro) return; window.HP.editingLoteId = s.id; navigate('sector_new'); }
  async function eliminar() {
    if (ro) return;
    if (!confirm('¿Eliminar el lote "' + s.name + '"? Se borrarán sus registros y predicciones.')) return;
    try { await window.HP.api.eliminarLote(s.id); await window.HP.api.refrescar(); toast('Lote eliminado ✓'); navigate('sectors'); }
    catch (e) { toast('Error al eliminar: ' + e.message); }
  }
  return (
    <div className="page">
      <PageHeader
        eyebrow={`M3 · ${s.id}`}
        title={s.name}
        sub={`${s.area} Ha · Hass · edad campo ${s.edadCampo} años · edad productiva ${s.edadProd} años`}
        actions={
          <>
            <button className="btn ghost" disabled={ro} onClick={editar}><Icon name="edit" size={14}/> Editar</button>
            <button className="btn ghost" disabled={ro} onClick={eliminar}><Icon name="trash" size={14}/> Eliminar</button>
            <button className="btn primary" disabled={ro} onClick={() => !ro && navigate('sector_vars')}><Icon name="plus" size={14}/> Ingresar variables</button>
          </>
        }
      />
      <Tabs
        value={tab} onChange={setTab}
        items={[
          { id:'overview', label:'Resumen' },
          { id:'history',  label:`Historial productivo (${s.history.length} ${s.history.length === 1 ? 'campaña' : 'campañas'})` },
          { id:'vars',     label:'Variables actuales' },
        ]}
      />

      {tab === 'overview' && (
        <div className="row-2">
          <div className="card">
            <div className="card-head"><h3>Indicadores</h3></div>
            <table className="tbl">
              <tbody>
                <tr><td>Tn/Ha promedio ({nCamp} {nCamp === 1 ? 'campaña' : 'campañas'})</td><td className="num strong">{nCamp ? fmtNum(s.avgYield, 2) + ' Tn/Ha' : '—'}</td></tr>
                <tr><td>Tn/Ha máxima histórica</td><td className="num">{nCamp ? fmtNum(s.maxYield, 2) + ' Tn/Ha' : '—'}</td></tr>
                <tr><td>Tn/Ha mínima histórica</td><td className="num">{nCamp ? fmtNum(s.minYield, 2) + ' Tn/Ha' : '—'}</td></tr>
                <tr><td>Producción esperada (avg × área)</td><td className="num strong">{nCamp ? fmtNum(s.avgYield * s.area, 1) + ' Tn' : '—'}</td></tr>
                <tr><td>Última campaña ({ult ? ult.c : '—'})</td><td className="num">{ult ? fmtNum(ult.y, 2) + ' Tn/Ha' : '—'}</td></tr>
                <tr><td>Estado actual</td><td><Sem level={s.status} label={s.status === 'ok' ? 'Óptimo' : s.status === 'warn' ? 'Atención' : 'Crítico'} /></td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-head"><h3>Ubicación</h3>
              <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>
                {s.lat != null ? `${s.lat.toFixed(4)}, ${s.lon.toFixed(4)}` : 'sin geometría'}
              </div>
            </div>
            <div className="card-pad">
              <LeafletMap height={220} lotes={[s]} center={s.lat != null ? [s.lat, s.lon] : undefined} />
              <div className="hint" style={{ marginTop: 8 }}>El centroide del polígono resuelve lat/lon para consultar el clima por API.</div>
            </div>
          </div>
        </div>
      )}

      {tab === 'history' && (
        <div className="card">
          <table className="tbl">
            <thead><tr><th>Campaña</th><th className="num">Tn/Ha</th><th className="num">Tn totales</th><th className="num">Δ vs anterior</th><th>Tendencia</th></tr></thead>
            <tbody>
              {s.history.slice().reverse().map((h, i, arr) => {
                const prev = arr[i+1];
                const delta = prev && h.y && prev.y ? ((h.y - prev.y) / prev.y) * 100 : null;
                const bar = h.y ? Math.min(100, (h.y / s.maxYield) * 100) : 0;
                return (
                  <tr key={h.c}>
                    <td className={i === 0 ? 'strong' : ''}>{h.c}{i === 0 ? ' (última)' : ''}</td>
                    <td className="num strong">{h.y ? fmtNum(h.y, 2) : '—'}</td>
                    <td className="num">{h.y ? fmtNum(h.y * s.area, 1) : '—'}</td>
                    <td className="num">{delta == null ? '—' : <span className={'delta mono ' + (delta >= 0 ? 'up' : 'down')}>{delta >= 0 ? '▲' : '▼'} {fmtNum(Math.abs(delta), 1)}%</span>}</td>
                    <td><div className="prog" style={{ width: 160 }}><span style={{ width: bar + '%' }}></span></div></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'vars' && <SectorVars embedded />}
    </div>
  );
}

function SectorVars({ embedded }) {
  const { navigate, toast } = useRouter();
  const s = window.HP.FINCAS.find(x => x.id === window.HP.selectedLoteId) || window.HP.FINCAS[0];
  // Fuente resiliente: los ids reales (nasa_power, open_meteo…) no coinciden con los
  // del prototipo (nasa-power…); si no se encuentra, usar la primera o un placeholder.
  const sourceId = window.HP.fincaSource(0);
  const source = window.HP.SOURCES.find(x => x.id === sourceId)
    || window.HP.SOURCES[0] || { name: '—', status: 'ok' };
  const ro = esCampanaCerrada();
  const [syncing, setSyncing] = useState(false);
  const [vals, setVals] = useState(() => {
    const v = {};
    const last = (s && s.last) || {};
    window.HP.VARS.forEach(x => { v[x.key] = last[x.key] != null ? last[x.key] : ''; });
    return v;
  });

  const [saving, setSaving] = useState(false);
  if (!s) {
    return <div className="page"><div className="empty">No hay lotes todavía. Crea un lote en la sección Lotes para ingresar sus variables.</div></div>;
  }
  const setVal = (k, v) => setVals({ ...vals, [k]: v });

  const manuales = window.HP.VARS.filter(v => v.source === 'manual');

  async function guardar() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (!s || s.id == null) { toast('No hay lote seleccionado'); return; }
    setSaving(true);
    try {
      // Se guardan las MANUALES (las que ingresa el productor); las climáticas vienen por API.
      for (const v of manuales) {
        const val = vals[v.key];
        if (val !== '' && val != null) {
          await window.HP.api.guardarVariable(s.id, v.key, Number(val));
        }
      }
      await window.HP.api.refrescar();
      toast('Variables guardadas ✓');
      navigate('intelligence');
    } catch (e) {
      toast('Error al guardar: ' + e.message);
    } finally {
      setSaving(false);
    }
  }

  async function resync() {
    if (ro) { toast('Campaña cerrada — solo lectura'); return; }
    if (!s || s.id == null) { toast('No hay lote seleccionado'); return; }
    const campana = window.HP.activeCampaign;
    if (!campana) { toast('Activa una campaña para sincronizar el clima'); return; }
    if (s.lat == null || s.lon == null) { toast('El lote no tiene centroide (lat/lon) para consultar el clima'); return; }
    setSyncing(true);
    try {
      const r = await window.HP.api.sincronizarClima(s.id, campana.id);
      await window.HP.api.refrescar();
      const msg = (r && r.sync && r.sync.mensaje) ? r.sync.mensaje : ('Variables climáticas sincronizadas · ' + source.name);
      toast(msg);
    } catch (e) {
      toast('Error al sincronizar: ' + e.message);
    } finally {
      setSyncing(false);
    }
  }

  const apiVars  = window.HP.VARS.filter(v => v.source === 'api');
  const groupsApi = ['Térmicas — Frío', 'Térmicas — Calor', 'Clima'];
  const groupsMan = ['Productividad', 'Manejo'];

  const Wrap = embedded ? React.Fragment : (props) => <div className="page">{props.children}</div>;
  return (
    <Wrap>
      {!embedded && (
        <PageHeader eyebrow={`M3 · Variables del modelo · ${s.id}`} title={`Ingreso de variables — ${s.name}`}
          sub="15 features del modelo: 3 manuales (manejo: riego y edades) y 12 climáticas sincronizadas vía API meteorológica."
          actions={
            <>
              <button className="btn ghost" onClick={() => navigate('sector_det')}>Cancelar</button>
              <button className="btn primary" onClick={guardar} disabled={saving || ro}><Icon name="check" size={14}/> {saving ? 'Guardando…' : 'Guardar y enviar a IA'}</button>
            </>
          }
        />
      )}

      {/* Two-column layout: Manual / API */}
      <div className="row-2" style={{ alignItems: 'flex-start' }}>
        {/* === Manual === */}
        <div className="card">
          <div className="card-head">
            <h3><span className="hstack" style={{ gap: 10 }}><Icon name="edit" size={15} /> Variables manuales</span></h3>
            <div className="right">
              <Badge tone="olive">{manuales.length} / {manuales.length} capturadas</Badge>
            </div>
          </div>
          <div className="card-pad">
            {groupsMan.map(g => (
              <div key={g} style={{ marginBottom: 14 }}>
                <div className="page-eyebrow" style={{ marginBottom: 8 }}>{g}</div>
                {manuales.filter(v => v.group === g).map(v => (
                  <div className="field" key={v.key} style={{ marginBottom: 10 }}>
                    <label>{v.label} <span style={{ color: 'var(--muted)', letterSpacing: 0, textTransform: 'none' }}>({v.unit})</span></label>
                    <input value={vals[v.key]} onChange={e => setVal(v.key, e.target.value)} />
                    <div className="hint">{v.desc}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* === API === */}
        <div className="card">
          <div className="card-head">
            <h3><span className="hstack" style={{ gap: 10 }}><Icon name="cloud" size={15} /> Variables climáticas · API</span></h3>
            <div className="right">
              <Badge tone={source.status === 'ok' ? 'olive' : 'warn'} dot>{source.status === 'ok' ? 'Sincronizado' : 'Reintentando'}</Badge>
              <button className="btn sm ghost" onClick={resync} disabled={syncing || ro}>
                <Icon name="refresh" size={12} /> {syncing ? 'Sincronizando…' : 'Resincronizar'}
              </button>
            </div>
          </div>
          <div style={{ padding: '10px 18px 4px', borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>
            <div className="hstack" style={{ justifyContent:'space-between', fontSize: 12, color: 'var(--ink-3)' }}>
              <span><span className="mono" style={{ color: 'var(--muted)' }}>FUENTE:</span> <b>{source.name}</b></span>
              <span><span className="mono" style={{ color: 'var(--muted)' }}>VENTANA:</span> 01-sep-25 → 30-abr-26</span>
              <span><span className="mono" style={{ color: 'var(--muted)' }}>LAT/LON:</span> {s.lat != null ? `${s.lat.toFixed(4)} / ${s.lon.toFixed(4)}` : '—'}</span>
            </div>
          </div>
          <div className="card-pad">
            {groupsApi.map(g => (
              <div key={g} style={{ marginBottom: 14 }}>
                <div className="page-eyebrow" style={{ marginBottom: 8 }}>{g}</div>
                {apiVars.filter(v => v.group === g).map(v => (
                  <ApiVarRow key={v.key} v={v} val={vals[v.key]} setVal={setVal} fincaId={s.id} syncing={syncing} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {embedded && (
        <div className="hstack" style={{ justifyContent: 'flex-end', marginTop: 16 }}>
          <button className="btn primary" onClick={guardar} disabled={saving || ro}><Icon name="check" size={14}/> {saving ? 'Guardando…' : 'Guardar y enviar a IA'}</button>
        </div>
      )}
    </Wrap>
  );
}

function ApiVarRow({ v, val, setVal, fincaId, syncing }) {
  const [override, setOverride] = useState(false);
  const ro = esCampanaCerrada();
  const synced = window.HP.syncTime(fincaId, v.key);
  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 110px 90px', gap: 10, alignItems:'center', padding: '6px 0', borderBottom: '1px dashed var(--border)' }}>
      <div>
        <div style={{ fontSize: 13, color: 'var(--ink)' }}>{v.label}</div>
        <div className="hstack mono" style={{ gap: 8, fontSize: 11, color: 'var(--muted)' }}>
          <span style={{ color: override ? 'var(--terra)' : (syncing ? 'var(--warn)' : 'var(--ok)') }}>
            {override ? '✎ override' : syncing ? '◜ sync…' : '✓ ' + synced}
          </span>
          <span style={{ color: 'var(--muted)' }}>· {v.unit}</span>
        </div>
      </div>
      <input className="mono" style={{ height: 30, padding: '0 8px', border: '1px solid var(--border-2)', borderRadius: 6, background: override ? 'var(--terra-tint)' : 'var(--surface-2)', textAlign: 'right', fontSize: 13, color: 'var(--ink)' }}
        value={val} onChange={e => setVal(v.key, e.target.value)} readOnly={!override || ro} />
      <button className="btn sm ghost" disabled={ro} onClick={() => !ro && setOverride(!override)} style={{ fontSize: 11 }}>
        {override ? 'Usar API' : 'Override'}
      </button>
    </div>
  );
}

Object.assign(window, {
  GlobalDashboard, ViewCampaignSummary, Campaigns, CampaignNew, CampaignDetail,
  Sectors, SectorNew, SectorDetail, SectorVars,
});
