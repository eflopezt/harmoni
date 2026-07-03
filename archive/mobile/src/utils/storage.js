import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS = {
  ACCESS_TOKEN: '@harmoni_access_token',
  REFRESH_TOKEN: '@harmoni_refresh_token',
  USER_DATA: '@harmoni_user_data',
  COMPANY_SUBDOMAIN: '@harmoni_company_subdomain',
};

/**
 * Store JWT tokens after login.
 */
export async function saveTokens(access, refresh) {
  await AsyncStorage.multiSet([
    [KEYS.ACCESS_TOKEN, access],
    [KEYS.REFRESH_TOKEN, refresh],
  ]);
}

export async function getAccessToken() {
  return AsyncStorage.getItem(KEYS.ACCESS_TOKEN);
}

export async function getRefreshToken() {
  return AsyncStorage.getItem(KEYS.REFRESH_TOKEN);
}

export async function clearTokens() {
  await AsyncStorage.multiRemove([KEYS.ACCESS_TOKEN, KEYS.REFRESH_TOKEN]);
}

/**
 * Store/retrieve the logged-in user profile.
 */
export async function saveUserData(userData) {
  await AsyncStorage.setItem(KEYS.USER_DATA, JSON.stringify(userData));
}

export async function getUserData() {
  const raw = await AsyncStorage.getItem(KEYS.USER_DATA);
  return raw ? JSON.parse(raw) : null;
}

export async function clearUserData() {
  await AsyncStorage.removeItem(KEYS.USER_DATA);
}

/**
 * Store/retrieve the company subdomain so users don't re-enter it.
 */
export async function saveCompanySubdomain(subdomain) {
  await AsyncStorage.setItem(KEYS.COMPANY_SUBDOMAIN, subdomain);
}

export async function getCompanySubdomain() {
  return AsyncStorage.getItem(KEYS.COMPANY_SUBDOMAIN);
}

/**
 * Full logout — clear everything.
 */
export async function clearAllData() {
  await AsyncStorage.multiRemove(Object.values(KEYS));
}

export { KEYS };
