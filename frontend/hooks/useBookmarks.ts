/**
 * AI Research OS — ブックマーク関連 React Query hooks
 */

import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    fetchBookmarks,
    addBookmark,
    removeBookmark,
    type ApiResponse,
    type Bookmark,
} from '../lib/api';

export function useBookmarks() {
    return useInfiniteQuery({
        queryKey: ['bookmarks'],
        queryFn: ({ pageParam }) =>
            fetchBookmarks({ cursor: pageParam as string | undefined }),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage: ApiResponse<Bookmark[]>) =>
            lastPage.pagination?.has_next ? lastPage.pagination.next_cursor : undefined,
    });
}

export function useAddBookmark() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (arxivId: string) => addBookmark(arxivId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
            void queryClient.invalidateQueries({ queryKey: ['papers'] });
        },
    });
}

export function useRemoveBookmark() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (bookmarkId: number) => removeBookmark(bookmarkId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
            void queryClient.invalidateQueries({ queryKey: ['papers'] });
        },
    });
}
