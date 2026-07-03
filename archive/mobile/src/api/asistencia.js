import apiClient from './client';

/**
 * Mark attendance (clock in / clock out).
 * The server determines whether it's an entry or exit based on existing records.
 */
export async function marcarAsistencia(payload = {}) {
  const { data } = await apiClient.post('/mi-portal/api/marcar-asistencia/', payload);
  return data;
}

/**
 * Get today's attendance records for the logged-in employee.
 */
export async function getMyAttendanceToday() {
  const { data } = await apiClient.get('/mi-portal/api/asistencia/hoy/');
  return data;
}

/**
 * Get attendance history with optional date range filters.
 *
 * @param {object} params - { fecha_inicio, fecha_fin, page }
 */
export async function getMyAttendanceHistory(params = {}) {
  const { data } = await apiClient.get('/mi-portal/api/asistencia/', { params });
  return data;
}

/**
 * Get attendance summary / statistics for the current period.
 */
export async function getAttendanceSummary() {
  const { data } = await apiClient.get('/mi-portal/api/asistencia/resumen/');
  return data;
}

/**
 * Submit a leave request (papeleta).
 *
 * @param {object} papeleta - { tipo, fecha_inicio, fecha_fin, motivo }
 */
export async function submitPapeleta(papeleta) {
  const { data } = await apiClient.post('/mi-portal/api/papeletas/', papeleta);
  return data;
}

/**
 * Get the employee's leave requests (papeletas).
 */
export async function getMyPapeletas(params = {}) {
  const { data } = await apiClient.get('/mi-portal/api/papeletas/', { params });
  return data;
}
