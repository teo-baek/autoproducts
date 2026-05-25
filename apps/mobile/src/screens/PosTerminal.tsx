import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, Image, Alert } from 'react-native';
import * as Print from 'expo-print';
import { supabase } from '../lib/supabase';
import { useCartStore, CartItem } from '../store/useCartStore';

export default function PosTerminal() {
  const { cart, addToCart, removeFromCart, clearCart } = useCartStore();
  const [products, setProducts] = React.useState<any[]>([]);

  React.useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    const { data, error } = await supabase
      .from('products')
      .select('id, name, price, main_image_url, product_skus(id, allocated_stock)');
    if (data) {
      setProducts(data);
    }
  };

  const handleAllocateStock = async (skuId: string) => {
    Alert.prompt(
      '라이브 락 부여',
      '추가로 할당할 가상 재고 수량을 입력하세요.',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '할당',
          onPress: async (text) => {
            const num = parseInt(text || '0', 10);
            if (num > 0) {
              const { error } = await supabase.rpc('increment_allocated_stock', { p_sku_id: skuId, qty: num });
              if (!error) fetchProducts();
            }
          }
        }
      ],
      'plain-text',
      '50'
    );
  };

  const totalAmount = cart.reduce((sum, item) => sum + item.price * item.qty, 0);

  const printReceipt = async () => {
    if (cart.length === 0) {
      Alert.alert('오류', '장바구니가 비어 있습니다.');
      return;
    }

    let itemsHtml = '';
    cart.forEach(item => {
      itemsHtml += `
        <tr>
          <td style="padding: 5px 0;">${item.name}</td>
          <td style="text-align: right;">${item.qty}</td>
          <td style="text-align: right;">${(item.price * item.qty).toLocaleString()}원</td>
        </tr>
      `;
    });

    const html = `
      <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0, user-scalable=no" />
          <style>
            body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 20px; font-size: 14px; width: 300px; margin: 0 auto; color: #000; }
            h1 { text-align: center; font-size: 24px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            th { border-bottom: 1px solid #000; padding-bottom: 5px; text-align: left; }
            .total { font-size: 18px; font-weight: bold; text-align: right; border-top: 2px solid #000; padding-top: 10px; }
            .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
          </style>
        </head>
        <body>
          <h1>🧾 AutoProducts</h1>
          <div style="text-align: center; margin-bottom: 20px;">동대문 도매상 영수증</div>
          <table>
            <thead>
              <tr>
                <th>품명</th>
                <th style="text-align: right;">수량</th>
                <th style="text-align: right;">금액</th>
              </tr>
            </thead>
            <tbody>
              ${itemsHtml}
            </tbody>
          </table>
          <div class="total">합계: ${totalAmount.toLocaleString()} 원</div>
          <div class="footer">이용해 주셔서 감사합니다.</div>
        </body>
      </html>
    `;

    try {
      await Print.printAsync({
        html,
        printerUrl: undefined, // iOS/Android OS 기본 인쇄 팝업 호출
      });
      // 결제 완료 후 로컬 장바구니 비우기 및 상품 재고는 무한대이므로 별도 차감 없음 (도매상)
      clearCart();
    } catch (error) {
      console.error('인쇄 실패:', error);
      Alert.alert('인쇄 오류', '영수증 인쇄 중 문제가 발생했습니다.');
    }
  };

  const renderProduct = ({ item }: { item: any }) => {
    const skuId = item.product_skus?.[0]?.id;
    const allocated = item.product_skus?.[0]?.allocated_stock || 0;

    return (
      <View style={styles.productCard}>
        <Image source={{ uri: item.main_image_url || 'https://via.placeholder.com/150' }} style={styles.productImage} />
        <Text style={styles.productName}>{item.name}</Text>
        <Text style={styles.productPrice}>{item.price.toLocaleString()} 원</Text>
        <TouchableOpacity 
          style={styles.addButton}
          onPress={() => addToCart({ id: item.id, name: item.name, price: item.price, qty: 1 })}
        >
          <Text style={styles.addButtonText}>🛒 담기</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.lockButton}
          onPress={() => skuId && handleAllocateStock(skuId)}
        >
          <Text style={styles.lockButtonText}>🔒 락 부여 ({allocated}개)</Text>
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* 좌측 패널 (7) */}
      <View style={styles.leftPanel}>
        <Text style={styles.headerTitle}>🏷️ 매장 상품 매대</Text>
        <FlatList
          data={products}
          renderItem={renderProduct}
          keyExtractor={(item) => item.id}
          numColumns={3}
          contentContainerStyle={styles.listContainer}
        />
      </View>

      {/* 우측 패널 (3) */}
      <View style={styles.rightPanel}>
        <Text style={styles.headerTitle}>🛒 계산대</Text>
        
        <View style={styles.cartList}>
          {cart.length === 0 ? (
            <Text style={styles.emptyText}>장바구니가 비어 있습니다.</Text>
          ) : (
            cart.map((item) => (
              <View key={item.id} style={styles.cartItem}>
                <View style={styles.cartItemInfo}>
                  <Text style={styles.cartItemName}>{item.name}</Text>
                  <Text style={styles.cartItemPrice}>{item.price.toLocaleString()}원 x {item.qty}</Text>
                </View>
                <TouchableOpacity onPress={() => removeFromCart(item.id)}>
                  <Text style={styles.deleteIcon}>❌</Text>
                </TouchableOpacity>
              </View>
            ))
          )}
        </View>

        <View style={styles.cartFooter}>
          <Text style={styles.totalText}>총 결제: {totalAmount.toLocaleString()} 원</Text>
          <View style={styles.buttonRow}>
            <TouchableOpacity style={styles.clearButton} onPress={clearCart}>
              <Text style={styles.buttonText}>비우기</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.printButton} onPress={printReceipt}>
              <Text style={styles.buttonText}>🖨️ 결제/인쇄</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'row', // 핵심: 7:3 가로 분할
    backgroundColor: '#f5f5f5',
  },
  leftPanel: {
    flex: 7,
    padding: 20,
    backgroundColor: '#fff',
  },
  rightPanel: {
    flex: 3,
    backgroundColor: '#fafafa',
    borderLeftWidth: 1,
    borderColor: '#eee',
    padding: 20,
    justifyContent: 'space-between',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    color: '#111',
  },
  listContainer: {
    paddingBottom: 20,
  },
  productCard: {
    flex: 1,
    margin: 8,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 12,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 5,
    elevation: 2,
    alignItems: 'center',
  },
  productImage: {
    width: '100%',
    height: 120,
    borderRadius: 8,
    marginBottom: 10,
  },
  productName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  productPrice: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
  },
  addButton: {
    backgroundColor: '#000',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    width: '100%',
    alignItems: 'center',
  },
  addButtonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  lockButton: {
    backgroundColor: '#ff4444',
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 8,
    width: '100%',
    alignItems: 'center',
    marginTop: 5,
  },
  lockButtonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  cartList: {
    flex: 1,
  },
  emptyText: {
    color: '#999',
    textAlign: 'center',
    marginTop: 50,
  },
  cartItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderColor: '#eee',
  },
  cartItemInfo: {
    flex: 1,
  },
  cartItemName: {
    fontSize: 16,
    fontWeight: '500',
    color: '#222',
  },
  cartItemPrice: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  deleteIcon: {
    fontSize: 18,
    padding: 10,
  },
  cartFooter: {
    borderTopWidth: 2,
    borderColor: '#111',
    paddingTop: 20,
  },
  totalText: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 20,
    color: '#111',
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  clearButton: {
    flex: 1,
    backgroundColor: '#666',
    padding: 15,
    borderRadius: 8,
    marginRight: 10,
    alignItems: 'center',
  },
  printButton: {
    flex: 2,
    backgroundColor: '#000',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16,
  },
});
