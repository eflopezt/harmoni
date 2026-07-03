import React from 'react';
import { View, ActivityIndicator, Text, StyleSheet } from 'react-native';

const TEAL = '#0f766e';

export default function LoadingSpinner({ message = 'Cargando...' }) {
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color={TEAL} />
      {message ? <Text style={styles.message}>{message}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8fafc',
  },
  message: {
    marginTop: 12,
    fontSize: 14,
    color: '#6b7280',
  },
});
