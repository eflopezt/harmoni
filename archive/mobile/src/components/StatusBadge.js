import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const STATUS_COLORS = {
  APROBADA: { bg: '#d1fae5', text: '#065f46' },
  APROBADO: { bg: '#d1fae5', text: '#065f46' },
  PAGADA: { bg: '#d1fae5', text: '#065f46' },
  PAGADO: { bg: '#d1fae5', text: '#065f46' },
  PENDIENTE: { bg: '#fef3c7', text: '#92400e' },
  EN_PROCESO: { bg: '#dbeafe', text: '#1e40af' },
  RECHAZADA: { bg: '#fecaca', text: '#991b1b' },
  RECHAZADO: { bg: '#fecaca', text: '#991b1b' },
  CANCELADA: { bg: '#f3f4f6', text: '#374151' },
  CANCELADO: { bg: '#f3f4f6', text: '#374151' },
};

const DEFAULT_COLORS = { bg: '#f3f4f6', text: '#374151' };

export default function StatusBadge({ status }) {
  const key = (status || '').toUpperCase().replace(/\s+/g, '_');
  const colors = STATUS_COLORS[key] || DEFAULT_COLORS;

  const label = (status || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }]}>
      <Text style={[styles.text, { color: colors.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  text: {
    fontSize: 11,
    fontWeight: '700',
  },
});
