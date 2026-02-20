/**
 * AI Research OS — React Query クライアント設定
 */

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 60 * 1000, // 60秒
            retry: 2,
            refetchOnWindowFocus: false,
        },
    },
});
