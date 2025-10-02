import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import clsx from 'clsx';
import './App.css';
import './index.css';
import {
  fetchDiagnostics,
  fetchMotd,
  fetchUploadText,
  fetchUploads,
  fetchFSList,
  fetchFileText,
  formatBytes,
  renameUpload,
  runUploadCommand,
  saveUploadText,
  updateMotd,
  uploadFiles,
  deleteUpload,
} from './api';
import type { Diagnostics, UploadItem, UploadCommandResponse, FSListItem } from './api';
import { useToasts } from './hooks';

const SAMPLE_MARKDOWN = `# Fresh Playbook

Welcome to the dojo dashboard. Use this canvas to sketch plans, ship notes, or stash snippets.

- [x] sync uploads
- [ ] cut a new release
- [ ] brag to the squad about this UI
`;

const AUTO_REFRESH_INTERVAL = 30_000;

function App() {
  const { toasts, pushToast, dismissToast } = useToasts();
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [isLoadingUploads, setIsLoadingUploads] = useState(false);
  const [selectedFile, setSelectedFile] = useState('create.md');
  const [editorValue, setEditorValue] = useState('');
  const [isEditorDirty, setIsEditorDirty] = useState(false);
  const [isSavingFile, setIsSavingFile] = useState(false);
  const [motdDraft, setMotdDraft] = useState('');
  const [motdUpdatedAt, setMotdUpdatedAt] = useState<string | null>(null);
  const [isSavingMotd, setIsSavingMotd] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [isLoadingDiagnostics, setIsLoadingDiagnostics] = useState(false);
  const [commandInput, setCommandInput] = useState('ls');
  const [terminalLines, setTerminalLines] = useState<string[]>(['DebtCoder Dojo terminal ready. Type `ls` to see uploads.']);
  const [isRunningCommand, setIsRunningCommand] = useState(false);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const historyCursorRef = useRef<number | null>(null);
  const [selectedDirectory, setSelectedDirectory] = useState<string>('');
  const [directoryUploads, setDirectoryUploads] = useState<UploadItem[]>([]);
  const [isLoadingDirectory, setIsLoadingDirectory] = useState(false);
  const [directoryCatalog, setDirectoryCatalog] = useState<string[]>([]);
  const [copyFeedbackId, setCopyFeedbackId] = useState<string | null>(null);
  const [profileMarkdown, setProfileMarkdown] = useState<string | null>(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);

  const appendTerminal = useCallback((lines: string[]) => {
    setTerminalLines((current) => {
      const next = [...current, ...lines];
      return next.slice(-400);
    });
  }, []);

  const registerDirectories = useCallback((items: FSListItem[]) => {
    if (!items?.length) return;
    setDirectoryCatalog((current) => {
      const next = new Set(current);
      items.forEach((item) => {
        if (item.is_dir) {
          next.add(item.path);
        }
      });
      return Array.from(next).sort((a, b) => a.localeCompare(b));
    });
  }, []);

  const refreshDirectory = useCallback(
    async (directory: string) => {
      if (!directory) {
        setDirectoryUploads([]);
        return;
      }
      setIsLoadingDirectory(true);
      try {
        const items = await fetchFSList(directory);
        registerDirectories(items);
        const files = items.filter((item) => !item.is_dir);
        setDirectoryUploads(
          files.map((item) => ({
            filename: item.path,
            size_bytes: typeof item.size_bytes === 'number' ? item.size_bytes : 0,
            modified_at: item.modified_at,
          }))
        );
      } catch (error) {
        console.error(error);
        setDirectoryUploads([]);
        pushToast({ title: `Failed to load ${directory}`, detail: String(error), tone: 'error' });
      } finally {
        setIsLoadingDirectory(false);
      }
    },
    [registerDirectories, pushToast]
  );

  const refreshUploads = useCallback(async () => {
    try {
      setIsLoadingUploads(true);
      const data = await fetchUploads();
      setUploads(data);
      try {
        const fsItems = await fetchFSList();
        registerDirectories(fsItems);
      } catch (error) {
        console.error('Failed to load directory index', error);
      }
      if (selectedDirectory) {
        await refreshDirectory(selectedDirectory);
      }
    } catch (error) {
      console.error(error);
      pushToast({ title: 'Failed to load uploads', detail: String(error), tone: 'error' });
    } finally {
      setIsLoadingUploads(false);
    }
  }, [pushToast, registerDirectories, refreshDirectory, selectedDirectory]);

  const refreshDiagnostics = useCallback(async () => {
    try {
      setIsLoadingDiagnostics(true);
      const data = await fetchDiagnostics();
      setDiagnostics(data);
      if (data.motd_last_modified) {
        setMotdUpdatedAt(data.motd_last_modified);
      }
    } catch (error) {
      console.error(error);
      pushToast({ title: 'Diagnostics fetch failed', detail: String(error), tone: 'error' });
    } finally {
      setIsLoadingDiagnostics(false);
    }
  }, [pushToast]);

  const loadMotd = useCallback(async () => {
    try {
      const value = await fetchMotd();
      setMotdDraft(value);
    } catch (error) {
      console.error(error);
      pushToast({ title: 'Unable to load MOTD', detail: String(error), tone: 'error' });
    }
  }, [pushToast]);

  const bootstrap = useCallback(async () => {
    await Promise.all([refreshUploads(), refreshDiagnostics(), loadMotd()]);
  }, [refreshUploads, refreshDiagnostics, loadMotd]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (!autoRefreshEnabled) return;
    const timer = window.setInterval(() => {
      refreshUploads();
      refreshDiagnostics();
    }, AUTO_REFRESH_INTERVAL);
    return () => window.clearInterval(timer);
  }, [autoRefreshEnabled, refreshUploads, refreshDiagnostics]);

  useEffect(() => {
    if (!selectedDirectory) {
      setDirectoryUploads([]);
      setIsLoadingDirectory(false);
      return;
    }
    refreshDirectory(selectedDirectory);
  }, [selectedDirectory, refreshDirectory]);

  useEffect(() => {
    if (!selectedDirectory) return;
    setDirectoryCatalog((current) => {
      if (current.includes(selectedDirectory)) {
        return current;
      }
      return [...current, selectedDirectory].sort((a, b) => a.localeCompare(b));
    });
  }, [selectedDirectory]);

  const loadFileIntoEditor = useCallback(
    async (filename: string) => {
      try {
        const content = await fetchUploadText(filename);
        setSelectedFile(filename);
        setEditorValue(content);
        setIsEditorDirty(false);
        pushToast({ title: `Loaded ${filename}` });
      } catch (error) {
        console.error(error);
        pushToast({ title: `Unable to load ${filename}`, detail: String(error), tone: 'error' });
      }
    },
    [pushToast]
  );

  const handleFileDelete = useCallback(
    async (filename: string) => {
      if (!window.confirm(`Delete ${filename}?`)) return;
      try {
        await deleteUpload(filename);
        pushToast({ title: `Deleted ${filename}` });
        refreshUploads();
      } catch (error) {
        console.error(error);
        pushToast({ title: `Failed to delete ${filename}`, detail: String(error), tone: 'error' });
      }
    },
    [pushToast, refreshUploads]
  );

  const handleUpload = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      try {
        const summaries = await uploadFiles(files);
        pushToast({ title: `Uploaded ${summaries.length} file${summaries.length > 1 ? 's' : ''}` });
        refreshUploads();
      } catch (error) {
        console.error(error);
        pushToast({ title: 'Upload failed', detail: String(error), tone: 'error' });
      }
    },
    [pushToast, refreshUploads]
  );

  const handleFileSave = useCallback(async () => {
    if (!selectedFile) {
      pushToast({ title: 'Choose a file name before saving', tone: 'error' });
      return;
    }
    try {
      setIsSavingFile(true);
      const summary = await saveUploadText(selectedFile, editorValue);
      setIsEditorDirty(false);
      pushToast({ title: `Saved ${summary.filename}`, detail: `${formatBytes(summary.bytes_written)} written` });
      refreshUploads();
    } catch (error) {
      console.error(error);
      pushToast({ title: `Save failed (${selectedFile})`, detail: String(error), tone: 'error' });
    } finally {
      setIsSavingFile(false);
    }
  }, [selectedFile, editorValue, pushToast, refreshUploads]);

  const handleMotdSave = useCallback(async () => {
    try {
      setIsSavingMotd(true);
      const result = await updateMotd(motdDraft);
      setMotdUpdatedAt(result.updated_at);
      pushToast({ title: 'MOTD updated', detail: `${formatBytes(result.bytes_written)} written` });
    } catch (error) {
      console.error(error);
      pushToast({ title: 'Failed to update MOTD', detail: String(error), tone: 'error' });
    } finally {
      setIsSavingMotd(false);
    }
  }, [motdDraft, pushToast]);

  const handleCopyPath = useCallback(
    (path: string) => {
      if (!navigator?.clipboard) {
        pushToast({ title: 'Clipboard unsupported', tone: 'error' });
        return;
      }
      navigator.clipboard
        .writeText(path)
        .then(() => {
          setCopyFeedbackId(path);
          window.setTimeout(() => {
            setCopyFeedbackId((current) => (current === path ? null : current));
          }, 1500);
        })
        .catch((error) => {
          console.error(error);
          pushToast({ title: 'Unable to copy path', detail: String(error), tone: 'error' });
        });
    },
    [pushToast]
  );

  const handleRunCommand = useCallback(
    async (command: string) => {
      const trimmed = command.trim();
      if (!trimmed) return;
      setIsRunningCommand(true);
      appendTerminal([`dojo> ${trimmed}`]);
      try {
        const response: UploadCommandResponse = await runUploadCommand(trimmed);
        if (response.error) {
          appendTerminal([`⚠️ ${response.error}`]);
        } else if (response.output.length > 0) {
          appendTerminal(response.output);
        } else {
          appendTerminal(['(no output)']);
        }
        setCommandHistory((history) => [trimmed, ...history].slice(0, 50));
        historyCursorRef.current = null;
      } catch (error) {
        console.error(error);
        appendTerminal([`✖ ${String(error)}`]);
      } finally {
        setIsRunningCommand(false);
      }
    },
    [appendTerminal]
  );

  const handleRename = useCallback(
    async (filename: string) => {
      const target = window.prompt('Rename to?', filename);
      if (!target || target === filename) return;
      try {
        await renameUpload(filename, target);
        pushToast({ title: `Renamed to ${target}` });
        refreshUploads();
        if (selectedFile === filename) {
          setSelectedFile(target);
        }
      } catch (error) {
        console.error(error);
        pushToast({ title: 'Rename failed', detail: String(error), tone: 'error' });
      }
    },
    [pushToast, refreshUploads, selectedFile]
  );

  const handleCommandSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      handleRunCommand(commandInput);
      setCommandInput('');
    },
    [commandInput, handleRunCommand]
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        const currentIndex = historyCursorRef.current;
        const nextIndex = currentIndex === null ? 0 : Math.min(currentIndex + 1, commandHistory.length - 1);
        const command = commandHistory[nextIndex];
        if (command) setCommandInput(command);
        historyCursorRef.current = nextIndex;
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        const currentIndex = historyCursorRef.current;
        if (currentIndex === null) return;
        const nextIndex = currentIndex - 1;
        if (nextIndex < 0) {
          setCommandInput('');
          historyCursorRef.current = null;
          return;
        }
        const command = commandHistory[nextIndex];
        if (command) setCommandInput(command);
        historyCursorRef.current = nextIndex;
      }
    },
    [commandHistory]
  );

  const motdCharCount = motdDraft.length;

  const directoryOptions = useMemo(
    () => directoryCatalog.slice().sort((a, b) => a.localeCompare(b)),
    [directoryCatalog]
  );

  const currentUploads = selectedDirectory ? directoryUploads : uploads;
  const isLoadingCurrentUploads = selectedDirectory ? isLoadingDirectory : isLoadingUploads;

  const currentDirectoryStats = useMemo(() => {
    if (currentUploads.length === 0) {
      return { count: 0, bytes: 0 };
    }
    const bytes = currentUploads.reduce((total, item) => total + item.size_bytes, 0);
    return { count: currentUploads.length, bytes };
  }, [currentUploads]);

  const quickStats = useMemo(() => {
    if (!diagnostics) return [];
    return [
      { label: 'Uptime', value: `${(diagnostics.uptime_seconds / 3600).toFixed(1)} h` },
      { label: 'Uploads', value: diagnostics.upload_file_count.toString() },
      { label: 'Disk Used', value: formatBytes(diagnostics.upload_disk_usage_bytes) },
      { label: 'DuckDuckGo', value: diagnostics.duckduckgo_ready ? 'online' : 'degraded' },
    ];
  }, [diagnostics]);

  const handleTemplate = useCallback(() => {
    const target = selectedDirectory ? `${selectedDirectory}/create.md` : 'create.md';
    setSelectedFile(target);
    setEditorValue(SAMPLE_MARKDOWN);
    setIsEditorDirty(true);
    pushToast({ title: 'Template loaded', detail: `Ready to edit ${target}` });
  }, [pushToast, selectedDirectory]);

  useEffect(() => {
    const profileTarget = selectedDirectory ? `${selectedDirectory}/profile.md` : 'profile.md';
    const hasProfile = currentUploads.some((item) => item.filename === profileTarget);
    if (!hasProfile) {
      setProfileMarkdown(null);
      setIsLoadingProfile(false);
      return;
    }
    setIsLoadingProfile(true);
    fetchFileText(profileTarget)
      .then((content) => {
        setProfileMarkdown(content);
      })
      .catch((error) => {
        console.error(error);
        setProfileMarkdown(null);
        pushToast({ title: 'Failed to load profile.md', detail: String(error), tone: 'error' });
      })
      .finally(() => setIsLoadingProfile(false));
  }, [selectedDirectory, currentUploads, pushToast]);

  return (
    <div className="app-shell">
      <header className="card app-frame__full" style={{ maxWidth: '1200px', marginBottom: '24px' }}>
        <div className="card__title">DebtCoder Ops Cockpit <span>api.debtcodersdoja.com</span></div>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div className="auto-refresh-toggle">
            <input
              type="checkbox"
              id="auto-refresh"
              checked={autoRefreshEnabled}
              onChange={(event) => setAutoRefreshEnabled(event.target.checked)}
            />
            <label htmlFor="auto-refresh">Auto refresh ({AUTO_REFRESH_INTERVAL / 1000}s)</label>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button className="button button--ghost" onClick={() => refreshUploads()} disabled={isLoadingUploads}>
              Refresh uploads
            </button>
            <button className="button button--ghost" onClick={() => refreshDiagnostics()} disabled={isLoadingDiagnostics}>
              Refresh diagnostics
            </button>
            <label className="button" style={{ cursor: 'pointer' }}>
              Upload files
              <input type="file" multiple style={{ display: 'none' }} onChange={(event) => handleUpload(event.target.files)} />
            </label>
            <button className="button" onClick={handleTemplate}>
              Load Markdown template
            </button>
            <button className="button button--ghost" onClick={() => window.open('https://api.debtcodersdoja.com/docs', '_blank')}>
              Open Swagger
            </button>
          </div>
        </div>
      </header>

      <div className="app-frame">
        <section className="card">
        <div className="card__title">Uploads <span>{uploads.length} tracked</span></div>
        <div className="section-grid" style={{ gridTemplateColumns: 'minmax(0, 1fr)' }}>
          <div className="field">
            <label htmlFor="directory-select">Directory</label>
            <select
              id="directory-select"
              className="text-input"
              value={selectedDirectory}
              onChange={(event) => setSelectedDirectory(event.target.value)}
            >
              <option value="">All uploads</option>
              {directoryOptions.map((dir) => (
                <option key={dir} value={dir}>
                  {dir}
                </option>
              ))}
            </select>
          </div>
          <div className="directory-summary" role="presentation">
            <span className="directory-summary__label">Files</span>
            <span className="directory-summary__value">{currentDirectoryStats.count}</span>
            <span className="directory-summary__label">Bytes</span>
            <span className="directory-summary__value">{formatBytes(currentDirectoryStats.bytes)}</span>
          </div>
        </div>
        {(profileMarkdown || isLoadingProfile) && (
          <div className="profile-card">
            <div className="profile-card__header">
              <span className="profile-card__badge">Profile</span>
              <span className="profile-card__dir">{selectedDirectory || 'root'}</span>
            </div>
            <div className="profile-card__body">
              {isLoadingProfile ? <div>Loading profile…</div> : <ReactMarkdown>{profileMarkdown ?? ''}</ReactMarkdown>}
            </div>
          </div>
        )}
        <div className="upload-table" role="table" aria-label="Uploads">
          <div className="upload-header" role="row">
            <span role="columnheader">Filename</span>
            <span role="columnheader">Size</span>
            <span role="columnheader">Modified</span>
            <span role="columnheader" className="upload-header__actions">Actions</span>
          </div>
          {isLoadingCurrentUploads && (
            <div className="upload-row upload-row--status" role="row">
              <span role="cell">Loading {selectedDirectory ? `${selectedDirectory}…` : 'uploads…'}</span>
            </div>
          )}
          {!isLoadingCurrentUploads && currentUploads.length === 0 && (
            <div className="upload-row upload-row--status" role="row">
              <span role="cell">
                {selectedDirectory
                  ? `No files yet inside ${selectedDirectory}. Drop one with the uploader or run touch via the terminal.`
                  : 'No uploads yet. Drop a file or run `touch` in the terminal.'}
              </span>
            </div>
          )}
          {currentUploads.map((item) => (
            <div key={item.filename} className="upload-item" role="row">
              <div className="upload-item__name" role="cell">
                <span className="upload-item__path">{item.filename}</span>
                <button
                  type="button"
                  className="button button--ghost button--mini"
                  onClick={() => handleCopyPath(item.filename)}
                  aria-label={`Copy path for ${item.filename}`}
                >
                  {copyFeedbackId === item.filename ? 'Copied' : 'Copy'}
                </button>
              </div>
              <div role="cell">{formatBytes(item.size_bytes)}</div>
              <div role="cell">{new Date(item.modified_at).toLocaleString()}</div>
              <div className="upload-actions" role="cell">
                <button className="button button--ghost" onClick={() => loadFileIntoEditor(item.filename)}>
                  Edit
                </button>
                <button className="button button--ghost" onClick={() => handleRename(item.filename)}>
                  Rename
                </button>
                <button
                  className="button button--ghost"
                  onClick={() =>
                    window.open(
                      `${import.meta.env.VITE_API_BASE ?? 'https://api.debtcodersdoja.com'}/upload/${encodeURIComponent(item.filename)}`,
                      '_blank'
                    )
                  }
                >
                  Download
                </button>
                <button className="button button--ghost" onClick={() => handleFileDelete(item.filename)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
        </section>

        <section className="card">
          <div className="card__title">MOTD Control <span>{motdCharCount} chars</span></div>
          <div className="field">
            <label htmlFor="motd">Message of the day</label>
            <textarea
              id="motd"
              className="text-area"
              value={motdDraft}
              onChange={(event) => setMotdDraft(event.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button className="button" onClick={handleMotdSave} disabled={isSavingMotd}>
              Save MOTD
            </button>
            <button className="button button--ghost" onClick={loadMotd}>
              Reset
            </button>
            {motdUpdatedAt && <span style={{ fontSize: '0.8rem', opacity: 0.65 }}>Last updated {new Date(motdUpdatedAt).toLocaleString()}</span>}
          </div>
        </section>

        <section className="card app-frame__full">
          <div className="card__title">Markdown Lab <span>{selectedFile}</span></div>
          <div className="section-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
            <div className="field">
              <label htmlFor="filename">Filename</label>
              <input
                id="filename"
                className="text-input"
                value={selectedFile}
                onChange={(event) => {
                  setSelectedFile(event.target.value);
                  setIsEditorDirty(true);
                }}
                placeholder="create.md"
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
              <button className="button" onClick={handleFileSave} disabled={isSavingFile}>
                {isSavingFile ? 'Saving…' : 'Save file'}
              </button>
              <button className="button button--ghost" onClick={() => loadFileIntoEditor(selectedFile)}>
                Load file
              </button>
            </div>
          </div>
          <div className="field">
            <label htmlFor="editor">Markdown source</label>
            <textarea
              id="editor"
              className="text-area"
              value={editorValue}
              onChange={(event) => {
                setEditorValue(event.target.value);
                setIsEditorDirty(true);
              }}
            />
          </div>
          <div className="field">
            <label>Preview</label>
            <div className="markdown-preview">
              <ReactMarkdown>{editorValue}</ReactMarkdown>
            </div>
          </div>
          {isEditorDirty && <span style={{ fontSize: '0.8rem', color: 'var(--xanthous)' }}>Unsaved changes</span>}
        </section>

        <section className="card">
          <div className="card__title">Terminal <span>uploads shell</span></div>
          <div className="terminal">
            <div className="terminal__output">
              {terminalLines.map((line, index) => (
                <div key={index}>{line}</div>
              ))}
            </div>
            <form className="terminal__input" onSubmit={handleCommandSubmit}>
              <input
                className="text-input"
                value={commandInput}
                placeholder="ls | cat create.md | touch notes.txt"
                onChange={(event) => setCommandInput(event.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button className="button" type="submit" disabled={isRunningCommand}>
                Run
              </button>
            </form>
          </div>
          <small style={{ opacity: 0.7 }}>Commands: ls · cat &lt;file&gt; · rm &lt;file&gt; · touch &lt;file&gt; · mv &lt;src&gt; &lt;dest&gt;</small>
        </section>

        <section className="card">
          <div className="card__title">Diagnostics <span>{diagnostics ? diagnostics.status : 'loading…'}</span></div>
          {diagnostics ? (
            <div className="metrics-grid">
              {quickStats.map((metric) => (
                <div key={metric.label} className="metric-card">
                  <span className="metric-card__label">{metric.label}</span>
                  <span className="metric-card__value">{metric.value}</span>
                </div>
              ))}
              <div className="metric-card">
                <span className="metric-card__label">Python</span>
                <span className="metric-card__value">{diagnostics.python_version}</span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">Upload dir</span>
                <span className="metric-card__value" style={{ fontSize: '0.75rem' }}>{diagnostics.upload_dir}</span>
              </div>
            </div>
          ) : (
            <div>Loading diagnostics…</div>
          )}
        </section>
      </div>

      <div className="toast-stack">
        {toasts.map((toast) => (
          <div key={toast.id} className={clsx('toast', toast.tone === 'error' && 'toast--error')} onClick={() => dismissToast(toast.id)}>
            <strong>{toast.title}</strong>
            {toast.detail && <div style={{ fontSize: '0.85rem', marginTop: '4px', opacity: 0.75 }}>{toast.detail}</div>}
          </div>
        ))}
      </div>

      <footer className="app-footer">
        <span className="app-footer__label">Meet the community →</span>
        <a className="app-footer__link" href="https://www.reddit.com/r/debtcodersdojo/" target="_blank" rel="noopener noreferrer">
          r/debtcodersdojo
        </a>
      </footer>
    </div>
  );
}

export default App;
