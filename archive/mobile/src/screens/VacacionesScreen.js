import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  RefreshControl,
  Alert,
  FlatList,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  getMyVacationBalance,
  getMyVacationRequests,
  requestVacation,
} from '../api/vacaciones';
import { formatDate } from '../utils/format';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import EmptyState from '../components/EmptyState';

const TEAL = '#0f766e';

export default function VacacionesScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [balance, setBalance] = useState(null);
  const [requests, setRequests] = useState([]);

  // Form state
  const [fechaInicio, setFechaInicio] = useState('');
  const [fechaFin, setFechaFin] = useState('');
  const [motivo, setMotivo] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const [balData, reqData] = await Promise.allSettled([
        getMyVacationBalance(),
        getMyVacationRequests(),
      ]);
      if (balData.status === 'fulfilled') setBalance(balData.value);
      if (reqData.status === 'fulfilled') {
        const list = Array.isArray(reqData.value) ? reqData.value : reqData.value.results || [];
        setRequests(list);
      }
    } catch (_) {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const handleSubmit = async () => {
    if (!fechaInicio || !fechaFin) {
      Alert.alert('Error', 'Ingresa las fechas de inicio y fin.');
      return;
    }

    // Basic date format validation (YYYY-MM-DD)
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(fechaInicio) || !dateRegex.test(fechaFin)) {
      Alert.alert('Error', 'Formato de fecha: AAAA-MM-DD (ej. 2026-04-01)');
      return;
    }

    setSubmitting(true);
    try {
      await requestVacation({
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
        motivo: motivo || undefined,
      });
      Alert.alert('Solicitud Enviada', 'Tu solicitud de vacaciones fue registrada.');
      setFechaInicio('');
      setFechaFin('');
      setMotivo('');
      await fetchData();
    } catch (err) {
      Alert.alert(
        'Error',
        err.response?.data?.detail || 'No se pudo enviar la solicitud.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={TEAL} />}
    >
      {/* Balance Card */}
      <View style={styles.balanceCard}>
        <Ionicons name="sunny" size={32} color="#ffffff" />
        <View style={styles.balanceInfo}>
          <Text style={styles.balanceTitle}>Saldo Vacacional</Text>
          <View style={styles.balanceNumbers}>
            <Text style={styles.balanceAvailable}>
              {balance?.dias_disponibles ?? '--'}
            </Text>
            <Text style={styles.balanceSeparator}>/</Text>
            <Text style={styles.balanceTotal}>
              {balance?.dias_total ?? '30'} dias
            </Text>
          </View>
        </View>
      </View>

      {/* Request Form */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Nueva Solicitud</Text>

        <Text style={styles.label}>Fecha Inicio (AAAA-MM-DD)</Text>
        <TextInput
          style={styles.input}
          placeholder="2026-04-01"
          value={fechaInicio}
          onChangeText={setFechaInicio}
          keyboardType="default"
        />

        <Text style={styles.label}>Fecha Fin (AAAA-MM-DD)</Text>
        <TextInput
          style={styles.input}
          placeholder="2026-04-15"
          value={fechaFin}
          onChangeText={setFechaFin}
          keyboardType="default"
        />

        <Text style={styles.label}>Motivo (opcional)</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Vacaciones familiares..."
          value={motivo}
          onChangeText={setMotivo}
          multiline
          numberOfLines={3}
          textAlignVertical="top"
        />

        <TouchableOpacity
          style={[styles.submitButton, submitting && styles.submitButtonDisabled]}
          onPress={handleSubmit}
          disabled={submitting}
          activeOpacity={0.8}
        >
          <Text style={styles.submitButtonText}>
            {submitting ? 'Enviando...' : 'Enviar Solicitud'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Request History */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Historial de Solicitudes</Text>
        {requests.length === 0 ? (
          <EmptyState
            icon="calendar-outline"
            message="No tienes solicitudes registradas."
          />
        ) : (
          requests.map((req) => (
            <View key={req.id} style={styles.requestItem}>
              <View style={styles.requestHeader}>
                <Text style={styles.requestDates}>
                  {formatDate(req.fecha_inicio)} - {formatDate(req.fecha_fin)}
                </Text>
                <StatusBadge status={req.estado || 'PENDIENTE'} />
              </View>
              {req.dias && (
                <Text style={styles.requestDias}>{req.dias} dias</Text>
              )}
              {req.motivo && (
                <Text style={styles.requestMotivo} numberOfLines={2}>
                  {req.motivo}
                </Text>
              )}
            </View>
          ))
        )}
      </View>

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  balanceCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: TEAL,
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 12,
    padding: 20,
    gap: 16,
  },
  balanceInfo: {
    flex: 1,
  },
  balanceTitle: {
    color: '#99f6e4',
    fontSize: 13,
    fontWeight: '600',
  },
  balanceNumbers: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 4,
  },
  balanceAvailable: {
    fontSize: 36,
    fontWeight: '800',
    color: '#ffffff',
  },
  balanceSeparator: {
    fontSize: 20,
    color: '#99f6e4',
    marginHorizontal: 4,
  },
  balanceTotal: {
    fontSize: 16,
    color: '#99f6e4',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 12,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 6,
    marginTop: 10,
  },
  input: {
    backgroundColor: '#f9fafb',
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: '#111827',
  },
  textArea: {
    minHeight: 70,
  },
  submitButton: {
    backgroundColor: TEAL,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 16,
  },
  submitButtonDisabled: {
    opacity: 0.7,
  },
  submitButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '700',
  },
  requestItem: {
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
    paddingVertical: 12,
  },
  requestHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  requestDates: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  requestDias: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 2,
  },
  requestMotivo: {
    fontSize: 13,
    color: '#6b7280',
    marginTop: 4,
    fontStyle: 'italic',
  },
});
