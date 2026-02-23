import '@aws-amplify/react-native';
import { Stack } from 'expo-router';
import { QueryClientProvider } from '@tanstack/react-query';
import { configureAmplify } from '../lib/amplify';
import { queryClient } from '../lib/query-client';
import '../global.css';

// Amplify 初期化
try {
    configureAmplify();
    console.log('[RootLayout] Amplify configured successfully');
} catch (error) {
    console.error('[RootLayout] Failed to configure Amplify:', error);
}

export { ErrorBoundary } from 'expo-router';

export default function RootLayout() {
    console.log('[RootLayout] Rendering starting...');
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
