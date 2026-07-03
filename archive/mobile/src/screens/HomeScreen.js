import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  FlatList,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../context/AuthContext';
import { getAttendanceSummary } from '../api/asistencia';
import { getMyVacationBalance } from '../api/vacaciones';
import { getMyBoletas } from '../api/nominas';
import { formatCurrency } from '../utils/format';
import KPICard from '../components/KPICard';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

const TEAL = '#0f766e';

export default function HomeScreen({ navigation }) {
  const { user } = useAuth();
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState({
    asistencia: '--',
    vacaciones: '--',
    saldo: '--',
    neto: '--',
  });
  const [notifications, setNotifications] = useState([]);

  const fetchData = useCallback(async () => {
    try {
      const [attendance, vacation, boletas] = await Promise.allSettled([
        getAttendanceSummary(),
        getMyVacationBalance(),
        getMyBoletas({ limit: 1 }),
      ]);

      const newKpis = { ...kpis };

      if (attendance.status === 'fulfilled') {
        const a = attendance.value;
        newKpis.asistencia = `${a.dias_trabajados || 0}d`;
      }

      if (vacation.status === 'fulfilled') {
        const v = vacation.value;
        newKpis.vacaciones = `${v.dias_disponibles || 0}d`;
        newKpis.saldo = `${v.dias_disponibles || 0}/${v.dias_total || 30}`;
      }

      if (boletas.status === 'fulfilled') {
        const b = boletas.value;
        const latest = Array.isArray(b) ? b[0] : b.results?.[0];
        if (latest) {
          newKpis.neto = formatCurrency(latest.neto || latest.total_neto || 0);
        }
      }

      setKpis(newKpis);
    } catch (_) {
      // Silently handle — KPIs will show defaults
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

  const firstName = user?.nombre?.split(' ')[0]
    || user?.first_name
    || user?.username
    || 'Usuario';

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={TEAL} />}
    >
      {/* Welcome Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>Hola, {firstName}</Text>
          <Text style={styles.subtitle}>Bienvenido a Harmoni</Text>
        </View>
        <TouchableOpacity
          style={styles.bellButton}
          onPress={() => navigation.navigate('Notificaciones')}
        >
          <Ionicons name="notifications-outline" size={24} color={TEAL} />
        </TouchableOpacity>
      </View>

      {/* KPI Cards */}
      <View style={styles.kpiGrid}>
        <KPICard icon="calendar" color="#0f766e" value={kpis.asistencia} label="Asistencia" />
        <KPICard icon="sunny" color="#d97706" value={kpis.vacaciones} label="Vacaciones" />
        <KPICard icon="time" color="#7c3aed" value={kpis.saldo} label="Saldo Vac." />
        <KPICard icon="cash" color="#059669" value={kpis.neto} label="Ultimo Neto" />
      </View>

      {/* Quick Actions */}
      <Text style={styles.sectionTitle}>Acciones Rapidas</Text>
      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => navigation.navigate('Asistencia')}
        >
          <View style={[styles.actionIcon, { backgroundColor: '#ccfbf1' }]}>
            <Ionicons name="finger-print" size={24} color={TEAL} />
          </View>
          <Text style={styles.actionLabel}>Marcar{'\n'}Asistencia</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => navigation.navigate('Vacaciones')}
        >
          <View style={[styles.actionIcon, { backgroundColor: '#fef3c7' }]}>
            <Ionicons name="airplane" size={24} color="#d97706" />
          </View>
          <Text style={styles.actionLabel}>Pedir{'\n'}Vacaciones</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => navigation.navigate('Boletas')}
        >
          <View style={[styles.actionIcon, { backgroundColor: '#d1fae5' }]}>
            <Ionicons name="document-text" size={24} color="#059669" />
          </View>
          <Text style={styles.actionLabel}>Ver{'\n'}Boletas</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => navigation.navigate('Perfil')}
        >
          <View style={[styles.actionIcon, { backgroundColor: '#ede9fe' }]}>
            <Ionicons name="person" size={24} color="#7c3aed" />
          </View>
          <Text style={styles.actionLabel}>Mi{'\n'}Perfil</Text>
        </TouchableOpacity>
      </View>

      {/* Recent Notifications */}
      <Text style={styles.sectionTitle}>Notificaciones Recientes</Text>
      {notifications.length === 0 ? (
        <View style={styles.emptyNotifications}>
          <Ionicons name="checkmark-circle-outline" size={32} color="#9ca3af" />
          <Text style={styles.emptyText}>No hay notificaciones nuevas</Text>
        </View>
      ) : (
        notifications.slice(0, 5).map((notif, idx) => (
          <View key={notif.id || idx} style={styles.notifItem}>
            <View style={[styles.notifDot, !notif.leido && styles.notifDotUnread]} />
            <View style={styles.notifContent}>
              <Text style={styles.notifTitle}>{notif.titulo}</Text>
              <Text style={styles.notifMessage} numberOfLines={2}>{notif.mensaje}</Text>
            </View>
          </View>
        ))
      )}

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  greeting: {
    fontSize: 24,
    fontWeight: '800',
    color: '#111827',
  },
  subtitle: {
    fontSize: 14,
    color: '#6b7280',
    marginTop: 2,
  },
  bellButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#f0fdfa',
    justifyContent: 'center',
    alignItems: 'center',
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    paddingHorizontal: 20,
    marginTop: 24,
    marginBottom: 12,
  },
  actionsRow: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    justifyContent: 'space-between',
  },
  actionButton: {
    flex: 1,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  actionIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 6,
  },
  actionLabel: {
    fontSize: 11,
    color: '#374151',
    textAlign: 'center',
    fontWeight: '600',
    lineHeight: 15,
  },
  emptyNotifications: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  emptyText: {
    color: '#9ca3af',
    fontSize: 13,
    marginTop: 8,
  },
  notifItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
  },
  notifDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#d1d5db',
    marginTop: 6,
    marginRight: 12,
  },
  notifDotUnread: {
    backgroundColor: TEAL,
  },
  notifContent: {
    flex: 1,
  },
  notifTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  notifMessage: {
    fontSize: 13,
    color: '#6b7280',
    marginTop: 2,
  },
});
