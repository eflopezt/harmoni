import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getMyBoletas, downloadBoletaPdf } from '../api/nominas';
import { formatCurrency, formatDate } from '../utils/format';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';

const TEAL = '#0f766e';

export default function BoletasScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [boletas, setBoletas] = useState([]);
  const [downloading, setDownloading] = useState(null);

  const fetchBoletas = useCallback(async () => {
    try {
      const data = await getMyBoletas();
      const list = Array.isArray(data) ? data : data.results || [];
      setBoletas(list);
    } catch (_) {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBoletas();
  }, [fetchBoletas]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchBoletas();
    setRefreshing(false);
  }, [fetchBoletas]);

  const handleDownload = async (boleta) => {
    setDownloading(boleta.id);
    try {
      const periodo = boleta.periodo_label || boleta.periodo || 'boleta';
      const filename = `boleta_${periodo}.pdf`.replace(/\s+/g, '_');
      await downloadBoletaPdf(boleta.id, filename);
    } catch (err) {
      Alert.alert('Error', 'No se pudo descargar la boleta.');
    } finally {
      setDownloading(null);
    }
  };

  const renderBoleta = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View>
          <Text style={styles.periodo}>
            {item.periodo_label || item.periodo || 'Periodo'}
          </Text>
          <Text style={styles.fecha}>
            {formatDate(item.fecha_pago || item.created_at)}
          </Text>
        </View>
        <StatusBadge status={item.estado || 'PAGADA'} />
      </View>

      <View style={styles.cardBody}>
        <View style={styles.amountRow}>
          <Text style={styles.amountLabel}>Neto a Pagar</Text>
          <Text style={styles.amountValue}>
            {formatCurrency(item.neto || item.total_neto || 0)}
          </Text>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Ingresos</Text>
          <Text style={styles.detailValue}>
            {formatCurrency(item.total_ingresos || item.ingresos || 0)}
          </Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Descuentos</Text>
          <Text style={[styles.detailValue, { color: '#dc2626' }]}>
            -{formatCurrency(item.total_descuentos || item.descuentos || 0)}
          </Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.downloadButton}
        onPress={() => handleDownload(item)}
        disabled={downloading === item.id}
        activeOpacity={0.7}
      >
        <Ionicons
          name={downloading === item.id ? 'hourglass-outline' : 'download-outline'}
          size={18}
          color={TEAL}
        />
        <Text style={styles.downloadText}>
          {downloading === item.id ? 'Descargando...' : 'Descargar PDF'}
        </Text>
      </TouchableOpacity>
    </View>
  );

  if (loading) return <LoadingSpinner />;

  return (
    <FlatList
      style={styles.container}
      data={boletas}
      keyExtractor={(item) => String(item.id)}
      renderItem={renderBoleta}
      contentContainerStyle={boletas.length === 0 ? styles.emptyContainer : styles.listContent}
      ListEmptyComponent={
        <EmptyState
          icon="document-text-outline"
          message="No tienes boletas de pago aun."
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
  listContent: {
    padding: 16,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    marginBottom: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  periodo: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  fecha: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 2,
  },
  cardBody: {
    borderTopWidth: 1,
    borderTopColor: '#f3f4f6',
    paddingTop: 12,
  },
  amountRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  amountLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  amountValue: {
    fontSize: 20,
    fontWeight: '800',
    color: TEAL,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  detailLabel: {
    fontSize: 13,
    color: '#6b7280',
  },
  detailValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
  },
  downloadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderTopWidth: 1,
    borderTopColor: '#f3f4f6',
    marginTop: 12,
    paddingTop: 12,
    gap: 6,
  },
  downloadText: {
    color: TEAL,
    fontSize: 14,
    fontWeight: '600',
  },
});
