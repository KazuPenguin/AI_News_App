import { ScrollView, TouchableOpacity, Text } from 'react-native';
import { clsx } from 'clsx';

type CategoryItem = {
    id: number;
    name: string;
};

type CategoryTabProps = {
    categories: CategoryItem[];
    selectedCategoryId: number | null;
    onSelect: (categoryId: number | null) => void;
};

export function CategoryTab({ categories, selectedCategoryId, onSelect }: CategoryTabProps) {
    return (
        <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            className="max-h-12 border-b border-gray-100 bg-white"
            contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 8, gap: 8 }}
        >
            {/* 「すべて」タブ */}
            <TouchableOpacity
                onPress={() => onSelect(null)}
                className={clsx(
                    "px-4 py-1.5 rounded-full border",
                    selectedCategoryId === null
                        ? "bg-blue-500 border-blue-500"
                        : "bg-gray-50 border-gray-200"
                )}
            >
                <Text className={clsx("text-sm font-medium", selectedCategoryId === null ? "text-white" : "text-gray-600")}>
                    すべて
                </Text>
            </TouchableOpacity>

            {categories.map((cat) => {
                const isSelected = cat.id === selectedCategoryId;
                return (
                    <TouchableOpacity
                        key={cat.id}
                        onPress={() => onSelect(cat.id)}
                        className={clsx(
                            "px-4 py-1.5 rounded-full border",
                            isSelected
                                ? "bg-blue-500 border-blue-500"
                                : "bg-gray-50 border-gray-200"
                        )}
                    >
                        <Text className={clsx("text-sm font-medium", isSelected ? "text-white" : "text-gray-600")}>
                            {cat.name}
                        </Text>
                    </TouchableOpacity>
                );
            })}
        </ScrollView>
    );
}
