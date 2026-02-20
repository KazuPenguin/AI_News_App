/**
 * AI Research OS — ユーザー関連 React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    fetchUserProfile,
    updateUserSettings,
    fetchUserStats,
    type UpdateSettingsRequest,
} from '../lib/api';

export function useUserProfile() {
    return useQuery({
        queryKey: ['user', 'profile'],
        queryFn: fetchUserProfile,
    });
}

export function useUpdateSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (settings: UpdateSettingsRequest) => updateUserSettings(settings),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
        },
    });
}

export function useUserStats() {
    return useQuery({
        queryKey: ['user', 'stats'],
        queryFn: fetchUserStats,
    });
}
