import axios from 'axios';
import apiClient, { setBaseUrl } from './client';
import { saveTokens, clearAllData, saveUserData, saveCompanySubdomain } from '../utils/storage';

/**
 * Authenticate the user and store tokens.
 *
 * @param {string} subdomain  Company subdomain (e.g. "acme")
 * @param {string} username
 * @param {string} password
 * @returns {object} User profile data
 */
export async function login(subdomain, username, password) {
  // Configure API base URL for this company
  setBaseUrl(subdomain);
  await saveCompanySubdomain(subdomain);

  // Obtain JWT token pair
  const { data: tokens } = await apiClient.post('/api/token/', {
    username,
    password,
  });

  await saveTokens(tokens.access, tokens.refresh);

  // Fetch user profile
  const { data: profile } = await apiClient.get('/mi-portal/api/perfil/');
  await saveUserData(profile);

  return profile;
}

/**
 * Log out: clear stored tokens and user data.
 */
export async function logout() {
  try {
    // Attempt server-side logout (best-effort)
    await apiClient.post('/api/token/blacklist/');
  } catch (_) {
    // Ignore — we'll clear local state regardless
  }
  await clearAllData();
}

/**
 * Refresh the access token using the stored refresh token.
 * This is normally handled automatically by the interceptor in client.js,
 * but can be called manually if needed.
 */
export async function refreshAccessToken(refreshToken) {
  const { data } = await apiClient.post('/api/token/refresh/', {
    refresh: refreshToken,
  });
  await saveTokens(data.access, refreshToken);
  return data.access;
}
