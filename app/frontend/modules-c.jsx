// HassPlan — modules C: M10 Fuentes de datos (clima API + GeoJSON)
const HP_C = window.HP;

function DataSources() {
  const { toast } = useRouter();
  const [tab, setTab] = useState('apis');
  const [syncing, setSyncing] = useState({});
  const [logRows, setLogRows] = useState(() => buildSyncLog());

  function resync(srcId) {
    setSyncing({ ...syncing, [srcId]: true });
    setTimeout(() => {
      setSyncing({ ...syncing, [srcId]: false });
      const src = HP_C.SOURCES.find(s => s.id === srcId);
      toast(`${src.name} resincronizada`);
      setLogRows(prev => [
        { ts: nowTs(), src: src.name, op: 'Resync manual', records: 35, status: 'ok', detail: 'Todas las fincas actualizadas' },
        ...prev,
      ]);
    }, 1100);
  }

  // Mapeo finca → fuente
  const mappings = HP_C.FINCAS.map((f, i) => ({
    finca: f,
    source: HP_C.SOURCES.find(s => s.id === HP_C.fincaSource(i)),
    lat: -13.4521 + (i * 0.0083),
    lon: -76.1273 + (i * 0.0044),
    elev: 240 + ((i * 27) % 320),
    geo: i < 28,    // 28 de 35 con GeoJSON cargado
    lastSync: f.syncOk ? HP_C.syncTime(f.id, 'tProm') : 'sin datos',
  }));

  return (
    <div className="page">
      <PageHeader
        eyebrow="M10 · Fuentes de datos"
        title="Integración con APIs y geometrías"
        sub="Configuración de las fuentes que alimentan las 13 variables climáticas del modelo y la cartografía de fincas. Cada finca puede asignarse a una fuente preferida, con fallback automático."
        actions={
          <>
            <button className="btn ghost"><Icon name="link" size={14}/> Probar conexión</button>
            <button className="btn primary" onClick={() => HP_C.SOURCES.forEach(s => s.id !== 'manual' && resync(s.id))}>
              <Icon name="refresh" size={14}/> Resincronizar todo
            </button>
          </>
        }
      />

      <div className="row-3" style={{ marginBottom: 16 }}>
        <KpiC label="Fuentes activas" big="4 / 5" small="3 APIs externas + estaciones locales" tone="ok" />
        <KpiC label="Fincas con GeoJSON cargado" big={`${mappings.filter(m => m.geo).length} / 35`} small="7 pendientes de digitalización" tone="warn" />
        <KpiC label="Última sincronización clima" big="hoy 06:00" small="Cron diario · próxima 09 jun 18:00" tone="ok" />
      </div>

      <Tabs value={tab} onChange={setTab} items={[
        { id: 'apis',      label: 'APIs meteorológicas' },
        { id: 'mapping',   label: 'Mapeo finca → fuente' },
        { id: 'geojson',   label: 'GeoJSON y cartografía' },
        { id: 'log',       label: 'Log de sincronización' },
      ]}/>

      {tab === 'apis' && (
        <div style={{ display: 'grid', gap: 14 }}>
          {HP_C.SOURCES.map(s => (
            <SourceCard key={s.id} s={s} syncing={syncing[s.id]} onSync={() => resync(s.id)} />
          ))}
        </div>
      )}

      {tab === 'mapping' && (
        <div className="card">
          <div className="card-head">
            <h3>Mapeo de fincas a fuentes</h3>
            <div className="right mono" style={{ fontSize: 11, color: 'var(--muted)' }}>35 FINCAS · LAT/LON DERIVADAS DEL CENTROIDE GEOJSON</div>
          </div>
          <table className="tbl">
            <thead><tr>
              <th>Finca</th><th>Nombre</th><th>Lat / Lon</th><th className="num">Altitud</th>
              <th>Fuente clima</th><th>Última sincronización</th><th>Estado</th><th></th>
            </tr></thead>
            <tbody>
              {mappings.map(m => (
                <tr key={m.finca.id}>
                  <td className="mono" style={{ color: 'var(--ink-3)' }}>{m.finca.id}</td>
                  <td className="strong">{m.finca.name}</td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{m.lat.toFixed(4)}, {m.lon.toFixed(4)}</td>
                  <td className="num">{m.elev} msnm</td>
                  <td>
                    <select defaultValue={m.source.id} style={{ height: 28, padding: '0 8px', border: '1px solid var(--border-2)', borderRadius: 6, background: 'var(--surface)', fontFamily: 'inherit', fontSize: 12 }}>
                      {HP_C.SOURCES.filter(s => s.id !== 'manual').map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{m.lastSync}</td>
                  <td>
                    {m.finca.syncOk
                      ? <Badge tone="olive" dot>OK</Badge>
                      : <Badge tone="crit" dot>Sin datos</Badge>}
                  </td>
                  <td><button className="btn sm ghost"><Icon name="refresh" size={12}/></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'geojson' && (
        <div className="row-2" style={{ alignItems: 'flex-start' }}>
          <div className="card">
            <div className="card-head"><h3>Cartografía de fincas</h3>
              <div className="right hstack" style={{ gap: 8 }}>
                <Badge tone="olive">28 cargadas</Badge>
                <Badge tone="warn">7 pendientes</Badge>
              </div>
            </div>
            <div className="card-pad">
              <div className="map-box" style={{ height: 360 }}>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
                  {Array.from({ length: 28 }).map((_, i) => {
                    const cx = 8 + (i % 7) * 12 + ((i * 3) % 5);
                    const cy = 10 + Math.floor(i / 7) * 18 + ((i * 7) % 6);
                    const w = 7 + ((i * 3) % 4);
                    const h = 6 + ((i * 5) % 3);
                    const finca = HP_C.FINCAS[i];
                    const color = finca.status === 'crit' ? 'rgba(155,44,31,0.55)' : finca.status === 'warn' ? 'rgba(201,122,33,0.55)' : 'rgba(77,124,15,0.55)';
                    const stroke = finca.status === 'crit' ? '#7A1F12' : finca.status === 'warn' ? '#8C520F' : '#2C4E03';
                    return (
                      <g key={i}>
                        <polygon points={`${cx},${cy+1} ${cx+w-1},${cy} ${cx+w},${cy+h-1} ${cx+1},${cy+h}`} fill={color} stroke={stroke} strokeWidth="0.3" />
                        <text x={cx + w/2} y={cy + h/2 + 0.5} textAnchor="middle" fontSize="1.8" fill="#FBF7E9" fontFamily="Geist Mono" fontWeight="500">{finca.id}</text>
                      </g>
                    );
                  })}
                </svg>
                <div className="map-legend">
                  <span className="hstack" style={{ gap: 6 }}><Icon name="sat" size={12}/> Capa satelital · ESRI</span>
                  <span className="mono" style={{ color: 'var(--muted)' }}>·</span>
                  <span className="mono">EPSG:4326</span>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h3>Estado de la cartografía</h3></div>
            <div className="card-pad">
              <div className="page-eyebrow" style={{ marginBottom: 8 }}>Atributos derivados del polígono</div>
              <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
                <FieldRow label="Área (Ha)" desc="turf.area(geometry) / 10 000 · auto" />
                <FieldRow label="Centroide" desc="Para resolver lat/lon de la API clima" />
                <FieldRow label="Altitud (msnm)" desc="Cruce con DEM SRTM 30 m" />
                <FieldRow label="Pendiente media" desc="DEM derivative · auto" />
                <FieldRow label="Orientación predominante" desc="Aspect del DEM · auto" />
              </div>

              <div className="divider-h"></div>
              <div className="page-eyebrow" style={{ marginBottom: 8 }}>Cargar / actualizar</div>
              <div style={{ border: '1.5px dashed var(--border-2)', borderRadius: 10, padding: 18, textAlign: 'center', background: 'var(--surface-2)' }}>
                <Icon name="map" size={22} />
                <div style={{ fontSize: 13, marginTop: 8, color: 'var(--ink)' }}>Arrastra un .geojson o .kml aquí</div>
                <div className="hint" style={{ marginTop: 4 }}>Tamaño máx. 25 MB · uno o varios polígonos · campo Finca para mapear al ID</div>
                <button className="btn sm" style={{ marginTop: 10 }}>Examinar archivos</button>
              </div>

              <div className="divider-h"></div>
              <div className="page-eyebrow" style={{ marginBottom: 8 }}>Fincas sin polígono</div>
              <div className="hstack" style={{ flexWrap: 'wrap', gap: 6 }}>
                {HP_C.FINCAS.slice(28).map(f => (
                  <Badge key={f.id} tone="warn">{f.id} · {f.name}</Badge>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'log' && (
        <div className="card">
          <div className="card-head"><h3>Historial de sincronización</h3>
            <div className="right"><button className="btn ghost sm"><Icon name="filter" size={12}/> Filtrar</button></div>
          </div>
          <table className="tbl">
            <thead><tr>
              <th>Timestamp</th><th>Fuente</th><th>Operación</th>
              <th className="num">Registros</th><th>Estado</th><th>Detalle</th>
            </tr></thead>
            <tbody>
              {logRows.map((l, i) => (
                <tr key={i}>
                  <td className="mono" style={{ fontSize: 12 }}>{l.ts}</td>
                  <td>{l.src}</td>
                  <td>{l.op}</td>
                  <td className="num">{l.records}</td>
                  <td>
                    {l.status === 'ok'   && <Badge tone="olive" dot>OK</Badge>}
                    {l.status === 'warn' && <Badge tone="warn" dot>Parcial</Badge>}
                    {l.status === 'err'  && <Badge tone="crit" dot>Error</Badge>}
                  </td>
                  <td style={{ color: 'var(--ink-3)' }}>{l.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KpiC({ label, big, small, tone }) {
  const color = tone === 'ok' ? 'var(--ok)' : tone === 'warn' ? 'var(--warn)' : tone === 'crit' ? 'var(--crit)' : 'var(--ink)';
  return (
    <div className="card card-pad">
      <div className="page-eyebrow" style={{ marginBottom: 8 }}>{label}</div>
      <div className="serif" style={{ fontSize: 26, lineHeight: 1.15, color, letterSpacing: '-0.01em' }}>{big}</div>
      <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>{small}</div>
    </div>
  );
}

function FieldRow({ label, desc }) {
  return (
    <div className="hstack" style={{ gap: 10, padding: '6px 0', borderBottom: '1px dashed var(--border)' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--primary)' }}></span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: 'var(--ink)' }}>{label}</div>
        <div className="hint">{desc}</div>
      </div>
      <Badge tone="olive">auto</Badge>
    </div>
  );
}

function SourceCard({ s, syncing, onSync }) {
  const icons = { 'nasa-power': 'sat', 'open-meteo': 'cloud', 'agera5': 'sat', 'davis-local': 'wifi', 'manual': 'edit' };
  return (
    <div className="card">
      <div style={{ padding: '14px 18px', display: 'grid', gridTemplateColumns: '44px 1fr auto', gap: 14, alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <div style={{ width: 44, height: 44, borderRadius: 10, background: s.status === 'ok' ? 'var(--primary-tint)' : s.status === 'warn' ? 'var(--warn-tint)' : 'var(--crit-tint)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: s.status === 'ok' ? '#2C4E03' : s.status === 'warn' ? '#6E3406' : '#5C160C' }}>
          <Icon name={icons[s.id]} size={20} />
        </div>
        <div>
          <div className="hstack" style={{ gap: 10 }}>
            <div className="serif" style={{ fontSize: 17, color: 'var(--ink)' }}>{s.name}</div>
            {s.status === 'ok'   && <Badge tone="olive" dot>Activa</Badge>}
            {s.status === 'warn' && <Badge tone="warn" dot>{s.errors} errores 24h</Badge>}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 4 }}>{s.provides}</div>
        </div>
        <div className="hstack" style={{ gap: 8 }}>
          <div className="mono" style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'right' }}>
            ÚLTIMA SYNC<br/>
            <span style={{ color: 'var(--ink-3)' }}>{s.lastSync}</span>
          </div>
          <button className="btn sm" onClick={onSync} disabled={syncing || s.id === 'manual'}>
            <Icon name="refresh" size={12}/> {syncing ? 'Sincronizando…' : 'Resync'}
          </button>
        </div>
      </div>

      {s.id !== 'manual' && (
        <div style={{ padding: '12px 18px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
          <Field label="Endpoint" value={endpointFor(s.id)} mono />
          <Field label="Resolución temporal" value={s.id === 'davis-local' ? 'Horaria' : 'Diaria'} />
          <Field label="Cobertura" value={s.id === 'davis-local' ? '3 estaciones · 7 fincas' : 'Global'} />
          <Field label="Latencia típica" value={s.id === 'davis-local' ? '< 5 min' : '~ 24 h'} />
        </div>
      )}
    </div>
  );
}

function Field({ label, value, mono }) {
  return (
    <div>
      <div className="page-eyebrow" style={{ marginBottom: 4 }}>{label}</div>
      <div className={mono ? 'mono' : ''} style={{ fontSize: 12.5, color: 'var(--ink)', wordBreak: 'break-all' }}>{value}</div>
    </div>
  );
}

function endpointFor(id) {
  return ({
    'nasa-power':  'power.larc.nasa.gov/api/temporal/daily/point',
    'open-meteo':  'archive-api.open-meteo.com/v1/archive',
    'agera5':      'cds.climate.copernicus.eu/api/v2/agera5',
    'davis-local': 'http://10.0.4.18:8086/api/v2/query',
  })[id] || '—';
}

function buildSyncLog() {
  return [
    { ts: '2026-06-09 06:00:14', src: 'NASA POWER',     op: 'Cron diario',       records: 35, status: 'ok',   detail: '35/35 fincas actualizadas' },
    { ts: '2026-06-09 06:00:08', src: 'Open-Meteo',     op: 'Cron diario',       records: 35, status: 'ok',   detail: 'Latencia 1.4 s' },
    { ts: '2026-06-09 06:00:02', src: 'AgERA5',         op: 'Cron diario',       records: 33, status: 'warn', detail: 'Fincas F18, F27 sin datos · fallback NASA POWER' },
    { ts: '2026-06-09 05:59:51', src: 'Estaciones Davis', op: 'Push horario',    records: 7,  status: 'ok',   detail: 'Buffer normal · sensores activos' },
    { ts: '2026-06-08 22:14:33', src: 'AgERA5',         op: 'Cron diario',       records: 31, status: 'warn', detail: '4 fallos · timeout en Copernicus' },
    { ts: '2026-06-08 18:00:11', src: 'NASA POWER',     op: 'Cron diario',       records: 35, status: 'ok',   detail: '35/35' },
    { ts: '2026-06-08 12:30:00', src: 'Manual',         op: 'Override usuario',  records: 1,  status: 'ok',   detail: 'F08 · H.Frío <19°C → 2 100 h (Jorge Mendoza)' },
    { ts: '2026-06-08 09:14:00', src: 'NASA POWER',     op: 'Resync manual',     records: 35, status: 'ok',   detail: 'Disparado desde M4 antes de ejecutar predicción' },
    { ts: '2026-06-08 06:00:07', src: 'NASA POWER',     op: 'Cron diario',       records: 35, status: 'ok',   detail: '35/35' },
    { ts: '2026-06-08 06:00:01', src: 'Open-Meteo',     op: 'Cron diario',       records: 34, status: 'warn', detail: 'F35 sin GeoJSON · usando lat/lon manual' },
  ];
}

function nowTs() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

window.DataSources = DataSources;
