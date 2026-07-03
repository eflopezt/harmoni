import apiClient from './client';

/**
 * Get the employee's vacation balance (saldo vacacional).
 */
export async function getMyVacationBalance() {
  const { data } = await apiClient.get('/mi-portal/api/vacaciones/saldo/');
  return data;
}

/**
 * Get vacation request history.
 */
export async function getMyVacationRequests(params = {}) {
  const { data } = await apiClient.get('/mi-portal/api/vacaciones/', { params });
  return data;
}

/**
 * Submit a new vacation request.
 *
 * @param {object} request - { fecha_inicio, fecha_fin, motivo }
 */
export async function requestVacation(request) {
  const { data } = await apiClient.post('/mi-portal/api/vacaciones/', request);
  return data;
}

/**
 * Cancel a pending vacation request.
 */
export async function cancelVacationRequest(id) {
  const { data } = await apiClient.post(`/mi-portal/api/vacaciones/${id}/cancelar/`);
  return data;
}
