// HassPlan — main App
// Rutas que pertenecen al bloque de contexto de campaña (solo lectura si está cerrada).
const CAMPAIGN_ROUTES = new Set([
  'campaign_summary', 'sectors', 'sector_new', 'sector_det', 'sector_vars',
  'intelligence', 'intelligence_res', 'harvest', 'harvest_cal',
  'labor', 'labor_req', 'logistics', 'logistics_req', 'transport', 'transport_plan',
]);

function App({ initialRoute }) {
  const [route, setRoute] = useState(initialRoute || 'global_dashboard');
  const [toast, setToast] = useState(null);
  // Permite que api.js fuerce un re-render tras recargar datos (cambio de campaña).
  const [, setTick] = useState(0);
  React.useEffect(() => { window.HP.__rerender = () => setTick((t) => t + 1); }, []);

  const navigate = useCallback((r) => {
    setRoute(r);
    // scroll content to top
    setTimeout(() => {
      const c = document.querySelector('.content');
      if (c) c.scrollTo({ top: 0, behavior: 'instant' });
    }, 0);
  }, []);

  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1900);
  }, []);

  const router = useMemo(() => ({ route, navigate, toast: showToast }), [route, navigate, showToast]);

  const alertsCount = window.HP.ALERTS.length;

  return (
    <RouterCtx.Provider value={router}>
      <div className="app">
        <Sidebar route={route} navigate={navigate} alertsCount={alertsCount} />
        <div className="main">
          <Topbar route={route} alertsCount={alertsCount} navigate={navigate} />
          <div className="content">
            {CAMPAIGN_ROUTES.has(route) && <LockBanner />}
            <View route={route} />
          </div>
        </div>
        <Toast msg={toast} />
      </div>
    </RouterCtx.Provider>
  );
}

function View({ route }) {
  switch (route) {
    case 'global_dashboard':  return <GlobalDashboard />;
    case 'campaign_summary':  return <ViewCampaignSummary />;
    case 'dashboard':         return <GlobalDashboard />;  // alias temporal (nav viejo)
    case 'fincas':            return <FincasManager />;
    case 'campaigns':         return <Campaigns />;
    case 'campaign_new':      return <CampaignNew />;
    case 'campaign_det':      return <CampaignDetail />;
    case 'sectors':           return <Sectors />;
    case 'sector_new':        return <SectorNew />;
    case 'sector_det':        return <SectorDetail />;
    case 'sector_vars':       return <SectorVars />;
    case 'intelligence':      return <Intelligence />;
    case 'intelligence_res':  return <IntelligenceResult />;
    case 'harvest':           return <Harvest />;
    case 'harvest_cal':       return <HarvestCalendar />;
    case 'labor':             return <Labor />;
    case 'labor_req':         return <Labor />;
    case 'logistics':         return <Logistics />;
    case 'logistics_req':     return <Logistics />;
    case 'transport':         return <Transport />;
    case 'transport_plan':    return <Transport />;
    case 'alerts':            return <Alerts />;
    case 'sources':           return <DataSources />;
    case 'admin_productores': return <AdminPanel />;
    default:                  return <GlobalDashboard />;
  }
}

// Gate de autenticación: comprueba la sesión, muestra login si hace falta y solo
// monta la app tras cargar los datos del tenant logueado.
function Root() {
  const [phase, setPhase] = useState('checking');   // checking | login | ready

  const loadApp = useCallback(async (usuario) => {
    window.HP.currentUser = usuario;
    // El SUPERADMIN (proveedor) NO carga datos operativos de clientes: su única vista
    // es la gestión de productores/usuarios. Solo los clientes cargan su tenant.
    if (!usuario.is_superadmin) {
      await window.HP.api.cargarTodo();              // datos del tenant (RLS en backend)
    }
    setPhase('ready');
  }, []);

  useEffect(() => {
    // Logout disponible para el sidebar.
    window.HP.__logout = async () => {
      await window.HP.api.logout().catch(() => {});
      window.HP.currentUser = null;
      setPhase('login');
    };
    (async () => {
      const me = await window.HP.api.me();
      if (me && me.usuario_id) await loadApp(me);
      else setPhase('login');
    })();
  }, [loadApp]);

  if (phase === 'checking') return <div className="auth-wrap"><div className="auth-foot">Cargando…</div></div>;
  if (phase === 'login') return <LoginScreen onSuccess={loadApp} />;
  // Deep-link opcional: /#<ruta> abre esa vista al entrar. El SUPERADMIN entra
  // directo a la gestión de productores (no tiene vistas operativas).
  const isSuper = window.HP.currentUser && window.HP.currentUser.is_superadmin;
  const initialRoute = (window.location.hash || '').replace('#', '')
    || (isSuper ? 'admin_productores' : undefined);
  return <App initialRoute={initialRoute} />;
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root />);
