// HassPlan — minimal stroke icon set
const Icon = ({ name, size = 16, stroke = 1.6 }) => {
  const s = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round' };
  switch (name) {
    case 'dashboard': return (
      <svg {...s}><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>
    );
    case 'campaign': return (
      <svg {...s}><path d="M4 5a2 2 0 0 1 2-2h8l4 4v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5Z"/><path d="M14 3v4h4"/><path d="M8 13h7M8 17h5"/></svg>
    );
    case 'sectors': return (
      <svg {...s}><path d="M3 7l9-4 9 4-9 4-9-4Z"/><path d="M3 12l9 4 9-4"/><path d="M3 17l9 4 9-4"/></svg>
    );
    case 'brain': return (
      <svg {...s}><path d="M8 4a3 3 0 0 0-3 3v2a3 3 0 0 0-1 5.5A3 3 0 0 0 8 20h0a3 3 0 0 0 3-3V4Z"/><path d="M16 4a3 3 0 0 1 3 3v2a3 3 0 0 1 1 5.5A3 3 0 0 1 16 20h0a3 3 0 0 1-3-3V4Z"/></svg>
    );
    case 'harvest': return (
      <svg {...s}><path d="M12 21V11"/><path d="M12 11c0-4 3-7 7-7-.4 4-3 7-7 7Z"/><path d="M12 11c0-4-3-7-7-7 .4 4 3 7 7 7Z"/></svg>
    );
    case 'workers': return (
      <svg {...s}><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="10" r="2.4"/><path d="M14 20c0-2.4 1.6-4 3-4s3 1.6 3 4"/></svg>
    );
    case 'crate': return (
      <svg {...s}><path d="M3 7h18l-2 13H5L3 7Z"/><path d="M8 7l1-3h6l1 3"/><path d="M9 12h6"/></svg>
    );
    case 'truck': return (
      <svg {...s}><path d="M3 6h11v9H3z"/><path d="M14 9h4l3 3v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>
    );
    case 'bell': return (
      <svg {...s}><path d="M6 8a6 6 0 0 1 12 0v5l1.5 3h-15L6 13V8Z"/><path d="M10 19a2 2 0 0 0 4 0"/></svg>
    );
    case 'cog': return (
      <svg {...s}><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.2-1.6l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2.7-1.6L13.2 2h-2.4l-.6 2.8a7 7 0 0 0-2.7 1.6l-2.3-.9-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .5.1 1.1.2 1.6l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2.7 1.6l.6 2.8h2.4l.6-2.8a7 7 0 0 0 2.7-1.6l2.3.9 2-3.4-2-1.5c.1-.5.2-1.1.2-1.6Z"/></svg>
    );
    case 'plus': return (<svg {...s}><path d="M12 5v14M5 12h14"/></svg>);
    case 'chev':  return (<svg {...s}><path d="M9 6l6 6-6 6"/></svg>);
    case 'down':  return (<svg {...s}><path d="M6 9l6 6 6-6"/></svg>);
    case 'check': return (<svg {...s}><path d="M5 12l4.5 4.5L19 7"/></svg>);
    case 'x':     return (<svg {...s}><path d="M6 6l12 12M18 6L6 18"/></svg>);
    case 'play':  return (<svg {...s}><path d="M7 5l12 7-12 7V5Z"/></svg>);
    case 'edit':  return (<svg {...s}><path d="M14 4l6 6L9 21H3v-6L14 4Z"/></svg>);
    case 'trash': return (<svg {...s}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/></svg>);
    case 'eye':   return (<svg {...s}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>);
    case 'search':return (<svg {...s}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>);
    case 'filter':return (<svg {...s}><path d="M4 5h16l-6 8v6l-4-2v-4L4 5Z"/></svg>);
    case 'calendar': return (<svg {...s}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>);
    case 'map':   return (<svg {...s}><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z"/><path d="M9 4v14M15 6v14"/></svg>);
    case 'drop':  return (<svg {...s}><path d="M12 3s-6 7-6 11a6 6 0 0 0 12 0c0-4-6-11-6-11Z"/></svg>);
    case 'sun':   return (<svg {...s}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/></svg>);
    case 'leaf':  return (<svg {...s}><path d="M4 20c8 0 16-4 16-16 0 0-12 0-14 6S4 20 4 20Z"/><path d="M4 20c4-8 8-12 16-16"/></svg>);
    case 'arrow-up':   return (<svg {...s}><path d="M12 19V5M5 12l7-7 7 7"/></svg>);
    case 'arrow-down': return (<svg {...s}><path d="M12 5v14M19 12l-7 7-7-7"/></svg>);
    case 'log-out': return (<svg {...s}><path d="M10 17l-5-5 5-5"/><path d="M5 12h12"/><path d="M14 5h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4"/></svg>);
    case 'chat':  return (<svg {...s}><path d="M21 12a8 8 0 1 1-3.5-6.6L21 5l-1 4.5A8 8 0 0 1 21 12Z"/></svg>);
    case 'cloud': return (<svg {...s}><path d="M7 18a4 4 0 0 1-1-7.9 6 6 0 0 1 11.6 1.4A4 4 0 0 1 17 18H7Z"/></svg>);
    case 'wifi':  return (<svg {...s}><path d="M5 12a10 10 0 0 1 14 0"/><path d="M8.5 15.5a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1"/></svg>);
    case 'refresh': return (<svg {...s}><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/></svg>);
    case 'link':  return (<svg {...s}><path d="M10 14a4 4 0 0 0 5.6 0l3-3a4 4 0 0 0-5.6-5.6L11 7"/><path d="M14 10a4 4 0 0 0-5.6 0l-3 3a4 4 0 0 0 5.6 5.6L13 17"/></svg>);
    case 'sat':   return (<svg {...s}><path d="M5 19l3-3M16 8l3-3M9 9l2 2M13 13l2 2"/><rect x="3" y="14" width="7" height="7" rx="1" transform="rotate(-45 6.5 17.5)"/><rect x="14" y="3" width="7" height="7" rx="1" transform="rotate(-45 17.5 6.5)"/></svg>);
    default: return <svg {...s}><circle cx="12" cy="12" r="9"/></svg>;
  }
};

window.Icon = Icon;
