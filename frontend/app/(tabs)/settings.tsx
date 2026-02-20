import { View, Text, SafeAreaView, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { Stack } from 'expo-router';
import { ChevronRight, Bell, User, FileText, Lock, HelpCircle } from 'lucide-react-native';
import { useUserProfile, useUpdateSettings, useUserStats } from '../../hooks/useUser';

const LEVEL_LABELS: Record<number, string> = {
    1: '初学者',
    2: '中級',
    3: 'プロ',
};

const SETTINGS_ITEMS = [
    { icon: Bell, label: '通知設定', route: '/settings/notifications' },
    { icon: FileText, label: '利用規約', route: '/settings/terms' },
    { icon: Lock, label: 'プライバシーポリシー', route: '/settings/privacy' },
    { icon: HelpCircle, label: 'お問い合わせ', route: '/settings/contact' },
];

export default function SettingsScreen() {
    const { data: profileData, isLoading: profileLoading } = useUserProfile();
    const { data: statsData } = useUserStats();
    const { mutate: updateSettings } = useUpdateSettings();

    const profile = profileData?.data;
    const stats = statsData?.data;

    const handleLevelChange = () => {
        if (!profile) return;
        // 1→2→3→1 のサイクル
        const nextLevel = ((profile.default_level % 3) + 1) as 1 | 2 | 3;
        updateSettings({ default_level: nextLevel });
    };

    return (
        <SafeAreaView className="flex-1 bg-gray-50">
            <Stack.Screen
                options={{
                    headerShown: true,
                    headerTitle: '設定',
                }}
            />

            <ScrollView className="flex-1">
                {/* ユーザー情報 */}
                {profileLoading ? (
                    <View className="p-4 items-center">
                        <ActivityIndicator size="small" color="#3B82F6" />
                    </View>
                ) : profile ? (
                    <View className="mt-4 bg-white border-y border-gray-200 p-4">
                        <View className="flex-row items-center mb-3">
                            <View className="w-12 h-12 bg-blue-100 rounded-full items-center justify-center mr-3">
                                <User size={24} color="#3B82F6" />
                            </View>
                            <View>
                                <Text className="text-base font-bold text-gray-900">
                                    {profile.display_name ?? profile.email}
                                </Text>
                                <Text className="text-xs text-gray-400">{profile.email}</Text>
                            </View>
                        </View>

                        {/* 統計 */}
                        {stats && (
                            <View className="flex-row justify-around mt-2 pt-3 border-t border-gray-100">
                                <View className="items-center">
                                    <Text className="text-lg font-bold text-gray-900">{stats.papers_viewed}</Text>
                                    <Text className="text-xs text-gray-400">閲覧</Text>
                                </View>
                                <View className="items-center">
                                    <Text className="text-lg font-bold text-gray-900">{stats.bookmarks_count}</Text>
                                    <Text className="text-xs text-gray-400">お気に入り</Text>
                                </View>
                                {stats.most_viewed_category && (
                                    <View className="items-center">
                                        <Text className="text-lg font-bold text-gray-900">{stats.most_viewed_category.count}</Text>
                                        <Text className="text-xs text-gray-400">{stats.most_viewed_category.name}</Text>
                                    </View>
                                )}
                            </View>
                        )}
                    </View>
                ) : null}

                {/* 難易度設定 */}
                <View className="mt-4 bg-white border-y border-gray-200">
                    <TouchableOpacity
                        onPress={handleLevelChange}
                        className="flex-row items-center p-4 border-b border-gray-100"
                    >
                        <User size={20} color="#666" />
                        <Text className="flex-1 text-base text-gray-900 ml-3">難易度設定</Text>
                        <Text className="text-sm text-blue-500 mr-2">
                            {profile ? LEVEL_LABELS[profile.default_level] ?? '中級' : '中級'}
                        </Text>
                        <ChevronRight size={20} color="#ccc" />
                    </TouchableOpacity>

                    {SETTINGS_ITEMS.map((item, index) => (
                        <TouchableOpacity
                            key={index}
                            className={`flex-row items-center p-4 ${index !== SETTINGS_ITEMS.length - 1 ? 'border-b border-gray-100' : ''
                                }`}
                        >
                            <item.icon size={20} color="#666" />
                            <Text className="flex-1 text-base text-gray-900 ml-3">{item.label}</Text>
                            <ChevronRight size={20} color="#ccc" />
                        </TouchableOpacity>
                    ))}
                </View>

                <View className="p-4 mt-4">
                    <Text className="text-center text-gray-400 text-xs">Version 1.0.0</Text>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}
