// HassPlan — componente de mapa Leaflet con satélite Esri.
// - Modo display: dibuja los lotes (geometría GeoJSON o punto) y centra el mapa.
// - Modo draw: deja dibujar UN polígono (Leaflet-Geoman) y lo devuelve por onPolygon(geometry).
// Reemplaza el placeholder CSS `.map-box` del prototipo.

const LAJOYA = [-16.592, -71.922];   // centro por defecto (Chacra La Joya)
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

function colorEstado(st) {
  return st === 'crit' ? '#9B2C1F' : st === 'warn' ? '#C97A21' : '#4D7C0F';
}

function LeafletMap({ height = 320, lotes = [], draw = false, onPolygon, center, flyTo }) {
  const elRef = React.useRef(null);
  const mapRef = React.useRef(null);

  // Volar a una ubicación buscada desde fuera (campo de búsqueda del formulario).
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

  return <div ref={elRef} style={{ height: height, borderRadius: 'var(--r)', overflow: 'hidden', border: '1px solid var(--border-2)' }} />;
}

window.LeafletMap = LeafletMap;
