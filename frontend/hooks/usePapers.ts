/**
 * AI Research OS — 論文関連 React Query hooks
 */

import { useInfiniteQuery, useQuery, useMutation } from '@tanstack/react-query';
import {
    fetchPapers,
    fetchPaperDetail,
    fetchCategories,
    recordView,
    type PapersQuery,
    type ApiResponse,
    type PaperSummary,
    type PaperDetail,
    type Category,
} from '../lib/api';

export function usePapers(filters: Omit<PapersQuery, 'cursor'> = {}) {
    return useInfiniteQuery({
        queryKey: ['papers', filters],
        queryFn: ({ pageParam }) =>
            fetchPapers({ ...filters, cursor: pageParam as string | undefined }),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage: ApiResponse<PaperSummary[]>) =>
            lastPage.pagination?.has_next ? lastPage.pagination.next_cursor : undefined,
    });
}

export function usePaperDetail(arxivId: string) {
    return useQuery({
        queryKey: ['paper', arxivId],
        queryFn: () => fetchPaperDetail(arxivId),
        enabled: !!arxivId,
    });
}

export function useCategories() {
    return useQuery({
        queryKey: ['categories'],
        queryFn: fetchCategories,
        staleTime: 3600 * 1000, // 1時間
    });
}

export function useRecordView() {
    return useMutation({
        mutationFn: (arxivId: string) => recordView(arxivId),
    });
}
