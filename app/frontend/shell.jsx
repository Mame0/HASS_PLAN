// HassPlan — shell: sidebar, topbar, navigation, toast
const { useState, useEffect, useMemo, useCallback, createContext, useContext } = React;

const NAV = [
  // --- Nivel global del fundo (estático, independiente de la campaña) ---
  { group: 'Fundo', items: [
    { id: 'global_dashboard', label: 'Panel de control global', icon: 'dashboard' },
    { id: 'fincas',           label: 'Fincas',                  icon: 'map' },
    { id: 'campaigns',        label: 'Gestión de campañas',     icon: 'campaign' },
  ]},
  // --- Bloque inyectado: contexto de la campaña seleccionada (dinámico) ---
  { context: true, items: [
    { id: 'campaign_summary', label: 'Resumen de campaña',      icon: 'dashboard' },
    { id: 'sectors',          label: 'Lotes',                   icon: 'sectors' },
    { id: 'intelligence',     label: 'Predicción IA',           icon: 'brain' },
    { id: 'harvest',          label: 'Planificación de cosecha', icon: 'harvest' },
    { id: 'labor',            label: 'Mano de obra',            icon: 'workers' },
    { id: 'logistics',        label: 'Logística',               icon: 'crate' },
    { id: 'transport',        label: 'Transporte',              icon: 'truck' },
  ]},
  { group: 'Sistema', items: [
    { id: 'alerts',     label: 'Alertas',           icon: 'bell' },
    { id: 'sources',    label: 'Fuentes de datos',  icon: 'cloud' },
  ]},
  // --- Solo proveedor (SUPERADMIN): gestión de clientes ---
  { group: 'Proveedor', superadmin: true, items: [
    { id: 'admin_productores', label: 'Productores y usuarios', icon: 'workers' },
  ]},
];

const CRUMBS = {
  global_dashboard: [['HassPlan'], ['Panel de control global']],
  dashboard:    [['HassPlan'], ['Panel de control global']],
  campaign_summary: [['HassPlan'], ['Resumen de campaña']],
  fincas:       [['HassPlan'], ['Fincas']],
  finca_new:    [['HassPlan'], ['Fincas'], ['Nueva finca']],
  finca_edit:   [['HassPlan'], ['Fincas'], ['Editar']],
  campaigns:    [['HassPlan'], ['Campañas']],
  campaign_new: [['HassPlan'], ['Campañas'], ['Nueva campaña']],
  campaign_det: [['HassPlan'], ['Campañas'], ['Campaña Hass 2025–26']],
  sectors:      [['HassPlan'], ['Lotes']],
  sector_new:   [['HassPlan'], ['Lotes'], ['Nuevo lote']],
  sector_det:   [['HassPlan'], ['Lotes'], ['Detalle']],
  sector_vars:  [['HassPlan'], ['Lotes'], ['Detalle'], ['Variables']],
  intelligence: [['HassPlan'], ['Predicción IA']],
  intelligence_res: [['HassPlan'], ['Predicción IA'], ['Resultados']],
  harvest:      [['HassPlan'], ['Cosecha']],
  harvest_cal:  [['HassPlan'], ['Cosecha'], ['Calendario']],
  labor:        [['HassPlan'], ['Mano de obra']],
  labor_req:    [['HassPlan'], ['Mano de obra'], ['Requerimientos']],
  logistics:    [['HassPlan'], ['Logística'], ['Inventario']],
  logistics_req:[['HassPlan'], ['Logística'], ['Requerimientos']],
  transport:    [['HassPlan'], ['Transporte']],
  transport_plan:[['HassPlan'], ['Transporte'], ['Plan']],
  alerts:       [['HassPlan'], ['Alertas']],
  sources:      [['HassPlan'], ['Fuentes de datos']],
  admin_productores: [['HassPlan'], ['Proveedor'], ['Productores y usuarios']],
};

// Map a route to which sidebar item is active
const ROUTE_TO_NAV = {
  global_dashboard: 'global_dashboard', dashboard: 'global_dashboard',
  campaign_summary: 'campaign_summary',
  fincas: 'fincas', finca_new: 'fincas', finca_edit: 'fincas',
  campaigns: 'campaigns', campaign_new: 'campaigns', campaign_det: 'campaigns',
  sectors: 'sectors', sector_new: 'sectors', sector_det: 'sectors', sector_vars: 'sectors',
  intelligence: 'intelligence', intelligence_res: 'intelligence',
  harvest: 'harvest', harvest_cal: 'harvest',
  labor: 'labor', labor_req: 'labor',
  logistics: 'logistics', logistics_req: 'logistics',
  transport: 'transport', transport_plan: 'transport',
  alerts: 'alerts',
  sources: 'sources',
  admin_productores: 'admin_productores',
};

const RouterCtx = createContext(null);
const useRouter = () => useContext(RouterCtx);

