import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import type { RecordNavigationState } from '@/routing/recordRoutes';

export function useRecordFormNavigation(fallbackPath: string) {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as RecordNavigationState | null;

  return useCallback(() => {
    navigate(state?.returnTo || fallbackPath);
  }, [fallbackPath, navigate, state?.returnTo]);
}
