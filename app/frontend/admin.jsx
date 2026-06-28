// HassPlan — Panel del PROVEEDOR (SUPERADMIN): productores y sus usuarios.
// Visible solo para usuarios SUPERADMIN (el sidebar filtra el grupo "Proveedor").
// Consume /api/admin/* (guardado en backend a is_superadmin).

function AdminPanel() {
  const router = useRouter();
  const [items, setItems] = useState(null);
  const [creating, setCreating] = useState(false);
  const [managing, setManaging] = useState(null);   // productor en gestión de usuarios

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

  return (
    <div className="page">
      <PageHeader
        eyebrow="Proveedor"
        title="Productores y usuarios"
        sub="Da de alta clientes (productores) y gestiona sus usuarios. Cada productor queda aislado por RLS en la base de datos."
        actions={
          <button className="btn primary" onClick={() => setCreating((c) => !c)}>
            {creating ? 'Cancelar' : '+ Nuevo productor'}
          </button>
        }
      />

      {creating && (
        <ProductorForm
          onCreated={() => { setCreating(false); load(); router.toast('Productor creado'); }}
          onError={(m) => router.toast(m)}
        />
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head"><h3>Productores registrados</h3></div>
        {items === null ? (
          <div className="empty">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="empty">Aún no hay productores. Crea el primero.</div>
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
              {items.map((p) => (
                <tr key={p.id}>
                  <td className="strong">{p.nombre_comercial}</td>
                  <td>{p.ruc_dni || '—'}</td>
                  <td>{p.correo_contacto || '—'}</td>
                  <td className="num">{p.n_usuarios}</td>
                  <td className="num">{p.n_fincas}</td>
                  <td><Badge tone={p.activo ? 'ok' : 'neut'} dot={p.activo}>{p.activo ? 'Activo' : 'Inactivo'}</Badge></td>
                  <td className="hstack">
                    <button className="btn sm" onClick={() => setManaging(p)}>Usuarios</button>
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

function ProductorForm({ onCreated, onError }) {
  const [f, setF] = useState({
    nombre_comercial: '', ruc_dni: '', correo_contacto: '', telefono: '',
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
      if (f.admin_user && f.admin_clave) {
        body.admin = { nombre_usuario: f.admin_user, correo: f.admin_correo, clave: f.admin_clave };
      }
      await window.HP.api.admin.crearProductor(body);
      onCreated();
    } catch (err) { onError('Error: ' + err.message); setBusy(false); }
  }

  return (
    <form className="card card-pad" onSubmit={submit} style={{ marginTop: 16 }}>
      <div className="row-3">
        <div className="field"><label>Nombre comercial *</label>
          <input value={f.nombre_comercial} onChange={set('nombre_comercial')} placeholder="ej. Fundo San Andrés" /></div>
        <div className="field"><label>RUC / DNI</label><input value={f.ruc_dni} onChange={set('ruc_dni')} /></div>
        <div className="field"><label>Correo de contacto</label><input value={f.correo_contacto} onChange={set('correo_contacto')} /></div>
      </div>
      <div className="divider-h"></div>
      <div className="page-eyebrow" style={{ marginBottom: 10 }}>Administrador inicial (opcional)</div>
      <div className="row-3">
        <div className="field"><label>Usuario</label><input value={f.admin_user} onChange={set('admin_user')} placeholder="ej. sanandres" /></div>
        <div className="field"><label>Correo</label><input value={f.admin_correo} onChange={set('admin_correo')} /></div>
        <div className="field"><label>Contraseña</label><input type="password" value={f.admin_clave} onChange={set('admin_clave')} /></div>
      </div>
      <button className="btn primary" disabled={busy || !f.nombre_comercial}>{busy ? 'Creando…' : 'Crear productor'}</button>
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
