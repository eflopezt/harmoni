import apiClient from './client';

/**
 * Get the logged-in employee's profile.
 */
export async function getMyProfile() {
  const { data } = await apiClient.get('/mi-portal/api/perfil/');
  return data;
}

/**
 * Update the logged-in employee's profile (partial update).
 */
export async function updateMyProfile(fields) {
  const { data } = await apiClient.patch('/mi-portal/api/perfil/', fields);
  return data;
}

/**
 * Get employee list (admin/RRHH only).
 */
export async function getEmployees(params = {}) {
  const { data } = await apiClient.get('/api/v1/personal/', { params });
  return data;
}

/**
 * Get a single employee's details.
 */
export async function getEmployee(id) {
  const { data } = await apiClient.get(`/api/v1/personal/${id}/`);
  return data;
}

/**
 * Search employees by name or document number.
 */
export async function searchEmployees(query) {
  const { data } = await apiClient.get('/api/v1/personal/', {
    params: { search: query },
  });
  return data;
}
