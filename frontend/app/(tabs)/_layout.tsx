import { Tabs } from 'expo-router';
import { Home, Star, Settings } from 'lucide-react-native';

export default function TabLayout() {
    return (
        <Tabs screenOptions={{ tabBarActiveTintColor: '#007AFF' }}>
            <Tabs.Screen
                name="index"
                options={{
                    title: 'Home',
                    headerShown: false, // Custom header in Home screen
                    tabBarIcon: ({ color }) => <Home size={24} color={color} />,
                }}
            />
            <Tabs.Screen
                name="favorite"
                options={{
                    title: 'Favorite',
                    headerShown: false,
                    tabBarIcon: ({ color }) => <Star size={24} color={color} />,
                }}
            />
            <Tabs.Screen
                name="settings"
                options={{
                    title: 'Settings',
                    headerShown: true,
                    tabBarIcon: ({ color }) => <Settings size={24} color={color} />,
                }}
            />
        </Tabs>
    );
}
