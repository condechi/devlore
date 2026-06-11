'use strict';

/*
 * devlore Ingest — a single-purpose Obsidian plugin.
 *
 * It adds ingest, compile, and ask actions to the command palette, assignable
 * hotkeys, ribbon buttons, and the right-click menu for notes and folders. Each
 * action runs ONE hardcoded script — scripts/devlore.sh, scripts/compile.sh, or
 * scripts/query.sh.
 *
 * Security design (why this is safer than the Shell Commands plugin):
 *   - Every script path is hardcoded below. This plugin is NOT a general command
 *     runner, so a malicious/shared vault cannot reconfigure it to execute
 *     arbitrary commands (that is exactly how the Shell Commands plugin gets
 *     weaponized — REF6598 / PHANTOMPULSE, 2026).
 *   - It uses child_process.execFile via /bin/bash with the file path passed as a
 *     separate argv element — NO shell string is built, so filenames containing
 *     spaces or shell metacharacters cannot inject a command.
 *   - The whole plugin is ~60 lines you can read top to bottom; you own it.
 */

const { Plugin, Notice, TFolder, Modal } = require('obsidian');
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

// The only commands this plugin can ever run (both hardcoded — not a general runner).
const DEVLORE_SH = '__DEVLORE_HOME__/scripts/devlore.sh';
const COMPILE_SH = '__DEVLORE_HOME__/scripts/compile.sh';
const QUERY_SH = '__DEVLORE_HOME__/scripts/query.sh';
// Heartbeat written by scripts/compile.py while a compile is running.
const COMPILE_STATUS = '__DEVLORE_HOME__/scripts/compile.status.json';
// Unified background-activity stream (scripts/activity.py): flush/compile/ingest events.
const ACTIVITY_FILE = '__DEVLORE_HOME__/scripts/activity.jsonl';
const TIMEOUT_MS = 10 * 60 * 1000; // 10 min — compile can take a few minutes.

