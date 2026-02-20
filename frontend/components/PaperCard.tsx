import { View, Text, TouchableOpacity } from 'react-native';
import { Link } from 'expo-router';
import { clsx } from 'clsx';
import type { PaperSummary } from '../lib/api';

type PaperCardProps = {
    paper: PaperSummary;
};

const IMPORTANCE_LABELS: Record<number, string> = {
    5: '超重要',
    4: '重要',
    3: '注目',
    2: '参考',
    1: '情報',
};

export function PaperCard({ paper }: PaperCardProps) {
    const authorText = paper.authors.join(', ');
    const dateText = paper.published_at
        ? new Date(paper.published_at).toLocaleDateString('ja-JP')
        : '';
    const importanceLabel = paper.importance ? IMPORTANCE_LABELS[paper.importance] ?? '' : '';

    return (
        <Link href={`/paper/${paper.arxiv_id}`} asChild>
            <TouchableOpacity
                className={clsx(
                    "bg-white rounded-xl p-4 mb-3 shadow-sm border border-gray-100 active:opacity-70",
                    paper.is_viewed && "opacity-60"
                )}
            >
                <View className="flex-row justify-between items-start mb-2">
                    <Text className="text-lg font-bold flex-1 mr-2 leading-6 text-gray-900">
                        {paper.title}
                    </Text>
                </View>

                <View className="flex-row items-center mb-2">
                    <Text className="text-gray-500 text-xs mr-2" numberOfLines={1}>
                        {authorText}
                    </Text>
                    <Text className="text-gray-400 text-xs">{dateText}</Text>
                </View>

                <View className="flex-row flex-wrap mb-2 gap-1">
                    {paper.category_name && (
                        <Text className="text-blue-600 text-xs font-medium">
                            #{paper.category_name}
                        </Text>
                    )}
                    {importanceLabel && (
                        <Text className="text-orange-600 text-xs font-medium">
                            #{importanceLabel}
                        </Text>
                    )}
                </View>

                <Text className="text-gray-600 text-sm leading-5" numberOfLines={3}>
                    {paper.summary_ja ?? paper.one_line_takeaway ?? ''}
                </Text>
            </TouchableOpacity>
        </Link>
    );
}
