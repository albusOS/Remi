"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";

/**
 * Drop-in replacement backed by TanStack Query.
 *
 * Preserves the original `{ data, loading, error, refetch, setData }` shape
 * so every consumer works without changes, while gaining caching,
 * deduplication, stale-while-revalidate, and background refetch.
 */
export function useApiQuery<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
) {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const queryKey = ["api", ...deps];

  const { data, isLoading, error, refetch: tqRefetch } = useQuery<T, Error>({
    queryKey,
    queryFn: () => fetcherRef.current(),
  });

  const queryClient = useQueryClient();

  const refetch = useCallback(() => {
    tqRefetch();
  }, [tqRefetch]);

  const setData = useCallback(
    (updater: T | ((prev: T | null) => T)) => {
      queryClient.setQueryData<T>(queryKey, (old) => {
        if (typeof updater === "function") {
          return (updater as (prev: T | null) => T)(old ?? null);
        }
        return updater;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [queryClient, JSON.stringify(queryKey)],
  );

  return {
    data: data ?? null,
    loading: isLoading,
    error: error ?? null,
    refetch,
    setData,
  };
}
