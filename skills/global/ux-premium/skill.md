# Skill: UX Premium

## Obiettivo
MyCow non deve sembrare una webapp AI generata in 5 minuti. Deve sembrare una piattaforma professionale che ispira fiducia. Ogni schermata che costruisci deve passare questo test: *"Pagherei per usare questo?"*

---

## Principi Fondamentali

### 1. Meno è più potente
Ogni elemento sulla schermata deve guadagnarsi il suo spazio. Se un elemento non serve all'utente in quel momento, non c'è. Niente widget decorativi, niente statistiche inutili, niente "coming soon" visibili.

### 2. Lo stato è sempre chiaro
L'utente deve sapere sempre: cosa sta succedendo, cosa è andato bene, cosa ha bisogno di attenzione. Usa colori, icone e testi precisi. Mai ambiguità sullo stato di un agente.

### 3. Le azioni importanti sono ovvie
Il pulsante primario di ogni schermata è immediatamente riconoscibile. Non ci sono più di 2 azioni primarie per schermata.

### 4. Il feedback è immediato
Ogni azione dell'utente riceve risposta visiva entro 100ms. Loading states sempre. Mai UI che sembra bloccata.

---

## Design System

### Palette Colori
```css
/* Brand */
--color-primary: #2D6A4F;        /* verde scuro — azioni primarie */
--color-primary-light: #52B788;  /* verde medio — hover, accenti */
--color-primary-pale: #D8F3DC;   /* verde pallido — background highlight */

/* Neutrali */
--color-bg: #0F1117;             /* background principale — scuro */
--color-surface: #1A1D27;        /* card, pannelli */
--color-surface-2: #22263A;      /* surface elevato */
--color-border: #2A2D3E;         /* bordi sottili */

/* Testo */
--color-text-primary: #F0F0F0;   /* testo principale */
--color-text-secondary: #8892A4; /* testo secondario, label */
--color-text-muted: #4A5568;     /* testo disabilitato, placeholder */

/* Stato */
--color-success: #52B788;        /* agente attivo, ok */
--color-warning: #F6AD55;        /* attenzione, in esecuzione */
--color-error: #FC8181;          /* errore, fermato */
--color-info: #63B3ED;           /* informazione neutra */
```

### Tipografia
```css
/* Font stack — system fonts, zero dipendenze esterne */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
font-family-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; /* per log/codice */

/* Scale */
--text-xs: 11px;    /* label, badge, timestamp */
--text-sm: 13px;    /* testo secondario */
--text-base: 14px;  /* testo principale */
--text-md: 16px;    /* titoli card */
--text-lg: 20px;    /* titoli sezione */
--text-xl: 28px;    /* titoli pagina */
```

### Spacing
```css
/* Usa multipli di 4px */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--space-12: 48px;
```

### Border Radius
```css
--radius-sm: 6px;   /* badge, tag */
--radius-md: 10px;  /* card, input */
--radius-lg: 16px;  /* modal, pannelli grandi */
```

---

## Componenti Standard

### Card Agente
```
┌─────────────────────────────────────┐
│ 🐄 Nome Agente          ● Attivo    │
│ Ultima esecuzione: 2 min fa         │
│ Prossima: 08:00                     │
│                          [▶ Run]    │
└─────────────────────────────────────┘
```
- Border left colorato per stato (verde/giallo/rosso)
- Timestamp in formato relativo ("2 min fa", non "14:32:17")
- Una sola azione primaria visibile

### Badge Stato
```css
/* Sempre testo + colore, mai solo colore */
.badge-active   { background: #1B4D3E; color: #52B788; }
.badge-running  { background: #4A3000; color: #F6AD55; }
.badge-error    { background: #4A1010; color: #FC8181; }
.badge-idle     { background: #1E2235; color: #8892A4; }
```

### Log Viewer
- Font monospace sempre
- Timestamp a sinistra, testo a destra
- Colori per livello: info (default), warning (giallo), error (rosso)
- Auto-scroll all'ultimo log, con possibilità di bloccare lo scroll
- Niente wall of text — raggruppa per run con separatore visivo

### Input e Form
- Label sempre sopra l'input, mai placeholder come unica label
- Validation inline, non submit e poi errore
- Helper text sotto per contesto aggiuntivo
- Focus state sempre visibile (outline 2px primary)

---

## Pattern da Evitare

❌ **Gradients aggressivi** — sembrono landing page economiche  
❌ **Troppe animazioni** — distraggono, rallentano la percezione  
❌ **Icone senza label** — l'utente non deve indovinare  
❌ **Tabelle per tutto** — usa card quando i dati sono pochi  
❌ **Modal su modal** — massimo un livello di overlay  
❌ **Empty state vuoti** — sempre un messaggio utile + azione suggerita  
❌ **Testo centrato in blocchi lunghi** — solo per titoli  
❌ **Colori AI cliché** — viola, neon, gradients blu-viola  

---

## Pattern da Usare

✅ **Dark theme** — professionale, riduce affaticamento, sembra premium  
✅ **Microinterazioni sottili** — hover state, transizioni 150ms  
✅ **Whitespace generoso** — il contenuto respira  
✅ **Gerarchia visiva chiara** — l'occhio sa dove andare  
✅ **Monospace per dati tecnici** — log, ID, path, comandi  
✅ **Empty state utili** — "Nessun agente. Crea il tuo primo agente →"  
✅ **Conferma per azioni distruttive** — elimina, stop, reset  

---

## Checklist Prima di Consegnare una Schermata

- [ ] Funziona su viewport 1280px e 1920px?
- [ ] Gli stati vuoti hanno un messaggio utile?
- [ ] I loading states sono implementati?
- [ ] Le azioni distruttive hanno conferma?
- [ ] Il contrasto testo/background è sufficiente (WCAG AA)?
- [ ] Nessun elemento decorativo senza funzione?
- [ ] L'azione primaria è immediatamente riconoscibile?
