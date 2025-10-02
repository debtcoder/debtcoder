export type UploadItem = {
  filename: string;
  size_bytes: number;
  modified_at: string;
};

export type UploadSummary = {
  filename: string;
  bytes_written: number;
};

export type UploadCommandResponse = {
  command: string;
  output: string[];
  status: string;
  error?: string | null;
};

export type Diagnostics = {
  status: string;
  version: string;
  uptime_seconds: number;
  motd_exists: boolean;
  motd_last_modified?: string | null;
  upload_dir: string;
  upload_file_count: number;
  upload_disk_usage_bytes: number;
  duckduckgo_ready: boolean;
  python_version: string;
};

export type FSListItem = {
  path: string;
  is_dir: boolean;
  size_bytes: number | null;
  modified_at: string;
};

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'https://api.debtcodersdoja.com';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json() as Promise<T>;
  }
  return response.text() as unknown as T;
}

export async function fetchUploads(): Promise<UploadItem[]> {
  const response = await fetch(`${API_BASE}/uploads`);
  const payload = await handleResponse<{ files: UploadItem[] }>(response);
  return payload.files;
}

export async function fetchUploadText(filename: string): Promise<string> {
  const response = await fetch(`${API_BASE}/upload/${encodeURIComponent(filename)}/text`);
  const payload = await handleResponse<{ content: string }>(response);
  return payload.content;
}

export async function saveUploadText(filename: string, content: string): Promise<UploadSummary> {
  const response = await fetch(`${API_BASE}/upload/${encodeURIComponent(filename)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return handleResponse<UploadSummary>(response);
}

export async function deleteUpload(filename: string): Promise<UploadSummary> {
  const response = await fetch(`${API_BASE}/upload/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
  return handleResponse<UploadSummary>(response);
}

export async function renameUpload(filename: string, target: string): Promise<UploadSummary> {
  const response = await fetch(`${API_BASE}/upload/${encodeURIComponent(filename)}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target }),
  });
  return handleResponse<UploadSummary>(response);
}

export async function runUploadCommand(command: string): Promise<UploadCommandResponse> {
  const response = await fetch(`${API_BASE}/uploads/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command }),
  });
  return handleResponse<UploadCommandResponse>(response);
}

export async function uploadFiles(files: FileList | File[]): Promise<UploadSummary[]> {
  const payload = new FormData();
  const list = Array.isArray(files) ? files : Array.from(files);
  list.forEach((file) => payload.append('files', file));

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: payload,
  });
  return handleResponse<UploadSummary[]>(response);
}

export async function fetchMotd(): Promise<string> {
  const response = await fetch(`${API_BASE}/motd`);
  return handleResponse<string>(response);
}

export async function updateMotd(content: string) {
  const response = await fetch(`${API_BASE}/motd`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return handleResponse<{ message: string; bytes_written: number; updated_at: string }>(response);
}

export async function fetchDiagnostics(): Promise<Diagnostics> {
  const response = await fetch(`${API_BASE}/diagnostics`);
  return handleResponse<Diagnostics>(response);
}

export async function fetchFSList(path?: string): Promise<FSListItem[]> {
  const url = new URL(`${API_BASE}/fs/list`);
  if (path) url.searchParams.set('path', path);
  const response = await fetch(url.toString());
  const payload = await handleResponse<{ items: FSListItem[] }>(response);
  return payload.items;
}

export async function fetchFileText(path: string): Promise<string> {
  const url = new URL(`${API_BASE}/fs/read`);
  url.searchParams.set('path', path);
  const response = await fetch(url.toString());
  const payload = await handleResponse<TextFilePayload>(response);
  return payload.content;
}

type TextFilePayload = {
  content: string;
};

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const idx = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, idx);
  return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
}
