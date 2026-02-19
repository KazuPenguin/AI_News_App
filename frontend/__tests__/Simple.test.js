import React from 'react';
import { render } from '@testing-library/react-native';
import { View, Text } from 'react-native';

describe('Simple Test', () => {
    it('renders correctly', () => {
        const { getByText } = render(
            <View>
                <Text>Hello</Text>
            </View>
        );
        expect(getByText('Hello')).toBeTruthy();
    });
});
