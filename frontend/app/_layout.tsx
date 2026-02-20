import { Stack } from 'expo-router';
import { QueryClientProvider } from '@tanstack/react-query';
import { configureAmplify } from '../lib/amplify';
import { queryClient } from '../lib/query-client';
import '../global.css';

// Amplify 初期化
configureAmplify();

export default function RootLayout() {
    return (
        <QueryClientProvider client={queryClient}>
            <Stack>
                <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                <Stack.Screen name="paper/[id]" options={{ presentation: 'modal', headerShown: false }} />
                <Stack.Screen name="login" options={{ headerShown: false }} />
            </Stack>
        </QueryClientProvider>
    );
}