function esSuperadmin() {
  return !!(window.HP.currentUser && window.HP.currentUser.is_superadmin);
}

function Sidebar({ route, navigate, alertsCount }) {
  const active = ROUTE_TO_NAV[route] || 'global_dashboard';
  const campNombre = (window.HP.activeCampaign && window.HP.activeCampaign.nombre) || 'Sin campaña activa';
  // Badge de Logística = nº de materiales con déficit (pico semanal > stock). Real por
  // tenant (antes estaba hardcodeado a "1", se veía hasta en cuentas vacías).
  const logisticsDeficit = (window.HP.INVENTORY || []).filter((i) => (i.required || 0) > (i.avail || 0)).length;

  const renderItem = (it) => (
    <div
      key={it.id}
      className={'nav-item' + (active === it.id ? ' active' : '')}
      onClick={() => navigate(it.id)}
    >
      <span className="ico"><Icon name={it.icon} /></span>
      <span>{it.label}</span>
      {it.id === 'alerts' && alertsCount > 0 && (
        <span className="nav-count">{alertsCount}</span>
      )}
      {it.id === 'logistics' && logisticsDeficit > 0 && (
        <span className="nav-count warn">{logisticsDeficit}</span>
      )}
    </div>
  );

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"></div>
        <div>
          <div className="brand-name"><b>Hass</b>Plan</div>
          <div className="brand-tag">v0.4 · prototipo</div>
        </div>
      </div>
      <nav className="nav">
        {NAV.filter((g) => (esSuperadmin() ? g.superadmin : !g.superadmin)).map((g, gi) => (
          g.context ? (
            // Bloque inyectado: contexto de la campaña seleccionada
            <div className="nav-campaign-context" key={gi}>
              <div className="ctx-title">
                <span className="dot"></span>
                <span className="ctx-name" title={campNombre}>{campNombre}</span>
              </div>
              {g.items.map(renderItem)}
            </div>
          ) : (
            <div className="nav-group" key={gi}>
              <div className="nav-group-label">{g.group}</div>
              {g.items.map(renderItem)}
            </div>
          )
        ))}
      </nav>
      <SidebarUser />
    </aside>
  );
}

const ROLES = {
  SUPERADMIN: 'Proveedor (superadmin)',
  CLIENTE_ADMIN: 'Administrador',
  CLIENTE_CAMPO: 'Operario de campo',
};

function SidebarUser() {
  const u = window.HP.currentUser || {};
  const nombre = u.nombre_usuario || 'Usuario';
  const rol = ROLES[u.tipo_usuario] || 'Productor';
  const iniciales = nombre.slice(0, 2).toUpperCase();
  const salir = () => window.HP.__logout && window.HP.__logout();
  return (
    <div className="sidebar-foot">
      <div className="avatar">{iniciales}</div>
      <div className="grow">
        <div className="user-name">{nombre}</div>
        <div className="user-role">{rol}</div>
      </div>
      <span title="Cerrar sesión" style={{ color: '#8C8669', cursor: 'pointer' }} onClick={salir}>
        <Icon name="log-out" size={15} />
      </span>
    </div>
  );
}


