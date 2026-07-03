import React, { createContext, useContext, useEffect, useReducer } from 'react';
import { login as apiLogin, logout as apiLogout } from '../api/auth';
import { setBaseUrl } from '../api/client';
import {
  getAccessToken,
  getUserData,
  getCompanySubdomain,
  clearAllData,
} from '../utils/storage';

const AuthContext = createContext(null);

const initialState = {
  isLoading: true,
  isAuthenticated: false,
  user: null,
  error: null,
};

function authReducer(state, action) {
  switch (action.type) {
    case 'RESTORE_TOKEN':
      return {
        ...state,
        isLoading: false,
        isAuthenticated: !!action.user,
        user: action.user,
      };
    case 'LOGIN_START':
      return { ...state, isLoading: true, error: null };
    case 'LOGIN_SUCCESS':
      return {
        ...state,
        isLoading: false,
        isAuthenticated: true,
        user: action.user,
        error: null,
      };
    case 'LOGIN_ERROR':
      return {
        ...state,
        isLoading: false,
        isAuthenticated: false,
        error: action.error,
      };
    case 'LOGOUT':
      return { ...state, isLoading: false, isAuthenticated: false, user: null };
    default:
      return state;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // On mount, try to restore an existing session from AsyncStorage.
  useEffect(() => {
    (async () => {
      try {
        const token = await getAccessToken();
        const subdomain = await getCompanySubdomain();
        if (token && subdomain) {
          setBaseUrl(subdomain);
          const user = await getUserData();
          dispatch({ type: 'RESTORE_TOKEN', user });
        } else {
          dispatch({ type: 'RESTORE_TOKEN', user: null });
        }
      } catch {
        dispatch({ type: 'RESTORE_TOKEN', user: null });
      }
    })();
  }, []);

  const authActions = {
    login: async (subdomain, username, password) => {
      dispatch({ type: 'LOGIN_START' });
      try {
        const user = await apiLogin(subdomain, username, password);
        dispatch({ type: 'LOGIN_SUCCESS', user });
        return user;
      } catch (err) {
        const message =
          err.response?.data?.detail ||
          err.response?.data?.non_field_errors?.[0] ||
          'Error al iniciar sesion. Verifica tus credenciales.';
        dispatch({ type: 'LOGIN_ERROR', error: message });
        throw err;
      }
    },

    logout: async () => {
      await apiLogout();
      dispatch({ type: 'LOGOUT' });
    },
  };

  return (
    <AuthContext.Provider value={{ ...state, ...authActions }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
