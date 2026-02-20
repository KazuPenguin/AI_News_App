import { View, Text, ScrollView, SafeAreaView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, Stack, useRouter } from 'expo-router';
import { Star, ArrowLeft, Share } from 'lucide-react-native';
import { useEffect } from 'react';
import { usePaperDetail, useRecordView } from '../../hooks/usePapers';
import { useAddBookmark, useRemoveBookmark } from '../../hooks/useBookmarks';
import { useQueryClient } from '@tanstack/react-query';

export default function PaperDetailScreen() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const router = useRouter();
    const queryClient = useQueryClient();

    const { data, isLoading, isError } = usePaperDetail(id ?? '');
    const { mutate: recordViewMutate } = useRecordView();
    const { mutate: addBookmarkMutate } = useAddBookmark();
    const { mutate: removeBookmarkMutate } = useRemoveBookmark();

    const paper = data?.data;

    // 閲覧記録を自動送信
    useEffect(() => {
        if (id) {
            recordViewMutate(id);
        }
    }, [id, recordViewMutate]);

    const handleToggleBookmark = () => {
        if (!paper) return;
        if (paper.is_bookmarked) {
            // ブックマーク削除（bookmark_id が必要だが detail には含まれないため、
            // invalidate で対応。実際には bookmark_id を別途取得する必要があるが、
            // ここでは add/remove の切り替えで対応）
            // 簡易実装: bookmark一覧から該当を検索するか、addBookmark を再利用
            // TODO: bookmark_id の取得が必要
        } else {
            addBookmarkMutate(paper.arxiv_id, {
                onSuccess: () => {
                    void queryClient.invalidateQueries({ queryKey: ['paper', id] });
                },
            });
        }
    };

    if (isLoading) {
        return (
            <SafeAreaView className="flex-1 bg-white justify-center items-center">
                <Stack.Screen options={{ headerShown: false }} />
                <ActivityIndicator size="large" color="#3B82F6" />
            </SafeAreaView>
        );
    }

    if (isError || !paper) {
        return (
            <SafeAreaView className="flex-1 bg-white justify-center items-center">
                <Stack.Screen options={{ headerShown: false }} />
                <Text className="text-gray-400">論文が見つかりませんでした</Text>
                <TouchableOpacity onPress={() => router.back()} className="mt-4">
                    <Text className="text-blue-500">戻る</Text>
                </TouchableOpacity>
            </SafeAreaView>
        );
    }

    const authorText = paper.authors.join(', ');
    const dateText = paper.published_at
        ? new Date(paper.published_at).toLocaleDateString('ja-JP')
        : '';

    // レベル別解説のデフォルト表示（中級）
    const levelText = paper.detail?.levels?.intermediate ?? '';

    return (
        <SafeAreaView className="flex-1 bg-white">
            <Stack.Screen options={{ headerShown: false }} />

            {/* Header */}
            <View className="flex-row justify-between items-center p-4 border-b border-gray-100">
                <TouchableOpacity onPress={() => router.back()} className="p-2 -ml-2">
                    <ArrowLeft size={24} color="#000" />
                </TouchableOpacity>
                <View className="flex-row gap-4">
                    <TouchableOpacity>
                        <Share size={24} color="#000" />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={handleToggleBookmark}>
                        <Star
                            size={24}
                            color={paper.is_bookmarked ? '#F59E0B' : '#000'}
                            fill={paper.is_bookmarked ? '#F59E0B' : 'none'}
                        />
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView className="flex-1 p-4">
                <Text className="text-2xl font-bold mb-2 leading-tight">{paper.title}</Text>
                <View className="flex-row justify-between mb-4">
                    <Text className="text-gray-600 font-medium" numberOfLines={1}>{authorText}</Text>
                    <Text className="text-gray-400">{dateText}</Text>
                </View>

                {/* サマリー */}
                {paper.summary_ja && (
                    <View className="bg-blue-50 p-4 rounded-lg mb-4">
                        <Text className="text-sm font-bold text-blue-800 mb-1">要約</Text>
                        <Text className="text-base text-blue-900 leading-6">{paper.summary_ja}</Text>
                    </View>
                )}

                {/* セクション */}
                {paper.detail?.sections?.map((section) => (
                    <View key={section.section_id} className="mb-4">
                        <Text className="text-lg font-bold text-gray-900 mb-2">{section.title_ja}</Text>
                        <Text className="text-base text-gray-800 leading-7">{section.content_ja}</Text>
                    </View>
                ))}

                {/* 3視点解説 */}
                {paper.detail?.perspectives && (
                    <View className="mb-4">
                        <Text className="text-lg font-bold text-gray-900 mb-3">3視点の解説</Text>

                        <View className="bg-green-50 p-4 rounded-lg mb-2">
                            <Text className="text-sm font-bold text-green-800 mb-1">AIエンジニア視点</Text>
                            <Text className="text-sm text-green-900 leading-6">
                                {paper.detail.perspectives.ai_engineer}
                            </Text>
                        </View>

                        <View className="bg-purple-50 p-4 rounded-lg mb-2">
                            <Text className="text-sm font-bold text-purple-800 mb-1">数学者視点</Text>
                            <Text className="text-sm text-purple-900 leading-6">
                                {paper.detail.perspectives.mathematician}
                            </Text>
                        </View>

                        <View className="bg-orange-50 p-4 rounded-lg mb-2">
                            <Text className="text-sm font-bold text-orange-800 mb-1">ビジネス視点</Text>
                            <Text className="text-sm text-orange-900 leading-6">
                                {paper.detail.perspectives.business}
                            </Text>
                        </View>
                    </View>
                )}

                {/* レベル別テキスト */}
                {levelText && (
                    <View className="bg-gray-50 p-4 rounded-lg mb-8">
                        <Text className="text-sm font-bold text-gray-700 mb-1">解説（中級）</Text>
                        <Text className="text-base text-gray-800 leading-7">{levelText}</Text>
                    </View>
                )}
            </ScrollView>
        </SafeAreaView>
    );
}
