// HassPlan — pantalla de login.
// Se monta cuando /api/auth/me dice que no hay sesión. Al autenticar, llama a
// onSuccess(usuario) para que el gate (app.jsx) cargue los datos del tenant.

function LoginScreen({ onSuccess }) {
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const u = await window.HP.api.login(usuario.trim(), clave);
      await onSuccess(u);           // el gate carga datos y cambia a la app
    } catch (err) {
      setError('Usuario o contraseña incorrectos.');
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <div className="brand-mark"></div>
          <div>
            <div className="brand-name" style={{ color: 'var(--ink)' }}><b>Hass</b>Plan</div>
            <div className="auth-tag">Gestión y planificación del cultivo de palta Hass</div>
          </div>
        </div>

        <h1 className="auth-title">Iniciar sesión</h1>
        <p className="auth-sub">Accede con tu usuario de productor.</p>

        <div className="field">
          <label>Usuario o correo</label>
          <input
            type="text" autoFocus autoComplete="username"
            value={usuario} onChange={(e) => setUsuario(e.target.value)}
            placeholder="p. ej. lajoya"
          />
        </div>
        <div className="field">
          <label>Contraseña</label>
          <input
            type="password" autoComplete="current-password"
            value={clave} onChange={(e) => setClave(e.target.value)}
            placeholder="••••••••"
          />
        </div>

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" className="btn primary auth-submit" disabled={busy || !usuario || !clave}>
          {busy ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
      <div className="auth-foot">Sistema multi-tenant · acceso aislado por productor</div>
    </div>
  );
}
