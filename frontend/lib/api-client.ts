/**
 * AI Research OS — API クライアント
 *
 * fetchAuthSession() で ID Token を取得し、Bearer token 付与でリクエストする。
 */

import { fetchAuthSession } from 'aws-amplify/auth';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? '';

export class ApiError extends Error {
    code: string;
    status: number;

    constructor(status: number, code: string, message: string) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.code = code;
    }
}

interface ApiClientOptions {
    method?: string;
    body?: unknown;
    params?: Record<string, string | number | undefined>;
}

export async function apiClient<T>(path: string, options: ApiClientOptions = {}): Promise<T> {
    const { method = 'GET', body, params } = options;

    // ID Token 取得
    let token = '';
    try {
        const session = await fetchAuthSession();
        token = session.tokens?.idToken?.toString() ?? '';
    } catch {
        // 未ログイン時は token なしで続行（health など）
    }

    // URL 構築
    let url = `${API_URL}${path}`;
    if (params) {
        const searchParams = new URLSearchParams();
        for (const [key, value] of Object.entries(params)) {
            if (value !== undefined) {
                searchParams.set(key, String(value));
            }
        }
        const qs = searchParams.toString();
        if (qs) {
            url += `?${qs}`;
        }
    }

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });

    // 204 No Content
    if (response.status === 204) {
        return undefined as T;
    }

    const json = await response.json();

    if (!response.ok) {
        const error = json?.error ?? {};
        throw new ApiError(
            response.status,
            error.code ?? 'UNKNOWN_ERROR',
            error.message ?? 'An unknown error occurred',
        );
    }

    return json as T;
}