function Topbar({ route, alertsCount, navigate }) {
  const crumb = CRUMBS[route] || CRUMBS.dashboard;
  const [open, setOpen] = useState(false);
  const [fincaOpen, setFincaOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const camps = window.HP.CAMPAIGNS || [];
  const fincas = window.HP.fincasList || [];
  const fincaSel = window.HP.selectedFinca;

  async function elegirFinca(id) {
    setFincaOpen(false);
    if (fincaSel && id === fincaSel.id) return;
    setSwitching(true);
    try { await window.HP.api.seleccionarFinca(id); }   // recarga campañas de esa finca
    finally { setSwitching(false); }
  }
  const activeId = window.HP.activeCampaign && window.HP.activeCampaign.id;
  const activeNombre = (window.HP.activeCampaign && window.HP.activeCampaign.nombre) || 'Sin campaña';
  const tone = { Activa: 'olive', Cerrada: 'neut', Borrador: 'warn' };

  async function elegir(id) {
    setOpen(false);
    if (id === activeId) return;
    setSwitching(true);
    try { await window.HP.api.seleccionarCampana(id); }   // re-fetch del bloque de campaña
    finally { setSwitching(false); }
  }

  return (
    <header className="topbar">
      <div className="crumbs">
        {crumb.map((c, i) => (
          <React.Fragment key={i}>
            <span className={i === crumb.length - 1 ? 'here' : ''}>{c[0]}</span>
            {i < crumb.length - 1 && <span className="sep"><Icon name="chev" size={12} /></span>}
          </React.Fragment>
        ))}
      </div>
      <div className="topbar-right">
        {esSuperadmin() ? (
          <span className="pill"><Icon name="workers" size={13} /> Modo proveedor</span>
        ) : (
        <React.Fragment>
        <div className="campaign-select">
          <div className="campaign-pill" title="Cambiar finca" style={{ cursor: 'pointer' }}
            onClick={() => setFincaOpen((o) => !o)}>
            <Icon name="map" size={13} />
            <span className="label">Finca:</span>
            <span className="name">{(fincaSel && fincaSel.nombre) || 'Sin finca'}</span>
            <Icon name="down" size={13} />
          </div>
          {fincaOpen && <div className="campaign-backdrop" onClick={() => setFincaOpen(false)}></div>}
          {fincaOpen && (
            <div className="campaign-menu">
              {fincas.length ? fincas.map((f) => (
                <div key={f.id}
                  className={'campaign-menu-item' + (fincaSel && f.id === fincaSel.id ? ' active' : '')}
                  onClick={() => elegirFinca(f.id)}>
                  <span className="cm-name">{f.nombre}</span>
                  <Badge tone="neut">{f.n_lotes} lotes</Badge>
                </div>
              )) : <div className="campaign-menu-empty">No hay fincas. Crea una en “Fincas”.</div>}
            </div>
          )}
        </div>
        <div className="campaign-select">
          <div className="campaign-pill" title="Cambiar campaña" style={{ cursor: 'pointer' }}
            onClick={() => setOpen((o) => !o)}>
            <span className="dot"></span>
            <span className="label">Campaña:</span>
            <span className="name">{switching ? 'Cargando…' : activeNombre}</span>
            <Icon name="down" size={13} />
          </div>
          {open && <div className="campaign-backdrop" onClick={() => setOpen(false)}></div>}
          {open && (
            <div className="campaign-menu">
              {camps.length ? camps.map((c) => (
                <div key={c.id}
                  className={'campaign-menu-item' + (c.id === activeId ? ' active' : '')}
                  onClick={() => elegir(c.id)}>
                  <span className="cm-name">{c.name}</span>
                  <Badge tone={tone[c.status] || 'neut'} dot={c.status === 'Activa'}>{c.status}</Badge>
                </div>
              )) : <div className="campaign-menu-empty">No hay campañas. Crea una en Gestión de campañas.</div>}
            </div>
          )}
        </div>
        <span className="hstack" style={{ color: 'var(--ink-3)', fontSize: 12 }}>
          <Icon name="sun" size={14} /> 19.4 °C
          <span style={{ color: 'var(--muted)' }}>·</span>
          <Icon name="drop" size={14} /> 62 %
        </span>
        <button className="icon-btn" title="Alertas" onClick={() => navigate('alerts')}>
          <Icon name="bell" />
          {alertsCount > 0 && <span className="badge">{alertsCount}</span>}
        </button>
        <button className="icon-btn" title="Mensajes"><Icon name="chat" /></button>
        <button className="icon-btn" title="Ajustes"><Icon name="cog" /></button>
        </React.Fragment>
        )}
      </div>
    </header>
  );
}

// ---- Helpers exposed
function Toast({ msg }) {
  if (!msg) return null;
  return <div className="toast">{msg}</div>;
}

function Sem({ level, label }) {
  return (
    <span className="sem">
      <span className={`sem-dot sem-${level}`}></span>
      <span>{label}</span>
    </span>
  );
}

function Badge({ tone = 'neut', children, dot }) {
  return <span className={'badge ' + tone + (dot ? ' dot' : '')}>{children}</span>;
}

// ¿La campaña cargada está cerrada? -> sus módulos van en solo lectura (backend devuelve 409).
function esCampanaCerrada() {
  return !!(window.HP.activeCampaign && window.HP.activeCampaign.estado === 'cerrada');
}

function LockBanner() {
  if (!esCampanaCerrada()) return null;
  return (
    <div className="lock-banner">
      <Icon name="x" size={14} />
      <span><b>Campaña cerrada</b> — histórico en solo lectura. Actívala desde <b>Gestión de campañas</b> para volver a modificar lotes, variables y planes.</span>
    </div>
  );
}

function PageHeader({ eyebrow, title, sub, actions }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <h1 className="page-title">{title}</h1>
        {sub && <div className="page-sub">{sub}</div>}
      </div>
      {actions && <div className="hstack">{actions}</div>}
    </div>
  );
}

function Tabs({ items, value, onChange }) {
  return (
    <div className="tabs">
      {items.map((it) => (
        <button
          key={it.id}
          className={'tab' + (value === it.id ? ' active' : '')}
          onClick={() => onChange(it.id)}
        >{it.label}</button>
      ))}
    </div>
  );
}

Object.assign(window, {
  RouterCtx, useRouter, Sidebar, Topbar, Toast, Sem, Badge, PageHeader, Tabs,
  LockBanner, esCampanaCerrada,
});
