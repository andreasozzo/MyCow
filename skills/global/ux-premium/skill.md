# Skill: UX Premium

## Goal
MyCow must not look like an AI webapp generated in 5 minutes. It must look like a professional platform that inspires trust. Every screen you build must pass this test: *"Would I pay to use this?"*

---

## Core Principles

### 1. Less is more powerful
Every element on the screen must earn its space. If an element is not useful to the user at that moment, it's not there. No decorative widgets, no useless statistics, no visible "coming soon" states.

### 2. State is always clear
The user must always know: what is happening, what went well, what needs attention. Use precise colors, icons, and text. Never any ambiguity about an agent's state.

### 3. Important actions are obvious
The primary button on every screen is immediately recognizable. There are no more than 2 primary actions per screen.

### 4. Feedback is immediate
Every user action receives a visual response within 100ms. Loading states always. Never a UI that looks stuck.

---

## Design System

### Color Palette
```css
/* Brand */
--color-primary: #2D6A4F;        /* dark green — primary actions */
--color-primary-light: #52B788;  /* medium green — hover, accents */
--color-primary-pale: #D8F3DC;   /* pale green — background highlight */

/* Neutrals */
--color-bg: #0F1117;             /* main background — dark */
--color-surface: #1A1D27;        /* cards, panels */
--color-surface-2: #22263A;      /* elevated surface */
--color-border: #2A2D3E;         /* subtle borders */

/* Text */
--color-text-primary: #F0F0F0;   /* main text */
--color-text-secondary: #8892A4; /* secondary text, labels */
--color-text-muted: #4A5568;     /* disabled text, placeholders */

/* State */
--color-success: #52B788;        /* active agent, ok */
--color-warning: #F6AD55;        /* attention, running */
--color-error: #FC8181;          /* error, stopped */
--color-info: #63B3ED;           /* neutral information */
```

### Typography
```css
/* Font stack — system fonts, zero external dependencies */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
font-family-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; /* for logs/code */

/* Scale */
--text-xs: 11px;    /* labels, badges, timestamps */
--text-sm: 13px;    /* secondary text */
--text-base: 14px;  /* main text */
--text-md: 16px;    /* card titles */
--text-lg: 20px;    /* section titles */
--text-xl: 28px;    /* page titles */
```

### Spacing
```css
/* Use multiples of 4px */
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
--radius-sm: 6px;   /* badges, tags */
--radius-md: 10px;  /* cards, inputs */
--radius-lg: 16px;  /* modals, large panels */
```

---

## Standard Components

### Agent Card
```
┌─────────────────────────────────────┐
│ 🐄 Agent Name           ● Active    │
│ Last run: 2 min ago                 │
│ Next: 08:00                         │
│                          [▶ Run]    │
└─────────────────────────────────────┘
```
- Colored left border for state (green/yellow/red)
- Relative-format timestamp ("2 min ago", not "14:32:17")
- Only one visible primary action

### State Badge
```css
/* Always text + color, never color alone */
.badge-active   { background: #1B4D3E; color: #52B788; }
.badge-running  { background: #4A3000; color: #F6AD55; }
.badge-error    { background: #4A1010; color: #FC8181; }
.badge-idle     { background: #1E2235; color: #8892A4; }
```

### Log Viewer
- Always monospace font
- Timestamp on the left, text on the right
- Colors by level: info (default), warning (yellow), error (red)
- Auto-scroll to the latest log, with option to lock scroll
- No wall of text — group by run with a visual separator

### Inputs and Forms
- Label always above the input, never placeholder as the only label
- Inline validation, not submit-then-error
- Helper text below for additional context
- Focus state always visible (outline 2px primary)

---

## Patterns to Avoid

❌ **Aggressive gradients** — they look like cheap landing pages  
❌ **Too many animations** — distracting, slow perceived performance  
❌ **Icons without labels** — the user should not have to guess  
❌ **Tables for everything** — use cards when data is sparse  
❌ **Modal on modal** — maximum one overlay level  
❌ **Empty empty states** — always a useful message + suggested action  
❌ **Centered text in long blocks** — only for titles  
❌ **AI cliche colors** — purple, neon, blue-violet gradients  

---

## Patterns to Use

✅ **Dark theme** — professional, reduces eye strain, feels premium  
✅ **Subtle microinteractions** — hover states, 150ms transitions  
✅ **Generous whitespace** — content has room to breathe  
✅ **Clear visual hierarchy** — the eye knows where to go  
✅ **Monospace for technical data** — logs, IDs, paths, commands  
✅ **Useful empty states** — "No agents. Create your first agent →"  
✅ **Confirmation for destructive actions** — delete, stop, reset  

---

## Checklist Before Delivering a Screen

- [ ] Does it work on 1280px and 1920px viewports?
- [ ] Do empty states have a useful message?
- [ ] Are loading states implemented?
- [ ] Do destructive actions require confirmation?
- [ ] Is the text/background contrast sufficient (WCAG AA)?
- [ ] No decorative elements without function?
- [ ] Is the primary action immediately recognizable?
