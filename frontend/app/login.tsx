import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert, SafeAreaView } from 'react-native';
import { useRouter } from 'expo-router';
import { signIn } from 'aws-amplify/auth';
import { Lock, Mail } from 'lucide-react-native';

export default function LoginScreen() {
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    async function handleSignIn() {
        if (!email || !password) {
            Alert.alert('Error', 'Please enter email and password');
            return;
        }

        setLoading(true);
        try {
            const { isSignedIn } = await signIn({ username: email, password });
            if (isSignedIn) {
                router.replace('/(tabs)');
            } else {
                Alert.alert('Info', 'Additional steps required (e.g. MFA)');
            }
        } catch (error: any) {
            Alert.alert('Login Failed', error.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <SafeAreaView className="flex-1 bg-white justify-center p-6">
            <View className="mb-10">
                <Text className="text-3xl font-bold text-center mb-2">AI News</Text>
                <Text className="text-gray-500 text-center">Login to your account</Text>
            </View>

            <View className="space-y-4">
                <View className="bg-gray-50 rounded-lg flex-row items-center px-4 py-3 border border-gray-100">
                    <Mail size={20} color="#9CA3AF" />
                    <TextInput
                        placeholder="Email"
                        className="flex-1 ml-3 text-base"
                        value={email}
                        onChangeText={setEmail}
                        autoCapitalize="none"
                        keyboardType="email-address"
                    />
                </View>

                <View className="bg-gray-50 rounded-lg flex-row items-center px-4 py-3 border border-gray-100 mb-6">
                    <Lock size={20} color="#9CA3AF" />
                    <TextInput
                        placeholder="Password"
                        className="flex-1 ml-3 text-base"
                        value={password}
                        onChangeText={setPassword}
                        secureTextEntry
                    />
                </View>

                <TouchableOpacity
                    onPress={handleSignIn}
                    disabled={loading}
                    className={`bg-blue-600 rounded-lg py-4 ${loading ? 'opacity-70' : ''}`}
                >
                    <Text className="text-white text-center font-bold text-lg">
                        {loading ? 'Logging in...' : 'Login'}
                    </Text>
                </TouchableOpacity>

                <TouchableOpacity className="mt-4">
                    <Text className="text-center text-blue-600">Don&apos;t have an account? Sign up</Text>
                </TouchableOpacity>
            </View>
        </SafeAreaView>
    );
}
