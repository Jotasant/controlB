import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

import { normalizeRecordType, parseRecordReference, type RecordReferenceType } from './recordNavigation';

interface UseRecordDeepLinkOptions<T> {
  types: string | string[];
  records: T[];
  onOpen: (record: T) => void;
  getIds?: (record: T) => Array<string | null | undefined>;
}

const defaultGetIds = <T extends { id: string }>(record: T) => [record.id];

/** Abre uma única vez o registro indicado na URL assim que sua lista for carregada. */
export const useRecordDeepLink = <T extends { id: string }>({
  types,
  records,
  onOpen,
  getIds = defaultGetIds,
}: UseRecordDeepLinkOptions<T>): void => {
  const [searchParams] = useSearchParams();
  const openedReference = useRef('');
  const reference = parseRecordReference(searchParams);
  const referenceType = reference?.type || null;
  const referenceId = reference?.id || '';
  const acceptedTypeSignature = (Array.isArray(types) ? types : [types])
    .map(normalizeRecordType)
    .filter((type): type is RecordReferenceType => Boolean(type))
    .join('|');

  useEffect(() => {
    if (!referenceType || !acceptedTypeSignature.split('|').includes(referenceType)) return;
    const signature = `${referenceType}:${referenceId}`;
    if (openedReference.current === signature) return;

    const record = records.find(item => getIds(item).some(id => id === referenceId));
    if (!record) return;
    openedReference.current = signature;
    onOpen(record);
  }, [acceptedTypeSignature, getIds, onOpen, records, referenceId, referenceType]);
};