// Icon per event source/kind, for status bar + notices.
function eventIcon(e) {
  const key = `${e.source}:${e.kind}`;
  return {
    'flush:saved': '🧠', 'flush:error': '⚠️', 'flush:deferred': '↪️', 'flush:ok': '🧠',
    'compile:start': '⚙️', 'compile:done': '✅', 'compile:error': '⚠️',
    'ingest:doc': '📄',
    'query:start': '❓', 'query:answer': '💡', 'query:filed': '📌', 'query:error': '⚠️',
  }[key] || '•';
}
function agoStr(ts) {
  const s = Math.max(0, Math.floor((Date.now() - Date.parse(ts)) / 1000));
  if (s < 10) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// Run one of the hardcoded scripts. execFile via /bin/bash with an argv array =>
// no shell string is built, so arguments cannot inject a command.
function runScript(scriptArgs, startMsg) {
  new Notice(startMsg);
  execFile('/bin/bash', scriptArgs, { timeout: TIMEOUT_MS }, (err, stdout, stderr) => {
    if (err) {
      console.error('[devlore]', err, stderr);
      new Notice(`devlore failed: ${err.message}`, 8000);
      return;
    }
    const lastLine = (stdout || '').trim().split('\n').filter(Boolean).pop() || 'done';
    new Notice(`devlore ✓ ${lastLine}`, 8000);
  });
}

// Ask the knowledge base: a small prompt modal (question + "file the answer back"
// toggle). On submit it calls back with the typed question and the toggle state.
class AskModal extends Modal {
  constructor(app, onSubmit) {
    super(app);
    this.onSubmit = onSubmit;
    this.fileBack = false;
  }
  onOpen() {
    const { contentEl } = this;
    contentEl.createEl('h3', { text: 'Ask the devlore knowledge base' });
    const input = contentEl.createEl('input', {
      type: 'text',
      placeholder: 'Your question…',
    });
    input.style.width = '100%';
    input.style.marginBottom = '10px';

    const fbLabel = contentEl.createEl('label');
    fbLabel.style.display = 'block';
    fbLabel.style.marginBottom = '10px';
    const fb = fbLabel.createEl('input', { type: 'checkbox' });
    fbLabel.appendText(' File the answer back as a qa/ article (compounding loop)');
    fb.addEventListener('change', () => { this.fileBack = fb.checked; });

    const submit = () => {
      const q = input.value.trim();
      if (!q) return;
      this.close();
      this.onSubmit(q, this.fileBack);
    };
    const btn = contentEl.createEl('button', { text: 'Ask' });
    btn.addEventListener('click', submit);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
    input.focus();
  }
  onClose() { this.contentEl.empty(); }
}

// Show a returned answer in a scrollable, read-only modal (the answer is cited
// markdown; shown as plain text so the [[wikilinks]] stay visible).
class AnswerModal extends Modal {
  constructor(app, question, answer) {
    super(app);
    this.question = question;
    this.answer = answer;
  }
  onOpen() {
    const { contentEl } = this;
    contentEl.createEl('h3', { text: `Q: ${this.question}` });
    const pre = contentEl.createEl('pre');
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.maxHeight = '60vh';
    pre.style.overflow = 'auto';
    pre.style.userSelect = 'text';
    pre.setText(this.answer);
  }
  onClose() { this.contentEl.empty(); }
}

module.exports = class DevLorePlugin extends Plugin {
  // Vault-relative path -> absolute filesystem path.
  absPath(relPath) {
    const adapter = this.app.vault.adapter;
    if (typeof adapter.getFullPath === 'function') return adapter.getFullPath(relPath);
    if (adapter.basePath) return path.join(adapter.basePath, relPath);
    return null;
  }

  ingest(relPath) {
    const abs = this.absPath(relPath);
    if (!abs) {
      new Notice('devlore: could not resolve an absolute path for this item');
      return;
    }
    // Bridge the brief gap before compile.py writes its heartbeat.
    this._startingUntil = Date.now() + 20000;
    this.updateStatusBar();
    runScript([DEVLORE_SH, abs], `devlore: ingesting ${abs.split('/').pop()}…`);
  }

  // Manual compile only (no ingest) — compiles any pending daily logs.
  compileNow() {
    this._startingUntil = Date.now() + 20000;
    this.updateStatusBar();
    runScript([COMPILE_SH], 'devlore: compiling knowledge base…');
  }

  // Open the ask prompt, then run query.sh and show the answer in a modal.
  askQuery() {
    new AskModal(this.app, (question, fileBack) => {
      const args = [QUERY_SH, question];
      if (fileBack) args.push('--file-back');
      new Notice(`devlore: asking "${question.slice(0, 50)}"…`);
      execFile('/bin/bash', args, { timeout: TIMEOUT_MS }, (err, stdout, stderr) => {
        if (err) {
          console.error('[devlore]', err, stderr);
          new Notice(`devlore query failed: ${err.message}`, 8000);
          return;
        }
        const answer = (stdout || '').trim() || '(no answer produced)';
        new AnswerModal(this.app, question, answer).open();
      });
    }).open();
  }

  pidAlive(pid) {
    try {
      process.kill(pid, 0);
      return true;
    } catch (e) {
      return e && e.code === 'EPERM'; // exists but not signalable => still alive
    }
  }

  // The detail home: a roomy, always-visible status-bar item (the CC status line
  // is cramped/truncated inside the realclaudian pane). Shows live compile detail,
  // a brief done-confirmation, and is click-through to knowledge/log.md.
  updateStatusBar() {
    // Persistent baseline so the item is ALWAYS visible (an empty status-bar
    // item is invisible) and the click-through to the log is always available.
    let text = '🧠 devlore';
    try {
      const data = JSON.parse(fs.readFileSync(COMPILE_STATUS, 'utf8'));
      if (data.state === 'running' && data.pid && this.pidAlive(data.pid)) {
        const where = data.index && data.total ? ` ${data.index}/${data.total}` : '';
        const f = data.file ? ` — ${data.file}` : '';
        const part = data.chunk && data.chunks > 1 ? ` (part ${data.chunk}/${data.chunks})` : '';
        text = `⚙ devlore: compiling${where}${f}${part}…`;
      }
    } catch (e) {
      /* missing/invalid heartbeat => keep the baseline */
    }
    // Starting bridge (right after a trigger, before the heartbeat appears).
    if (this._startingUntil && Date.now() < this._startingUntil && !text.startsWith('⚙')) {
      text = '⚙ devlore: starting…';
    }
    // Otherwise, show the most recent background event (flush/compile/ingest) if
    // it's recent — turning the status bar into a live activity feed.
    if (text === '🧠 devlore' && this._lastEvent &&
        Date.now() - Date.parse(this._lastEvent.ts) < 5 * 60 * 1000) {
      const e = this._lastEvent;
      text = `${eventIcon(e)} ${e.msg} · ${agoStr(e.ts)}`;
    }
    if (this.statusBar) this.statusBar.setText(text);
  }

  // Read the tail of the activity stream as parsed events.
  readActivity() {
    try {
      const lines = fs.readFileSync(ACTIVITY_FILE, 'utf8').trim().split('\n');
      return lines.slice(-80).map((l) => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean);
    } catch (e) {
      return [];
    }
  }

  // Poll for NEW background events; toast each and remember the latest.
  pollActivity() {
    const events = this.readActivity();
    if (!events.length) return;
    const fresh = events.filter((e) => e.ts > this._lastActivityTs);
    for (const e of fresh) {
      this._lastEvent = e;
      if (e.kind === 'ok') continue; // "nothing to save" is noise — status bar only
      new Notice(`${eventIcon(e)} devlore — ${e.msg}`, e.level === 'error' ? 9000 : 5000);
    }
    this._lastActivityTs = events[events.length - 1].ts;
  }

  // Open the build log (the full compile + supersede history) in a new pane.
  openLog() {
    const file = this.app.vault.getAbstractFileByPath('knowledge/log.md');
    if (file) this.app.workspace.getLeaf(true).openFile(file);
    else new Notice('devlore: knowledge/log.md not found in this vault');
  }

  async onload() {
    this.statusBar = this.addStatusBarItem();
    this.statusBar.setAttribute('aria-label', 'Open devlore build log');
    this.statusBar.style.cursor = 'pointer';
    this.statusBar.addEventListener('click', () => this.openLog());

    // Don't replay history: start from the newest event already on disk.
    const existing = this.readActivity();
    this._lastActivityTs = existing.length ? existing[existing.length - 1].ts : '';
    this._lastEvent = existing.length ? existing[existing.length - 1] : null;

    this.updateStatusBar();
    // One tick: poll the activity stream (toasts + latest) AND the compile
    // heartbeat (live progress) — covers events from ANY source (plugin,
    // /devlore, and the background flush/compile hooks).
    this.registerInterval(window.setInterval(() => { this.pollActivity(); this.updateStatusBar(); }, 2000));

    // Command palette entry + assignable hotkey: ingest the active note.
    this.addCommand({
      id: 'ingest-active-note',
      name: 'Ingest active note to devlore',
      checkCallback: (checking) => {
        const file = this.app.workspace.getActiveFile();
        if (!file) return false;
        if (!checking) this.ingest(file.path);
        return true;
      },
    });

    // Command palette entry + assignable hotkey: manual compile (no ingest).
    this.addCommand({
      id: 'compile-knowledge-base',
      name: 'Compile knowledge base now',
      callback: () => this.compileNow(),
    });

    // Command palette entry + assignable hotkey: ask the knowledge base.
    this.addCommand({
      id: 'ask-knowledge-base',
      name: 'Ask the devlore knowledge base',
      callback: () => this.askQuery(),
    });

    // Left-ribbon button for one-click manual compile.
    this.addRibbonIcon('refresh-cw', 'Compile devlore knowledge base', () => this.compileNow());

    // Left-ribbon button to ask the knowledge base.
    this.addRibbonIcon('help-circle', 'Ask the devlore knowledge base', () => this.askQuery());

    // Right-click on a note or folder in the file explorer.
    this.registerEvent(
      this.app.workspace.on('file-menu', (menu, item) => {
        const isFolder = item instanceof TFolder;
        menu.addItem((mi) =>
          mi
            .setTitle(isFolder ? 'Ingest folder to devlore' : 'Ingest to devlore')
            .setIcon('brain')
            .onClick(() => this.ingest(item.path))
        );
      })
    );

    // Right-click inside an open note.
    this.registerEvent(
      this.app.workspace.on('editor-menu', (menu, _editor, view) => {
        const file = view && view.file;
        if (!file) return;
        menu.addItem((mi) =>
          mi.setTitle('Ingest to devlore').setIcon('brain').onClick(() => this.ingest(file.path))
        );
      })
    );
  }
};
