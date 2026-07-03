import apiClient from './client';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { getAccessToken } from '../utils/storage';

/**
 * Get list of payslips (boletas) for the logged-in employee.
 */
export async function getMyBoletas(params = {}) {
  const { data } = await apiClient.get('/mi-portal/api/boletas/', { params });
  return data;
}

/**
 * Get details of a specific payslip.
 */
export async function getBoletaDetail(id) {
  const { data } = await apiClient.get(`/mi-portal/api/boletas/${id}/`);
  return data;
}

/**
 * Download a payslip PDF and share/save it.
 *
 * @param {number} id  Boleta ID
 * @param {string} filename  Desired filename (e.g., "boleta_202601.pdf")
 */
export async function downloadBoletaPdf(id, filename = 'boleta.pdf') {
  const token = await getAccessToken();
  const baseUrl = apiClient.defaults.baseURL;

  const fileUri = `${FileSystem.documentDirectory}${filename}`;

  const result = await FileSystem.downloadAsync(
    `${baseUrl}/mi-portal/api/boletas/${id}/pdf/`,
    fileUri,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (result.status !== 200) {
    throw new Error(`Error descargando boleta: HTTP ${result.status}`);
  }

  // Open share dialog so the user can save or share the PDF
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(result.uri, {
      mimeType: 'application/pdf',
      dialogTitle: 'Boleta de Pago',
    });
  }

  return result.uri;
}

/**
 * Get payroll summary for a given period.
 */
export async function getNominaSummary(periodoId) {
  const { data } = await apiClient.get(`/mi-portal/api/nomina/resumen/`, {
    params: { periodo: periodoId },
  });
  return data;
}
