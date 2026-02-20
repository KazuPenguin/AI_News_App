import { View, Text, FlatList, SafeAreaView, ActivityIndicator, TouchableOpacity } from 'react-native';
import { Link } from 'expo-router';
import { Stack } from 'expo-router';
import { useBookmarks } from '../../hooks/useBookmarks';
import type { Bookmark } from '../../lib/api';

function BookmarkCard({ bookmark }: { bookmark: Bookmark }) {
    const dateText = bookmark.bookmarked_at
        ? new Date(bookmark.bookmarked_at).toLocaleDateString('ja-JP')
        : '';

    return (
        <Link href={`/paper/${bookmark.paper.arxiv_id}`} asChild>
            <TouchableOpacity className="bg-white rounded-xl p-4 mb-3 shadow-sm border border-gray-100 active:opacity-70">
                <View className="flex-row justify-between items-start mb-2">
                    <Text className="text-lg font-bold flex-1 mr-2 leading-6 text-gray-900">
                        {bookmark.paper.title}
                    </Text>
                </View>

                <View className="flex-row items-center mb-2">
                    {bookmark.paper.category_name && (
                        <Text className="text-blue-600 text-xs font-medium mr-2">
                            #{bookmark.paper.category_name}
                        </Text>
                    )}
                    <Text className="text-gray-400 text-xs">{dateText}</Text>
                </View>

                <Text className="text-gray-600 text-sm leading-5" numberOfLines={3}>
                    {bookmark.paper.summary_ja ?? ''}
                </Text>
            </TouchableOpacity>
        </Link>
    );
}

export default function FavoriteScreen() {
    const {
        data,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isLoading,
        isError,
    } = useBookmarks();

    const bookmarks: Bookmark[] = data?.pages.flatMap((page) => page.data) ?? [];

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
                    headerTitle: 'お気に入り',
                    headerShadowVisible: false,
                }}
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
                    data={bookmarks}
                    keyExtractor={(item) => String(item.bookmark_id)}
                    renderItem={({ item }) => <BookmarkCard bookmark={item} />}
                    contentContainerStyle={{ padding: 16 }}
                    onEndReached={handleEndReached}
                    onEndReachedThreshold={0.5}
                    ListFooterComponent={
                        isFetchingNextPage ? (
                            <ActivityIndicator size="small" color="#3B82F6" style={{ marginVertical: 16 }} />
                        ) : null
                    }
                    ListEmptyComponent={
                        <View className="flex-1 justify-center items-center mt-20">
                            <Text className="text-gray-400">お気に入りはまだありません</Text>
                        </View>
                    }
                />
            )}
        </SafeAreaView>
    );
}
