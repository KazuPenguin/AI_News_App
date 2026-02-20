import { Amplify } from 'aws-amplify';

const amplifyConfig = {
    Auth: {
        Cognito: {
            userPoolId: process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID!,
            userPoolClientId: process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID!,
        },
    },
};

export const configureAmplify = () => {
    Amplify.configure(amplifyConfig);
};
