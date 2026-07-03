import axios from 'axios';
import { getAccessToken, getRefreshToken, saveTokens, clearAllData } from '../utils/storage';

/**
 * Build the base URL from a company subdomain.
 * In production each company has its own subdomain: https://acme.harmoni.pe
 * For local development use: http://<IP>:8000
 */
function buildBaseUrl(subdomain) {
  if (__DEV__) {
    // During development, point to local Django server.
    // Replace with your machine's LAN IP so the phone can reach it.
    return 'http://192.168.1.100:8000';
  }
  return `https://${subdomain}.harmoni.pe`;
}

let _baseUrl = null;

/**
 * Set the base URL for all API calls. Call once after the user enters their
 * company subdomain on the login screen.
 */
export function setBaseUrl(subdomain) {
  _baseUrl = buildBaseUrl(subdomain);
  apiClient.defaults.baseURL = _baseUrl;
}

/**
 * Pre-configured Axios instance with JWT handling.
 */
const apiClient = axios.create({
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// ── Request interceptor: attach access token ──────────────────────────
apiClient.interceptors.request.use(
  async (config) => {
    const token = await getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response interceptor: auto-refresh on 401 ────────────────────────
let isRefreshing = false;
let failedQueue = [];

function processQueue(error, token = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and we haven't already retried this request
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refresh = await getRefreshToken();
        if (!refresh) {
          throw new Error('No refresh token');
        }

        const { data } = await axios.post(`${_baseUrl}/api/token/refresh/`, {
          refresh,
        });

        await saveTokens(data.access, refresh);
        apiClient.defaults.headers.Authorization = `Bearer ${data.access}`;
        processQueue(null, data.access);

        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        // Refresh failed — force logout
        await clearAllData();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
