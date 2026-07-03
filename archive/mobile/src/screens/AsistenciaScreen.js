import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  marcarAsistencia,
  getMyAttendanceToday,
  getAttendanceSummary,
} from '../api/asistencia';
import { formatDateTime } from '../utils/format';
import LoadingSpinner from '../components/LoadingSpinner';

const TEAL = '#0f766e';

const WEEKDAYS = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab'];
const MONTHS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

function getCalendarDays(year, month) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const days = [];

  for (let i = 0; i < firstDay; i++) {
    days.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    days.push(d);
  }
  return days;
}

export default function AsistenciaScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [marking, setMarking] = useState(false);
  const [today, setToday] = useState(null);
  const [summary, setSummary] = useState(null);

  const now = new Date();
  const calendarDays = getCalendarDays(now.getFullYear(), now.getMonth());

  const fetchData = useCallback(async () => {
    try {
      const [todayData, summaryData] = await Promise.allSettled([
        getMyAttendanceToday(),
        getAttendanceSummary(),
      ]);
      if (todayData.status === 'fulfilled') setToday(todayData.value);
      if (summaryData.status === 'fulfilled') setSummary(summaryData.value);
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

  const handleMark = async () => {
    setMarking(true);
    try {
      const result = await marcarAsistencia();
      Alert.alert(
        'Asistencia',
        result.message || result.tipo === 'entrada'
          ? 'Entrada registrada correctamente.'
          : 'Salida registrada correctamente.',
      );
      await fetchData();
    } catch (err) {
      Alert.alert(
        'Error',
        err.response?.data?.detail || 'No se pudo registrar la asistencia.',
      );
    } finally {
      setMarking(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={TEAL} />}
    >
      {/* Mini Calendar */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          {MONTHS[now.getMonth()]} {now.getFullYear()}
        </Text>
        <View style={styles.calendarHeader}>
          {WEEKDAYS.map((d) => (
            <Text key={d} style={styles.calendarWeekday}>{d}</Text>
          ))}
        </View>
        <View style={styles.calendarGrid}>
          {calendarDays.map((day, idx) => {
            const isToday = day === now.getDate();
            return (
              <View key={idx} style={styles.calendarCell}>
                {day ? (
                  <View style={[styles.calendarDay, isToday && styles.calendarDayToday]}>
                    <Text style={[styles.calendarDayText, isToday && styles.calendarDayTextToday]}>
                      {day}
                    </Text>
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>
      </View>

      {/* Today Status */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Hoy</Text>
        <View style={styles.todayRow}>
          <View style={styles.todayItem}>
            <Ionicons name="log-in-outline" size={20} color="#059669" />
            <Text style={styles.todayLabel}>Entrada</Text>
            <Text style={styles.todayValue}>
              {today?.entrada ? formatDateTime(today.entrada).split(' ')[1] : '--:--'}
            </Text>
          </View>
          <View style={styles.todayDivider} />
          <View style={styles.todayItem}>
            <Ionicons name="log-out-outline" size={20} color="#dc2626" />
            <Text style={styles.todayLabel}>Salida</Text>
            <Text style={styles.todayValue}>
              {today?.salida ? formatDateTime(today.salida).split(' ')[1] : '--:--'}
            </Text>
          </View>
        </View>
      </View>

      {/* Monthly Summary */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Resumen del Mes</Text>
        <View style={styles.summaryGrid}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>{summary?.dias_trabajados ?? '--'}</Text>
            <Text style={styles.summaryLabel}>Dias Trabajados</Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryValue, { color: '#dc2626' }]}>
              {summary?.faltas ?? '--'}
            </Text>
            <Text style={styles.summaryLabel}>Faltas</Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryValue, { color: '#d97706' }]}>
              {summary?.tardanzas ?? '--'}
            </Text>
            <Text style={styles.summaryLabel}>Tardanzas</Text>
          </View>
        </View>
      </View>

      {/* Mark Attendance Button */}
      <TouchableOpacity
        style={[styles.markButton, marking && styles.markButtonDisabled]}
        onPress={handleMark}
        disabled={marking}
        activeOpacity={0.8}
      >
        <Ionicons name="finger-print" size={24} color="#ffffff" />
        <Text style={styles.markButtonText}>
          {marking ? 'Registrando...' : 'Marcar Asistencia'}
        </Text>
      </TouchableOpacity>

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
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
  calendarHeader: {
    flexDirection: 'row',
  },
  calendarWeekday: {
    flex: 1,
    textAlign: 'center',
    fontSize: 12,
    fontWeight: '600',
    color: '#9ca3af',
    marginBottom: 8,
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  calendarCell: {
    width: '14.28%',
    aspectRatio: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  calendarDay: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  calendarDayToday: {
    backgroundColor: TEAL,
  },
  calendarDayText: {
    fontSize: 13,
    color: '#374151',
  },
  calendarDayTextToday: {
    color: '#ffffff',
    fontWeight: '700',
  },
  todayRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  todayItem: {
    flex: 1,
    alignItems: 'center',
  },
  todayDivider: {
    width: 1,
    height: 40,
    backgroundColor: '#e5e7eb',
  },
  todayLabel: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 4,
  },
  todayValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    marginTop: 2,
  },
  summaryGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  summaryItem: {
    alignItems: 'center',
  },
  summaryValue: {
    fontSize: 24,
    fontWeight: '800',
    color: TEAL,
  },
  summaryLabel: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 4,
  },
  markButton: {
    flexDirection: 'row',
    backgroundColor: TEAL,
    marginHorizontal: 16,
    marginTop: 20,
    borderRadius: 12,
    paddingVertical: 16,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 10,
  },
  markButtonDisabled: {
    opacity: 0.7,
  },
  markButtonText: {
    color: '#ffffff',
    fontSize: 17,
    fontWeight: '700',
  },
});
