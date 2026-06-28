// HassPlan — Gestión de Fincas (CRUD). Un productor puede tener varias fincas;
// cada finca agrupa sus lotes. Backend: /api/fincas (GET/POST/PUT/DELETE).

function FincasManager() {
  const router = useRouter();
  const [items, setItems] = useState(null);
  const [editing, setEditing] = useState(null);   // null | 'new' | objeto finca

  const load = useCallback(async () => {
    try { setItems(await window.HP.api.fincas()); }
    catch (e) { router.toast('Error: ' + e.message); setItems([]); }
  }, [router]);
  useEffect(() => { load(); }, [load]);

  async function eliminar(f) {
    if (!window.confirm('¿Eliminar la finca "' + f.nombre + '"? Se borran también sus ' + f.n_lotes + ' lote(s).')) return;
    try { await window.HP.api.eliminarFinca(f.id); router.toast('Finca eliminada'); load(); }
    catch (e) { router.toast('Error: ' + e.message); }
  }

  if (editing) {
    return (
      <FincaForm
        finca={editing === 'new' ? null : editing}
        onDone={() => { setEditing(null); load(); router.toast('Finca guardada'); }}
        onCancel={() => setEditing(null)}
        toast={router.toast}
      />
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Fundo"
        title="Fincas"
        sub="Tus chacras o propiedades. Un productor puede tener varias; cada finca agrupa sus lotes."
        actions={<button className="btn primary" onClick={() => setEditing('new')}>+ Nueva finca</button>}
      />

      <div className="card">
        <div className="card-head"><h3>Mis fincas</h3></div>
        {items === null ? (
          <div className="empty">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="empty">Aún no tienes fincas. Crea la primera con “+ Nueva finca”.</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Finca</th><th>Distrito</th>
                <th className="num">Área total (ha)</th><th className="num">Lotes</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((f) => (
                <tr key={f.id}>
                  <td className="strong">{f.nombre}</td>
                  <td>{f.distrito || '—'}</td>
                  <td className="num">{f.area_total_ha != null ? f.area_total_ha : '—'}</td>
                  <td className="num">{f.n_lotes}</td>
                  <td className="hstack">
                    <button className="btn sm" onClick={() => setEditing(f)}>Editar</button>
                    <button className="btn sm ghost" onClick={() => eliminar(f)}>Eliminar</button>
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

function FincaForm({ finca, onDone, onCancel, toast }) {
  const [nombre, setNombre] = useState(finca ? finca.nombre : '');
  const [distrito, setDistrito] = useState(finca && finca.distrito ? finca.distrito : '');
  const [geometria, setGeometria] = useState(null);   // nuevo contorno dibujado (opcional)
  const [busy, setBusy] = useState(false);
  const esNueva = !finca;

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const body = { nombre: nombre.trim(), distrito: distrito.trim() };
      if (geometria) body.geometria = geometria;   // el backend deriva el centroide
      if (esNueva) await window.HP.api.crearFinca(body);
      else await window.HP.api.editarFinca(finca.id, body);
      onDone();
    } catch (err) { toast('Error: ' + err.message); setBusy(false); }
  }

  // Mostrar el contorno existente al editar.
  const lotesMapa = finca && finca.geometria
    ? [{ geometria: finca.geometria, name: finca.nombre }] : [];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Fincas"
        title={esNueva ? 'Nueva finca' : 'Editar finca'}
        sub="Define el nombre y, si quieres, dibuja el contorno en el mapa para fijar su ubicación."
        actions={<button className="btn ghost" onClick={onCancel}>← Volver</button>}
      />
      <form className="card card-pad" onSubmit={submit}>
        <div className="row-2">
          <div className="field"><label>Nombre *</label>
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="ej. Chacra La Joya" /></div>
          <div className="field"><label>Distrito / ubicación</label>
            <input value={distrito} onChange={(e) => setDistrito(e.target.value)} placeholder="ej. La Joya, Arequipa" /></div>
        </div>

        <div className="field">
          <label>Contorno de la finca (opcional)</label>
          <div className="hint" style={{ marginBottom: 8 }}>
            Usa la herramienta de polígono (arriba a la derecha del mapa) para dibujar el contorno.
            El sistema deriva el centro automáticamente.
          </div>
          <LeafletMap height={340} draw={true} lotes={lotesMapa} onPolygon={(g) => setGeometria(g)} />
          {geometria && <div className="hint" style={{ marginTop: 6 }}>✓ Nuevo contorno listo para guardar.</div>}
        </div>

        <div className="hstack" style={{ marginTop: 8 }}>
          <button type="submit" className="btn primary" disabled={busy || !nombre.trim()}>
            {busy ? 'Guardando…' : (esNueva ? 'Crear finca' : 'Guardar cambios')}
          </button>
          <button type="button" className="btn ghost" onClick={onCancel}>Cancelar</button>
        </div>
      </form>
    </div>
  );
}
