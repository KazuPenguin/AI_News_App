import { View, FlatList, SafeAreaView, ActivityIndicator, Text } from 'react-native';
import { useState, useMemo } from 'react';
import { PaperCard } from '../../components/PaperCard';
import { CategoryTab } from '../../components/CategoryTab';
import { Stack } from 'expo-router';
import { Search, Filter } from 'lucide-react-native';
import { TouchableOpacity } from 'react-native';
import { usePapers, useCategories } from '../../hooks/usePapers';
import type { PaperSummary } from '../../lib/api';

export default function HomeScreen() {
    const [categoryId, setCategoryId] = useState<number | null>(null);

    const filters = useMemo(
        () => (categoryId !== null ? { category_id: categoryId } : {}),
        [categoryId]
    );

    const { data: categoriesData } = useCategories();
    const {
        data: papersData,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isLoading,
        isError,
    } = usePapers(filters);

    const categories = categoriesData?.data ?? [];
    const papers: PaperSummary[] = papersData?.pages.flatMap((page) => page.data) ?? [];

    const handleEndReached = () => {
        if (hasNextPage && !isFetchingNextPage) {
            void fetchNextPage();
        }
    };

    return (
        <SafeAreaView className="flex-1 bg-gray-50">
            <Stack.Screen
                options={{
                    headerShown: true,
                    headerTitle: 'トップ',
                    headerTitleStyle: { fontWeight: 'bold' },
                    headerLeft: () => (
                        <TouchableOpacity className="ml-4">
                            <Filter size={24} color="#000" />
                        </TouchableOpacity>
                    ),
                    headerRight: () => (
                        <TouchableOpacity className="mr-4">
                            <Search size={24} color="#000" />
                        </TouchableOpacity>
                    ),
                    headerShadowVisible: false,
                    headerStyle: { backgroundColor: '#fff' },
                }}
            />

            <CategoryTab
                categories={categories}
                selectedCategoryId={categoryId}
                onSelect={setCategoryId}
            />

            {isLoading ? (
                <View className="flex-1 justify-center items-center">
                    <ActivityIndicator size="large" color="#3B82F6" />
                </View>
            ) : isError ? (
                <View className="flex-1 justify-center items-center">
                    <Text className="text-gray-400">データの取得に失敗しました</Text>
                </View>
            ) : (
                <FlatList
                    data={papers}
                    keyExtractor={(item) => item.arxiv_id}
                    renderItem={({ item }) => <PaperCard paper={item} />}
                    contentContainerStyle={{ padding: 16 }}
                    showsVerticalScrollIndicator={false}
                    onEndReached={handleEndReached}
                    onEndReachedThreshold={0.5}
                    ListFooterComponent={
                        isFetchingNextPage ? (
                            <ActivityIndicator size="small" color="#3B82F6" style={{ marginVertical: 16 }} />
                        ) : null
                    }
                    ListEmptyComponent={
                        <View className="flex-1 justify-center items-center mt-20">
                            <Text className="text-gray-400">論文がありません</Text>
                        </View>
                    }
                />
            )}
        </SafeAreaView>
    );
}
