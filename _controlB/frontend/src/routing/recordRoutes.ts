import type { Location } from 'react-router-dom';

export const NEW_RECORD_SEGMENT = 'novo';

export interface RecordNavigationState {
  returnTo?: string;
}

const normalizePathSegment = (value: string) => value.replace(/^\/+|\/+$/g, '');

export function buildRecordFormPath(modulePath: string, resourcePath: string, recordId?: string): string {
  const moduleSegment = normalizePathSegment(modulePath);
  const resourceSegment = normalizePathSegment(resourcePath);
  const idSegment = recordId ? encodeURIComponent(recordId) : NEW_RECORD_SEGMENT;
  return `/${moduleSegment}/${resourceSegment}/${idSegment}`;
}

export function isNewRecordSegment(recordId?: string): boolean {
  return !recordId || recordId === NEW_RECORD_SEGMENT;
}

export function createRecordNavigationState(
  location: Pick<Location, 'pathname' | 'search' | 'hash'>,
): RecordNavigationState {
  return {
    returnTo: `${location.pathname}${location.search}${location.hash}`,
  };
}
