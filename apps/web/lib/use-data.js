'use client';
import {useCallback, useEffect, useRef, useState} from 'react';

// A key includes the account and filters. Cached data never crosses that boundary.
export function useData(key, loader, {retain = false} = {}) {
  const load = useRef(loader);
  load.current = loader;
  const [revision, setRevision] = useState(0);
  const [snapshot, setSnapshot] = useState({key, value: null, error: '', loading: true});
  useEffect(() => {
    let alive = true;
    setSnapshot(old => ({key, value: retain && old.key === key ? old.value : null, error: '', loading: true}));
    load.current().then(value => {
      if (alive) setSnapshot({key, value, error: '', loading: false});
    }).catch(error => {
      if (alive) setSnapshot({key, value: null, error: error.message, loading: false});
    });
    return () => {alive = false;};
  }, [key, revision, retain]);
  const setValue = useCallback(value => setSnapshot(old => old.key !== key ? old : {
    ...old, value: typeof value === 'function' ? value(old.value) : value,
  }), [key]);
  return {
    ...(snapshot.key === key ? snapshot : {value: null, error: '', loading: true}),
    setValue,
    reload: useCallback(() => setRevision(value => value + 1), []),
  };
}

// Chat lists keep their current contents while a background refresh is in progress.
export function useBackgroundData(key, loader) {
  return useData(key, loader, {retain: true});
}
