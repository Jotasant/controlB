import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export function useRecordFormTab<T extends string>(
  allowedTabs: readonly T[],
  defaultTab: T,
  parameterName = 'tab',
): readonly [T, (tab: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get(parameterName) as T | null;
  const activeTab = requestedTab && allowedTabs.includes(requestedTab) ? requestedTab : defaultTab;

  const setActiveTab = useCallback((tab: T) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (tab === defaultTab) next.delete(parameterName);
      else next.set(parameterName, tab);
      return next;
    }, { replace: true });
  }, [defaultTab, parameterName, setSearchParams]);

  return [activeTab, setActiveTab] as const;
}
