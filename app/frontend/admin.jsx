// HassPlan — Panel del PROVEEDOR (SUPERADMIN): productores y sus usuarios.
// Visible solo para usuarios SUPERADMIN (el sidebar filtra el grupo "Proveedor").
// Consume /api/admin/* (guardado en backend a is_superadmin).

function AdminPanel() {
  const router = useRouter();
  const [items, setItems] = useState(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);     // productor en edición (o null)
  const [managing, setManaging] = useState(null);   // productor en gestión de usuarios
  const [q, setQ] = useState('');                   // filtro de búsqueda

  const load = useCallback(async () => {
    try { setItems(await window.HP.api.admin.productores()); }
    catch (e) { router.toast('Error: ' + e.message); setItems([]); }
  }, [router]);
  useEffect(() => { load(); }, [load]);

  async function toggleActivo(p) {
    try { await window.HP.api.admin.editarProductor(p.id, { activo: !p.activo }); load(); }
    catch (e) { router.toast('Error: ' + e.message); }
  }

  if (managing) {
    return <AdminUsuarios productor={managing} onBack={() => { setManaging(null); load(); }} />;
  }

  // KPIs del proveedor (se calculan desde la lista; sin llamada extra al backend).
  const stats = items ? {
    total: items.length,
    activos: items.filter((p) => p.activo).length,
    usuarios: items.reduce((s, p) => s + (p.n_usuarios || 0), 0),
    fincas: items.reduce((s, p) => s + (p.n_fincas || 0), 0),
  } : null;

  // Filtro por nombre / RUC / correo.
  const filtro = q.trim().toLowerCase();
  const visibles = (items || []).filter((p) => !filtro
    || (p.nombre_comercial || '').toLowerCase().includes(filtro)
    || (p.ruc_dni || '').toLowerCase().includes(filtro)
    || (p.correo_contacto || '').toLowerCase().includes(filtro));

  function nuevoProductor() { setEditing(null); setCreating((c) => !c); }
  function editarProductor(p) { setCreating(false); setEditing(p); }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Proveedor"
        title="Productores y usuarios"
        sub="Da de alta clientes (productores) y gestiona sus usuarios. Cada productor queda aislado por RLS en la base de datos."
        actions={
          <button className="btn primary" onClick={nuevoProductor}>
            {creating ? 'Cancelar' : '+ Nuevo productor'}
          </button>
        }
      />

      {stats && (
        <div className="kpi-grid" style={{ marginBottom: 16 }}>
          <Kpi icon="dashboard" label="Productores" value={String(stats.total)} unit=""
            foot={<span>{stats.activos} activos · {stats.total - stats.activos} inactivos</span>} />
          <Kpi icon="workers" label="Usuarios" value={String(stats.usuarios)} unit=""
            foot={<span>en toda la plataforma</span>} />
          <Kpi icon="map" label="Fincas" value={String(stats.fincas)} unit=""
            foot={<span>registradas por los clientes</span>} />
          <Kpi icon="check" label="Activos" value={String(stats.activos)} unit={'/ ' + stats.total}
            foot={<span>productores operativos</span>} />
        </div>
      )}

      {creating && (
        <ProductorForm
          onSaved={() => { setCreating(false); load(); router.toast('Productor creado'); }}
          onError={(m) => router.toast(m)}
        />
      )}
      {editing && (
        <ProductorForm
          productor={editing}
          onSaved={() => { setEditing(null); load(); router.toast('Productor actualizado'); }}
          onCancel={() => setEditing(null)}
          onError={(m) => router.toast(m)}
        />
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <h3>Productores registrados</h3>
          <div className="hstack" style={{ background: 'var(--surface)', border: '1px solid var(--border-2)', borderRadius: 8, padding: '0 10px', height: 34, gap: 8 }}>
            <Icon name="search" size={14} />
            <input style={{ border: 0, outline: 0, background: 'transparent', height: 32, fontSize: 13, width: 200 }}
              placeholder="Buscar productor…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
        {items === null ? (
          <div className="empty">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="empty">Aún no hay productores. Crea el primero.</div>
        ) : visibles.length === 0 ? (
          <div className="empty">Sin coincidencias para “{q}”.</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Productor</th><th>RUC / DNI</th><th>Contacto</th>
                <th className="num">Usuarios</th><th className="num">Fincas</th>
                <th>Estado</th><th></th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((p) => (
                <tr key={p.id}>
                  <td className="strong">{p.nombre_comercial}</td>
                  <td>{p.ruc_dni || '—'}</td>
                  <td>{p.correo_contacto || '—'}</td>
                  <td className="num">{p.n_usuarios}</td>
                  <td className="num">{p.n_fincas}</td>
                  <td><Badge tone={p.activo ? 'ok' : 'neut'} dot={p.activo}>{p.activo ? 'Activo' : 'Inactivo'}</Badge></td>
                  <td className="hstack">
                    <button className="btn sm" onClick={() => setManaging(p)}>Usuarios</button>
                    <button className="btn sm ghost" onClick={() => editarProductor(p)}>Editar</button>
                    <button className="btn sm ghost" onClick={() => toggleActivo(p)}>
                      {p.activo ? 'Desactivar' : 'Activar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// Formulario de productor. Sin `productor` => alta (con admin inicial opcional).
// Con `productor` => edición de sus datos (nombre, RUC, contacto, teléfono).
function ProductorForm({ productor, onSaved, onCancel, onError }) {
  const editMode = !!productor;
  const [f, setF] = useState({
    nombre_comercial: productor ? (productor.nombre_comercial || '') : '',
    ruc_dni: productor ? (productor.ruc_dni || '') : '',
    correo_contacto: productor ? (productor.correo_contacto || '') : '',
    telefono: productor ? (productor.telefono || '') : '',
    admin_user: '', admin_correo: '', admin_clave: '',
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => Object.assign({}, s, { [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const body = {
        nombre_comercial: f.nombre_comercial, ruc_dni: f.ruc_dni,
        correo_contacto: f.correo_contacto, telefono: f.telefono,
      };
      if (editMode) {
        await window.HP.api.admin.editarProductor(productor.id, body);
      } else {
        if (f.admin_user && f.admin_clave) {
          body.admin = { nombre_usuario: f.admin_user, correo: f.admin_correo, clave: f.admin_clave };
        }
        await window.HP.api.admin.crearProductor(body);
      }
      onSaved();
    } catch (err) { onError('Error: ' + err.message); setBusy(false); }
  }

  return (
    <form className="card card-pad" onSubmit={submit} style={{ marginTop: 16 }}>
      <div className="page-eyebrow" style={{ marginBottom: 10 }}>
        {editMode ? 'Editar productor · ' + productor.nombre_comercial : 'Nuevo productor'}
      </div>
      <div className="row-3">
        <div className="field"><label>Nombre comercial *</label>
          <input value={f.nombre_comercial} onChange={set('nombre_comercial')} placeholder="ej. Fundo San Andrés" /></div>
        <div className="field"><label>RUC / DNI</label><input value={f.ruc_dni} onChange={set('ruc_dni')} /></div>
        <div className="field"><label>Correo de contacto</label><input value={f.correo_contacto} onChange={set('correo_contacto')} /></div>
      </div>
      <div className="row-3">
        <div className="field"><label>Teléfono</label><input value={f.telefono} onChange={set('telefono')} /></div>
      </div>

      {!editMode && (
        <React.Fragment>
          <div className="divider-h"></div>
          <div className="page-eyebrow" style={{ marginBottom: 10 }}>Administrador inicial (opcional)</div>
          <div className="row-3">
            <div className="field"><label>Usuario</label><input value={f.admin_user} onChange={set('admin_user')} placeholder="ej. sanandres" /></div>
            <div className="field"><label>Correo</label><input value={f.admin_correo} onChange={set('admin_correo')} /></div>
            <div className="field"><label>Contraseña</label><input type="password" value={f.admin_clave} onChange={set('admin_clave')} /></div>
          </div>
        </React.Fragment>
      )}

      <div className="hstack">
        <button className="btn primary" disabled={busy || !f.nombre_comercial}>
          {busy ? 'Guardando…' : (editMode ? 'Guardar cambios' : 'Crear productor')}
        </button>
        {editMode && onCancel && <button type="button" className="btn ghost" onClick={onCancel}>Cancelar</button>}
      </div>
    </form>
  );
}

function AdminUsuarios({ productor, onBack }) {
  const router = useRouter();
  const [items, setItems] = useState(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try { setItems(await window.HP.api.admin.usuarios(productor.id)); }
    catch (e) { router.toast('Error: ' + e.message); setItems([]); }
  }, [productor.id, router]);
  useEffect(() => { load(); }, [load]);

  async function toggle(u) {
    try { await window.HP.api.admin.editarUsuario(u.id, { activo: !u.activo }); load(); }
    catch (e) { router.toast('Error: ' + e.message); }
  }
  async function cambiarRol(u) {
    const nuevo = u.tipo_usuario === 'CLIENTE_ADMIN' ? 'CLIENTE_CAMPO' : 'CLIENTE_ADMIN';
    try { await window.HP.api.admin.editarUsuario(u.id, { tipo_usuario: nuevo }); load(); router.toast('Rol actualizado'); }
    catch (e) { router.toast('Error: ' + e.message); }
  }
  async function resetear(u) {
    const c = window.prompt('Nueva contraseña para ' + u.nombre_usuario + ':');
    if (!c) return;
    try { await window.HP.api.admin.editarUsuario(u.id, { clave: c }); router.toast('Contraseña actualizada'); }
    catch (e) { router.toast('Error: ' + e.message); }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow={'Productor · ' + productor.nombre_comercial}
        title="Usuarios del cliente"
        sub="Crea administradores y operarios de campo. Quedan aislados al tenant de este productor."
        actions={
          <React.Fragment>
            <button className="btn ghost" onClick={onBack}>← Volver</button>
            <button className="btn primary" onClick={() => setCreating((c) => !c)}>
              {creating ? 'Cancelar' : '+ Nuevo usuario'}
            </button>
          </React.Fragment>
        }
      />

      {creating && (
        <UsuarioForm
          productorId={productor.id}
          onCreated={() => { setCreating(false); load(); router.toast('Usuario creado'); }}
          onError={(m) => router.toast(m)}
        />
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head"><h3>Usuarios de {productor.nombre_comercial}</h3></div>
        {items === null ? (
          <div className="empty">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="empty">Este productor no tiene usuarios todavía.</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Usuario</th><th>Correo</th><th>Rol</th><th>Estado</th><th></th></tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id}>
                  <td className="strong">{u.nombre_usuario}</td>
                  <td>{u.correo}</td>
                  <td><Badge tone={u.tipo_usuario === 'CLIENTE_ADMIN' ? 'olive' : 'neut'}>
                    {u.tipo_usuario === 'CLIENTE_ADMIN' ? 'Administrador' : 'Operario de campo'}
                  </Badge></td>
                  <td><Badge tone={u.activo ? 'ok' : 'neut'} dot={u.activo}>{u.activo ? 'Activo' : 'Inactivo'}</Badge></td>
                  <td className="hstack">
                    <button className="btn sm ghost" onClick={() => cambiarRol(u)}>
                      {u.tipo_usuario === 'CLIENTE_ADMIN' ? 'Hacer operario' : 'Hacer admin'}
                    </button>
                    <button className="btn sm ghost" onClick={() => toggle(u)}>{u.activo ? 'Desactivar' : 'Activar'}</button>
                    <button className="btn sm ghost" onClick={() => resetear(u)}>Resetear clave</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function UsuarioForm({ productorId, onCreated, onError }) {
  const [f, setF] = useState({ nombre_usuario: '', correo: '', clave: '', tipo_usuario: 'CLIENTE_CAMPO' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => Object.assign({}, s, { [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await window.HP.api.admin.crearUsuario({
        productor_id: productorId, nombre_usuario: f.nombre_usuario,
        correo: f.correo, clave: f.clave, tipo_usuario: f.tipo_usuario,
      });
      onCreated();
    } catch (err) { onError('Error: ' + err.message); setBusy(false); }
  }

  return (
    <form className="card card-pad" onSubmit={submit} style={{ marginTop: 16 }}>
      <div className="row-3">
        <div className="field"><label>Usuario *</label><input value={f.nombre_usuario} onChange={set('nombre_usuario')} /></div>
        <div className="field"><label>Correo *</label><input value={f.correo} onChange={set('correo')} /></div>
        <div className="field"><label>Contraseña *</label><input type="password" value={f.clave} onChange={set('clave')} /></div>
      </div>
      <div className="field" style={{ maxWidth: 260 }}>
        <label>Rol</label>
        <select value={f.tipo_usuario} onChange={set('tipo_usuario')}>
          <option value="CLIENTE_CAMPO">Operario de campo</option>
          <option value="CLIENTE_ADMIN">Administrador</option>
        </select>
      </div>
      <button className="btn primary" disabled={busy || !f.nombre_usuario || !f.correo || !f.clave}>
        {busy ? 'Creando…' : 'Crear usuario'}
      </button>
    </form>
  );
}
