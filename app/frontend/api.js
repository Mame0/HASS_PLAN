// HassPlan — capa de datos REAL.
// Se carga DESPUÉS de data.js (que define la forma + helpers + fallback simulado) y
// sobreescribe las partes dinámicas de window.HP con datos de la API REST (/api).
// Expone window.HP_READY (promesa) que app.jsx espera antes del primer render.
(function () {
  const API = '/api';
  // Densidad por defecto (plantas/Ha) cuando el lote no la tiene registrada. Marco
  // de plantación típico de palta Hass; solo se usa como fallback para estimar nº de árboles.
  const DENSIDAD_DEFAULT = 350;

  async function get(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(path + ' -> ' + r.status);
    return r.json();
  }

  async function send(method, path, body) {
    const r = await fetch(API + path, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    const data = await r.json().catch(() => ({}));
    // El error puede venir como {error}/{message} o, en el sync de clima, dentro de
    // {sync:{mensaje}} (ej. campaña futura -> 502 con explicación clara). Se prioriza
    // ese mensaje legible antes de caer al genérico "path -> status".
    if (!r.ok) {
      throw new Error(
        data.error || data.message || (data.sync && data.sync.mensaje) || (path + ' -> ' + r.status)
      );
    }
    return data;
  }
  const post = (path, body) => send('POST', path, body);
  const put = (path, body) => send('PUT', path, body);
  const del = (path) => send('DELETE', path);

  // frutos/árbol y peso del fruto son FUGA DE DATOS (corr. ~0.88 con el rendimiento):
  // se ocultan en el front, igual que se excluyen del modelo en el backend.
  const FUGA = ['frutosArbol', 'pesoFruto'];

  // Claves del backend (snake_case) -> claves del prototipo (camelCase).
  // Nota: frutos_arbol / peso_fruto se omiten a propósito (anti-fuga).
  const VAR_MAP = {
    edad_campo: 'edadCampo', edad_prod: 'edadProd', riego_m3ha: 'riegoM3',
    hfrio_19: 'hFrio19', hfrio_15: 'hFrio15', hfrio_14: 'hFrio14', hfrio_14_19: 'hFrio1419',
    hac_20_25: 'hAc2025', hac_25: 'hAcM25',
    t_prom: 'tProm', t_min: 'tMin', t_max: 'tMax', humedad: 'humedadProm',
    lluvia: 'lluvia', eto: 'eto',
  };
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

  function adaptCampaigns(camps) {
    return camps.map((c) => ({
      id: c.id, name: c.nombre, start: c.fecha_inicio, end: c.fecha_fin,
      status: cap(c.estado), fincas: 0, area: 0, plannedTons: 0, harvestedTons: 0,
    }));
  }

  function adaptSources(fs) {
    return fs.map((f) => ({
      id: f.tipo, name: f.nombre, provides: f.resolucion || '',
      status: f.activa ? 'ok' : 'warn', lastSync: '—', errors: 0,
    }));
  }

  function adaptAlerts(als) {
    const sev = { alta: 'crit', media: 'warn', baja: 'info' };
    const mod = { mano_obra: 'Mano de obra', logistica: 'Logística', transporte: 'Transporte' };
    return als.map((a) => ({
      id: 'AL-' + a.id, sev: sev[a.severidad] || 'warn',
      module: mod[a.modulo_origen] || a.modulo_origen, title: a.mensaje, desc: '',
      date: (a.fecha_creacion || '').slice(0, 10),
      action: a.estado === 'activa' ? 'Revisar' : 'Resuelta', finca: '',
    }));
  }

  function adaptWeeks(plan) {
    if (!plan || !plan.semanas) return [];
    return plan.semanas.map((s) => ({
      id: s.id, week: s.numero_semana, label: 'S' + String(s.numero_semana).padStart(2, '0'),
      dates: (s.fecha_inicio || '') + ' – ' + (s.fecha_fin || ''),
      planned: s.tn_planificada, real: s.tn_real, pct: (s.porcentaje || 0) / 100,
    }));
  }

  function adaptInventory(inv, log) {
    const pico = {};    // requerido pico (semanal) por material
    const total = {};   // requerido total de campaña por material
    if (log && log.semanas) {
      log.semanas.forEach((s) => (s.materiales || []).forEach((m) => {
        pico[m.material] = Math.max(pico[m.material] || 0, m.cantidad_requerida || 0);
        total[m.material] = (total[m.material] || 0) + (m.cantidad_requerida || 0);
      }));
    }
    return inv.map((i) => ({
      id: i.id, item: i.material, unit: i.unidad || 'und', avail: i.cantidad_disponible,
      consumoPorTn: i.consumo_por_tn,
      required: Math.round(pico[i.material] || 0),         // pico semanal
      requiredTotal: Math.round(total[i.material] || 0),   // total de campaña
      lead: '—',
    }));
  }

  // Cada "finca" del prototipo = un LOTE nuestro (con sus variables + predicción).
  // Los lotes se piden POR CAMPAÑA (/campanas/<id>/lotes): cada campaña tiene su propio
  // set de lotes (un lote agregado en 24-25 NO aparece en 25-26). El campanaId también
  // hace scope de variables/predicción (re-fetch al cambiar de campaña en la cabecera).
  async function cargarLotesComoFincas(campanaId) {
    if (!campanaId) return [];
    const q = '?campana_id=' + campanaId;
    // Nombre de finca por id (los lotes traen finca_id pero no el nombre).
    const fincas = await get('/fincas').catch(() => []);
    const nombreFinca = Object.fromEntries(fincas.map((f) => [f.id, f.nombre]));
    const lotes = await get('/campanas/' + campanaId + '/lotes').catch(() => []);
    const out = [];
    for (const l of lotes) {
      const vars = {};
      let pred = null;
      let pendientes = 0;   // variables (manual+clima) aún sin valor
      try {
        const v = await get('/lotes/' + l.id + '/variables' + q);
        [...(v.manual || []), ...(v.api || [])].forEach((row) => {
          // Solo las features del MODELO (VAR_MAP) cuentan; frutos_arbol/peso_fruto son
          // resultado de cosecha (anti-fuga), no entradas, y están vacías antes de cosechar.
          if (VAR_MAP[row.key]) {
            vars[VAR_MAP[row.key]] = row.value;
            if (row.value === null || row.value === undefined) pendientes++;
          }
        });
      } catch (e) { /* sin variables aún */ }
      try { pred = await get('/lotes/' + l.id + '/prediccion' + q); } catch (e) { /* sin predicción */ }
      const tn = pred ? pred.tn_ha : null;
      // Historial productivo del lote a través de TODAS sus campañas (no se filtra por
      // campana_id): Tn/Ha real si hay cosecha, si no la predicción. avg/máx/mín salen de aquí.
      let history = [];
      try {
        const h = await get('/lotes/' + l.id + '/historial');
        history = (h || [])
          .filter((x) => x.tn_ha != null)
          .map((x) => ({ c: x.campana, y: x.tn_ha, fuente: x.fuente, estado: x.estado }));
      } catch (e) { /* sin historial */ }
      const ys = history.map((x) => x.y);
      const avgY = ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : null;
      const maxY = ys.length ? Math.max(...ys) : null;
      const minY = ys.length ? Math.min(...ys) : null;
      out.push({
        id: l.id, name: l.nombre, fincaId: l.finca_id, fincaName: nombreFinca[l.finca_id] || '',
        area: l.area_ha, variety: l.variedad || 'Hass',
        anoPlantacion: l.ano_plantacion,
        edadCampo: vars.edadCampo, edadProd: vars.edadProd,
        densidadPlantasHa: l.densidad_plantas_ha != null ? l.densidad_plantas_ha : null,
        trees: Math.round((l.area_ha || 0) * (l.densidad_plantas_ha > 0 ? l.densidad_plantas_ha : DENSIDAD_DEFAULT)),
        last: Object.assign({ finca: l.nombre, campana: '', tnHa: tn }, vars),
        expectedYieldHa: tn, lastYield: tn, lastYieldHa: tn,
        avgYield: avgY, maxYield: maxY, minYield: minY, history: history,
        // confianza real del modelo (%) y estado de datos para el módulo de predicción.
        confianza: pred && pred.confianza != null ? pred.confianza / 100 : null,
        // intervalo plausible p10–p90 del bosque (Tn/Ha) — incertidumbre real de la predicción.
        intervalo: pred && pred.intervalo ? pred.intervalo : null,
        tienePrediccion: !!pred, pendientes: pendientes,
        status: pendientes > 0 ? 'warn' : 'ok', syncOk: true,
        lat: l.latitud, lon: l.longitud, geometria: l.geometria,
      });
    }
    return out;
  }

  // IMPORTANTE: los módulos desestructuran window.HP AL CARGAR (antes de este fetch),
  // así que NO se puede reasignar window.HP.X = nuevo (quedaría apuntando al array viejo).
  // Hay que MUTAR EN SU LUGAR los mismos arrays que ya capturaron los módulos.
  function fill(name, items) {
    if (!Array.isArray(window.HP[name])) window.HP[name] = [];
    window.HP[name].length = 0;
    (items || []).forEach((x) => window.HP[name].push(x));
  }

  // campanaId opcional: "campaña de trabajo" = id pedido -> activa -> primera.
  // Hoy se llama sin args (usa la activa). El parámetro deja preparada la futura
  // vista de solo-lectura de cualquier campaña sin tocar el estado activo.
  async function cargarTodo(campanaId) {
    // Anti-fuga: quitar frutos/árbol y peso del fruto in-place (SECTOR_VARS es la misma ref).
    for (let i = window.HP.VARS.length - 1; i >= 0; i--) {
      if (FUGA.includes(window.HP.VARS[i].key)) window.HP.VARS.splice(i, 1);
    }
    try {
      // Fincas del productor + finca seleccionada (contexto). Las campañas se
      // filtran POR FINCA: cada finca tiene las suyas, separadas de las demás.
      const fincas = await get('/fincas').catch(() => []);
      window.HP.fincasList = fincas;
      const fincaSel = fincas.find((f) => f.id === window.HP.selectedFincaId) || fincas[0] || null;
      window.HP.selectedFincaId = fincaSel ? fincaSel.id : null;
      window.HP.selectedFinca = fincaSel;

      const camps = fincaSel ? await get('/campanas?finca_id=' + fincaSel.id) : [];
      const campAdapt = adaptCampaigns(camps);
      const activa = (campanaId && camps.find((c) => c.id === campanaId))
        || camps.find((c) => c.estado === 'activa') || camps[0];

      const fuentes = await get('/fuentes').catch(() => []);
      fill('SOURCES', adaptSources(fuentes));

      // Panel global del fundo (histórico multi-campaña): acotado a la finca
      // seleccionada para que sus KPIs concuerden con el nombre del encabezado.
      const fincaQ = fincaSel ? '?finca_id=' + fincaSel.id : '';
      window.HP.fundo = await get('/fundo/dashboard' + fincaQ).catch(() => null);

      // Reset de los datos por-campaña: se limpian SIEMPRE (aunque no haya campaña
      // activa ni lotes) para NO dejar los datos simulados de data.js en un tenant
      // vacío — bug multi-tenant: una cuenta sin datos mostraba lotes/alertas demo.
      fill('ALERTS', []); fill('WEEKS', []); fill('INVENTORY', []); fill('FINCAS', []);
      window.HP.manoObra = null; window.HP.logistica = null; window.HP.transporte = null;
      window.HP.dashboard = null; window.HP.plan = null; window.HP.estimadoTn = 0;
      window.HP.activeCampaign = null;

      if (activa) {
        const cid = activa.id;
        const [alertas, plan, inv, log, manoObra, transporte, lotes] = await Promise.all([
          get('/campanas/' + cid + '/alertas').catch(() => []),
          get('/campanas/' + cid + '/plan-cosecha').catch(() => null),
          get('/campanas/' + cid + '/inventario').catch(() => []),
          get('/campanas/' + cid + '/logistica').catch(() => null),
          get('/campanas/' + cid + '/mano-obra').catch(() => null),
          get('/campanas/' + cid + '/transporte').catch(() => null),
          cargarLotesComoFincas(cid).catch(() => []),
        ]);
        fill('ALERTS', adaptAlerts(alertas));
        fill('WEEKS', adaptWeeks(plan));
        fill('INVENTORY', adaptInventory(inv, log));
        fill('FINCAS', lotes);   // SECTORS es la misma ref -> se actualiza (vacío = se limpia)
        window.HP.manoObra = manoObra;   // M6: parámetros + jornales/cuadrillas/déficit por semana
        window.HP.logistica = log;       // M7: requerimiento de materiales por semana (real)
        window.HP.transporte = transporte; // M8: camiones/viajes/costo/déficit por semana (real)
        window.HP.dashboard = await get('/campanas/' + cid + '/dashboard').catch(() => null);
        // Plan de cosecha crudo + total ESTIMADO (Σ predicciones de los lotes) para que la
        // página de Cosecha lea valores reales en vez de constantes hardcodeadas.
        window.HP.plan = plan;
        window.HP.estimadoTn = +lotes.reduce(
          (s, l) => s + (l.expectedYieldHa || 0) * (l.area || 0), 0).toFixed(2);
        // KPIs reales del panel: enriquecer la campaña activa con totales del plan/lotes.
        const ca = campAdapt.find((c) => c.id === activa.id);
        if (ca) {
          ca.plannedTons = plan ? Math.round(plan.tn_total) : 0;
          ca.area = +lotes.reduce((s, l) => s + (l.area || 0), 0).toFixed(1);
          ca.fincas = lotes.length;
          ca.sectors = lotes.length;
        }
        window.HP.activeCampaign = activa;
      }
      fill('CAMPAIGNS', campAdapt);
      window.HP.__live = true;
      console.info('HassPlan: datos en vivo desde /api ✓');
    } catch (e) {
      console.warn('HassPlan: API no disponible, usando datos simulados de data.js.', e);
      window.HP.__live = false;
    }
    // Re-render de la SPA tras (re)cargar datos — p. ej. al cambiar de campaña en la cabecera.
    if (window.HP.__rerender) window.HP.__rerender();
    return window.HP;
  }

  // ---- API de ESCRITURA: los formularios del front llaman estos helpers ----
  const VAR_MAP_INV = Object.fromEntries(Object.entries(VAR_MAP).map(([k, v]) => [v, k]));
  window.HP.api = {
    get: get, post: post, put: put, del: del,
    refrescar: () => cargarTodo(),    // recarga window.HP (campaña activa) tras un guardado
    // Carga los datos de UNA campaña concreta (escalable a solo-lectura sin activarla).
    seleccionarCampana: (id) => cargarTodo(id),
    fincas: () => get('/fincas'),
    // CRUD de fincas (un productor puede tener varias).
    obtenerFinca: (id) => get('/fincas/' + id),
    crearFinca: (body) => post('/fincas', body),
    editarFinca: (id, body) => put('/fincas/' + id, body),
    eliminarFinca: (id) => del('/fincas/' + id),
    // Devuelve el id de la primera finca; si no hay ninguna, crea una con nombre genérico
    // (NO atado a un tenant concreto: el productor la renombra en su ficha de finca).
    asegurarFinca: async function (nombre) {
      const fs = await get('/fincas');
      if (fs.length) return fs[0].id;
      const f = await post('/fincas', { nombre: nombre || 'Mi Finca' });
      return f.id;
    },
    fundoDashboard: () => get('/fundo/dashboard' + (window.HP.selectedFincaId ? '?finca_id=' + window.HP.selectedFincaId : '')),
    // Id de la campaña de trabajo (la activa que el front tiene cargada).
    campanaActivaId: () => (window.HP.activeCampaign && window.HP.activeCampaign.id) || null,
    // Crea el lote y lo asocia a la campaña de trabajo (entra SOLO a esa campaña).
    crearLote: function (fincaId, body) {
      const cid = (window.HP.activeCampaign && window.HP.activeCampaign.id) || null;
      return post('/fincas/' + fincaId + '/lotes', Object.assign({ campana_id: cid }, body));
    },
    editarLote: (id, body) => put('/lotes/' + id, body),
    // Asocia un lote EXISTENTE a la campaña de trabajo (o la indicada).
    asociarLote: function (loteId, campanaId) {
      const cid = campanaId || (window.HP.activeCampaign && window.HP.activeCampaign.id);
      return post('/campanas/' + cid + '/lotes/' + loteId);
    },
    // "Eliminar lote" = quitarlo de la campaña de trabajo (no borra su histórico en otras).
    eliminarLote: function (id) {
      const cid = (window.HP.activeCampaign && window.HP.activeCampaign.id) || null;
      return cid ? del('/campanas/' + cid + '/lotes/' + id) : del('/lotes/' + id);
    },
    // Borra el lote FÍSICO y todo su histórico en TODAS las campañas (acción destructiva).
    eliminarLoteFisico: (id) => del('/lotes/' + id),
    // M4 Predicción: corre el modelo para un lote en una campaña (devuelve tn_ha + OOD).
    predecirLote: (loteId, campanaId) => post('/lotes/' + loteId + '/prediccion?campana_id=' + campanaId),
    // M5 Cosecha: generar/reprogramar el plan (columna vertebral de la cascada).
    generarPlanCosecha: (campanaId, body) => post('/campanas/' + campanaId + '/plan-cosecha', body),
    reprogramarSemana: (semanaId, tn) => put('/semanas/' + semanaId, { tn_planificada: tn }),
    // F7: cosecha real por semana (real vs planificado). tn=null borra el registro.
    registrarCosechaReal: (semanaId, tn) => put('/semanas/' + semanaId + '/real', { tn_real: tn }),
    // F7: validación predicho vs real POR LOTE (cierre del modelo).
    resultadosCampana: (campanaId) => get('/campanas/' + campanaId + '/resultados'),
    guardarResultado: (loteId, campanaId, body) => put('/lotes/' + loteId + '/resultado?campana_id=' + campanaId, body),
    borrarResultado: (loteId, campanaId) => del('/lotes/' + loteId + '/resultado?campana_id=' + campanaId),
    // M6 Mano de obra: configura productividad/cuadrillas y calcula jornales por semana.
    configManoObra: (campanaId, body) => put('/campanas/' + campanaId + '/mano-obra', body),
    // M7 Logística: fija el stock de materiales (recalcula requerimientos por semana).
    setInventario: (campanaId, items) => put('/campanas/' + campanaId + '/inventario', { items: items }),
    // M8 Transporte: configura flota/capacidad y calcula camiones/viajes/costo por semana.
    configTransporte: (campanaId, body) => put('/campanas/' + campanaId + '/transporte', body),
    // ---- Panel SUPERADMIN: gestión de productores y usuarios ----
    admin: {
      productores: () => get('/admin/productores'),
      crearProductor: (body) => post('/admin/productores', body),
      editarProductor: (id, body) => put('/admin/productores/' + id, body),
      usuarios: (productorId) => get('/admin/productores/' + productorId + '/usuarios'),
      crearUsuario: (body) => post('/admin/usuarios', body),
      editarUsuario: (id, body) => put('/admin/usuarios/' + id, body),
    },
    // ---- Autenticación (sesión por cookie; fetch la envía same-origin) ----
    me: () => fetch(API + '/auth/me').then((r) => (r.ok ? r.json() : null)).catch(() => null),
    login: (usuario, clave) => post('/auth/login', { usuario: usuario, clave: clave }),
    logout: () => post('/auth/logout', {}),
    // Carga/recarga TODOS los datos del tenant logueado (lo llama el gate de login).
    cargarTodo: () => cargarTodo(),
    // Crea la campaña en la FINCA seleccionada (cada finca tiene sus campañas).
    crearCampana: (body) => post('/campanas', Object.assign({ finca_id: window.HP.selectedFincaId }, body)),
    editarCampana: (id, body) => put('/campanas/' + id, body),
    // Cambiar de finca: recarga las campañas de esa finca (resetea la campaña activa).
    seleccionarFinca: function (id) {
      window.HP.selectedFincaId = id;
      window.HP.activeCampaign = null;
      return cargarTodo();
    },
    fincaSeleccionadaId: () => window.HP.selectedFincaId || null,
    activarCampana: (id) => post('/campanas/' + id + '/activar'),
    cerrarCampana: (id) => post('/campanas/' + id + '/cerrar'),
    eliminarCampana: (id) => del('/campanas/' + id),
    sincronizarClima: (loteId, campanaId) =>
      post('/lotes/' + loteId + '/clima/sync?campana_id=' + campanaId),
    // key llega en camelCase (forma del front) -> se traduce a snake_case del backend.
    // Se DEBE pasar campana_id de la campaña de trabajo: sin él, el backend resuelve la
    // activa del tenant (que puede ser de OTRA finca) -> 400 "el lote pertenece a otra
    // finca que la campaña". Cada finca tiene su propia campaña activa.
    guardarVariable: function (loteId, keyCamel, valor) {
      const cid = (window.HP.activeCampaign && window.HP.activeCampaign.id) || null;
      const q = cid ? '?campana_id=' + cid : '';
      return put('/lotes/' + loteId + '/variables/' + (VAR_MAP_INV[keyCamel] || keyCamel) + q,
        { valor: valor });
    },
  };

  // El gate de login (app.jsx) decide cuándo cargar: tras autenticar llama a
  // window.HP.api.cargarTodo(). Antes había un cargarTodo() automático aquí.
  window.HP_READY = Promise.resolve();
})();
