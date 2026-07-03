import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { timeAgo } from '../utils/format';
import EmptyState from '../components/EmptyState';

const TEAL = '#0f766e';

// Placeholder notifications until the API is wired up
const DEMO_NOTIFICATIONS = [
  {
    id: '1',
    titulo: 'Boleta disponible',
    mensaje: 'Tu boleta del periodo Marzo 2026 esta disponible para descarga.',
    tipo: 'boleta',
    leido: false,
    created_at: new Date(Date.now() - 2 * 3600000).toISOString(),
  },
  {
    id: '2',
    titulo: 'Vacaciones aprobadas',
    mensaje: 'Tu solicitud de vacaciones del 01/04 al 15/04 fue aprobada.',
    tipo: 'vacaciones',
    leido: false,
    created_at: new Date(Date.now() - 24 * 3600000).toISOString(),
  },
  {
    id: '3',
    titulo: 'Recordatorio de asistencia',
    mensaje: 'No olvides marcar tu salida hoy.',
    tipo: 'asistencia',
    leido: true,
    created_at: new Date(Date.now() - 48 * 3600000).toISOString(),
  },
];

const ICON_MAP = {
  boleta: 'document-text',
  vacaciones: 'sunny',
  asistencia: 'finger-print',
  default: 'notifications',
};

const COLOR_MAP = {
  boleta: '#059669',
  vacaciones: '#d97706',
  asistencia: TEAL,
  default: '#6b7280',
};

export default function NotificacionesScreen() {
  const [notifications, setNotifications] = useState(DEMO_NOTIFICATIONS);
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    // TODO: fetch from API when endpoint is available
    // const data = await apiClient.get('/mi-portal/api/notificaciones/');
    setRefreshing(false);
  }, []);

  const markAsRead = (id) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, leido: true } : n)),
    );
  };

  const renderNotification = ({ item }) => {
    const icon = ICON_MAP[item.tipo] || ICON_MAP.default;
    const color = COLOR_MAP[item.tipo] || COLOR_MAP.default;

    return (
      <TouchableOpacity
        style={[styles.item, !item.leido && styles.itemUnread]}
        onPress={() => markAsRead(item.id)}
        activeOpacity={0.7}
      >
        <View style={[styles.iconCircle, { backgroundColor: `${color}15` }]}>
          <Ionicons name={icon} size={20} color={color} />
        </View>
        <View style={styles.content}>
          <View style={styles.titleRow}>
            <Text style={[styles.title, !item.leido && styles.titleUnread]}>
              {item.titulo}
            </Text>
            {!item.leido && <View style={styles.unreadDot} />}
          </View>
          <Text style={styles.message} numberOfLines={2}>
            {item.mensaje}
          </Text>
          <Text style={styles.time}>{timeAgo(item.created_at)}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <FlatList
      style={styles.container}
      data={notifications}
      keyExtractor={(item) => item.id}
      renderItem={renderNotification}
      contentContainerStyle={notifications.length === 0 ? styles.emptyContainer : undefined}
      ListEmptyComponent={
        <EmptyState
          icon="notifications-off-outline"
          message="No tienes notificaciones."
        />
      }
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={TEAL} />
      }
    />
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  item: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
  },
  itemUnread: {
    backgroundColor: '#f0fdfa',
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  content: {
    flex: 1,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    flex: 1,
  },
  titleUnread: {
    color: '#111827',
    fontWeight: '700',
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: TEAL,
    marginLeft: 8,
  },
  message: {
    fontSize: 13,
    color: '#6b7280',
    marginTop: 4,
    lineHeight: 18,
  },
  time: {
    fontSize: 11,
    color: '#9ca3af',
    marginTop: 4,
  },
});
