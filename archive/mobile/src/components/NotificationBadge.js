import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export default function NotificationBadge({ count }) {
  if (!count || count <= 0) return null;

  const display = count > 99 ? '99+' : String(count);

  return (
    <View style={styles.badge}>
      <Text style={styles.text}>{display}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    position: 'absolute',
    top: -4,
    right: -6,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#dc2626',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  text: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '800',
  },
});
