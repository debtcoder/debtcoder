import { useCallback, useState } from 'react';

export type ToastTone = 'info' | 'error';

export interface ToastMessage {
  id: string;
  title: string;
  detail?: string;
  tone?: ToastTone;
}

export function useToasts() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const pushToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    setToasts((current) => [{ id: crypto.randomUUID(), tone: 'info', ...toast }, ...current]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  return { toasts, pushToast, dismissToast };
}
