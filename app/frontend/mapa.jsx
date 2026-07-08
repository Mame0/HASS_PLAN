// HassPlan — componente de mapa Leaflet con satélite Esri.
// - Modo display: dibuja los lotes (geometría GeoJSON o punto) y centra el mapa.
// - Modo draw: deja dibujar UN polígono (Leaflet-Geoman) y lo devuelve por onPolygon(geometry).
// - search: buscador de lugares (Nominatim) con SUGERENCIAS: escribe y elige entre varios
//   resultados para ubicarte fácil; al elegir, vuela al lugar y deja un marcador temporal.
// Reemplaza el placeholder CSS `.map-box` del prototipo.

const LAJOYA = [-16.592, -71.922];   // centro por defecto (Chacra La Joya)
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

function colorEstado(st) {
  return st === 'crit' ? '#9B2C1F' : st === 'warn' ? '#C97A21' : '#4D7C0F';
}

function LeafletMap({ height = 320, lotes = [], draw = false, onPolygon, center, flyTo, search = false }) {
  const elRef = React.useRef(null);
  const mapRef = React.useRef(null);
  const buscadoRef = React.useRef(null);   // marcador del lugar buscado (uno a la vez)
  const IconC = window.Icon;               // Icon vive en icons.jsx (window.Icon)

  // Volar a una ubicación buscada desde fuera (compatibilidad con el prop flyTo).
  React.useEffect(() => {
    if (mapRef.current && flyTo) mapRef.current.setView([flyTo[0], flyTo[1]], 16);
  }, [flyTo]);

  React.useEffect(() => {
    if (!elRef.current || mapRef.current || typeof L === 'undefined') return;
    const map = L.map(elRef.current, { zoomControl: true, attributionControl: false });
    L.tileLayer(ESRI, { maxZoom: 19 }).addTo(map);
    map.setView(center || LAJOYA, 15);
    mapRef.current = map;

    // Lotes existentes
    const group = L.featureGroup().addTo(map);
    (lotes || []).forEach((l) => {
      const color = colorEstado(l.status);
      if (l.geometria) {
        L.geoJSON(l.geometria, { style: { color: color, weight: 2, fillColor: color, fillOpacity: 0.35 } })
          .bindTooltip(l.name || l.nombre || '', { permanent: false }).addTo(group);
      } else if (l.lat != null && l.lon != null) {
        L.circleMarker([l.lat, l.lon], { radius: 8, color: color, fillColor: color, fillOpacity: 0.6 })
          .bindTooltip(l.name || l.nombre || '').addTo(group);
      }
    });
    if (group.getLayers().length) {
      try { map.fitBounds(group.getBounds(), { padding: [24, 24], maxZoom: 16 }); } catch (e) { /* sin bounds */ }
    }

    // Modo dibujo: un polígono (área auto) O un punto (centroide; área a mano).
    if (draw && map.pm) {
      map.pm.addControls({
        position: 'topright', drawPolygon: true, drawMarker: true, drawPolyline: false,
        drawCircle: false, drawCircleMarker: false, drawRectangle: false, drawText: false,
        editMode: true, dragMode: false, cutPolygon: false, rotateMode: false,
      });
      map.pm.setLang('es');
      let centroide = null;
      map.on('pm:create', (e) => {
        group.eachLayer((ly) => map.removeLayer(ly));           // solo la última geometría
        if (centroide) { map.removeLayer(centroide); centroide = null; }
        e.layer.addTo(map);
        const gj = e.layer.toGeoJSON().geometry;
        // marcar y mostrar el centroide
        const c = gj.type === 'Polygon' ? e.layer.getBounds().getCenter() : e.layer.getLatLng();
        if (c) {
          centroide = L.circleMarker(c, { radius: 5, color: '#B5530B', fillColor: '#B5530B', fillOpacity: 1 })
            .bindTooltip('centroide ' + c.lat.toFixed(4) + ', ' + c.lng.toFixed(4), { permanent: false }).addTo(map);
        }
        if (onPolygon) onPolygon(gj);
        e.layer.on('pm:edit', (ev) => onPolygon && onPolygon(ev.layer.toGeoJSON().geometry));
      });
    }

    // Leaflet necesita recalcular tamaño tras montarse dentro de un contenedor flex.
    setTimeout(() => map.invalidateSize(), 60);
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // ---- Buscador de lugares con sugerencias (Nominatim) ----
  const [q, setQ] = React.useState('');
  const [sug, setSug] = React.useState([]);
  const [abierto, setAbierto] = React.useState(false);
  const [buscando, setBuscando] = React.useState(false);

  async function buscar(texto) {
    const t = (texto == null ? q : texto).trim();
    if (t.length < 3) { setSug([]); return; }
    setBuscando(true);
    try {
      // limit=6 -> varias opciones para elegir; accept-language=es -> nombres en español.
      const url = 'https://nominatim.openstreetmap.org/search?format=json&addressdetails=1'
        + '&accept-language=es&limit=6&q=' + encodeURIComponent(t);
      const r = await fetch(url);
      const d = await r.json();
      setSug(Array.isArray(d) ? d : []);
      setAbierto(true);
    } catch (e) { setSug([]); }
    finally { setBuscando(false); }
  }

  function irA(item) {
    const map = mapRef.current;
    if (!map) return;
    const lat = +item.lat, lon = +item.lon;
    map.setView([lat, lon], 16);
    if (buscadoRef.current) map.removeLayer(buscadoRef.current);
    buscadoRef.current = L.marker([lat, lon]).addTo(map)
      .bindTooltip(item.display_name, { permanent: false });
    setQ((item.display_name || '').split(',')[0]);
    setAbierto(false);
  }

  // Autocompletar: busca solo con lo que escribe (con debounce para no saturar Nominatim).
  React.useEffect(() => {
    if (!search) return undefined;
    const id = setTimeout(() => { if (q.trim().length >= 3) buscar(q); }, 450);
    return () => clearTimeout(id);
  }, [q, search]);

  const mapDiv = <div ref={elRef} style={{ height: height, borderRadius: 'var(--r)', overflow: 'hidden', border: '1px solid var(--border-2)' }} />;
  if (!search) return mapDiv;

  return (
    <div>
      <div style={{ position: 'relative', marginBottom: 10 }}>
        <div className="hstack" style={{ background: 'var(--surface)', border: '1px solid var(--border-2)', borderRadius: 8, padding: '0 10px', height: 38, gap: 8 }}>
          {IconC && <IconC name="search" size={16} />}
          <input
            style={{ border: 0, outline: 0, background: 'transparent', height: 36, fontSize: 14, width: '100%' }}
            placeholder="Buscar lugar (ej. La Joya, Arequipa) y elige de la lista…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => { if (sug.length) setAbierto(true); }}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); buscar(q); } if (e.key === 'Escape') setAbierto(false); }} />
          <span className="mono" style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
            {buscando ? 'Buscando…' : (sug.length ? sug.length + ' resultados' : 'satélite Esri')}</span>
        </div>
        {abierto && sug.length > 0 && (
          <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 1200, marginTop: 4, background: 'var(--surface)', border: '1px solid var(--border-2)', borderRadius: 8, overflow: 'hidden', boxShadow: '0 6px 18px rgba(0,0,0,.22)', maxHeight: 240, overflowY: 'auto' }}>
            {sug.map((it) => (
              <div key={it.place_id}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => irA(it)}
                style={{ padding: '8px 10px', fontSize: 13, cursor: 'pointer', borderBottom: '1px solid var(--border)' }}>
                {it.display_name}
              </div>
            ))}
          </div>
        )}
      </div>
      {mapDiv}
    </div>
  );
}

window.LeafletMap = LeafletMap;
