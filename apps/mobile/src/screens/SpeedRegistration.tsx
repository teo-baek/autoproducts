import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image, TextInput, Alert, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Print from 'expo-print';
import { supabase } from '../lib/supabase';
type SlotIndex = 0 | 1 | 2 | 3;
const SLOT_LABELS = ['정면', '후면', '디테일 1', '디테일 2'];

export default function SpeedRegistration() {
  const [images, setImages] = useState<(string | null)[]>([null, null, null, null]);
  const [price, setPrice] = useState<string>('');
  const priceInputRef = useRef<TextInput>(null);

  const handleSlotPress = (index: SlotIndex) => {
    Alert.alert(
      `${SLOT_LABELS[index]} 사진 추가`,
      '사진을 가져올 방식을 선택하세요.',
      [
        { text: '카메라 촬영', onPress: () => pickImage('camera', index) },
        { text: '갤러리에서 선택', onPress: () => pickImage('gallery', index) },
        { text: '취소', style: 'cancel' },
      ]
    );
  };

  const pickImage = async (source: 'camera' | 'gallery', index: SlotIndex) => {
    let result;
    if (source === 'camera') {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('권한 필요', '카메라 접근 권한이 필요합니다.');
        return;
      }
      result = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        quality: 0.8,
      });
    } else {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('권한 필요', '갤러리 접근 권한이 필요합니다.');
        return;
      }
      result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.8,
      });
    }

    if (!result.canceled) {
      const newImages = [...images];
      newImages[index] = result.assets[0].uri;
      setImages(newImages);
      
      // 첫 번째(정면) 사진을 등록했을 때 단가 입력창으로 포커스 이동 유도
      if (index === 0) {
        setTimeout(() => {
          priceInputRef.current?.focus();
        }, 500);
      }
    }
  };

  const clearSlot = (index: SlotIndex) => {
    const newImages = [...images];
    newImages[index] = null;
    setImages(newImages);
  };

  const saveAndPrint = async () => {
    const hasAnyImage = images.some(uri => uri !== null);
    if (!hasAnyImage || !price) {
      Alert.alert('입력 누락', '최소 1장의 사진과 단가를 입력해주세요.');
      return;
    }

    const numericPrice = parseInt(price.replace(/[^0-9]/g, ''), 10);
    const skuCode = `SKU-${Date.now().toString().slice(-6)}`;

    // QR 인쇄용 HTML
    const html = `
      <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0, user-scalable=no" />
          <style>
            body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 10px; margin: 0 auto; width: 200px; text-align: center; }
            .price { font-size: 28px; font-weight: bold; margin: 10px 0; }
            .sku { font-size: 14px; color: #333; margin-bottom: 10px; }
            .qr-box { width: 100px; height: 100px; background-color: #000; margin: 0 auto; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 10px;}
          </style>
        </head>
        <body>
          <div class="price">${numericPrice.toLocaleString()} 원</div>
          <div class="sku">${skuCode}</div>
          <div class="qr-box">[QR CODE<br/>${skuCode}]</div>
        </body>
      </html>
    `;

    try {
      // 1. Supabase products 테이블 Insert
      const { data: productData, error: productError } = await supabase
        .from('products')
        .insert([{
          p_number: skuCode,
          name: `도매 신상품 (${skuCode})`,
          price: numericPrice,
          main_image_url: images.find(img => img !== null) || ''
        }])
        .select()
        .single();

      if (productError) throw productError;

      // 2. Supabase product_skus 테이블 Insert (기본 가상 재고 50개 할당)
      const { error: skuError } = await supabase
        .from('product_skus')
        .insert([{
          product_id: productData.id,
          color: 'Free',
          size: 'Free',
          allocated_stock: 50,
        }]);

      if (skuError) throw skuError;

      // 3. 물리적 프린트
      await Print.printAsync({ html });
      
      // 인쇄 완료 후 폼 초기화 (무한 루프)
      setImages([null, null, null, null]);
      setPrice('');
      Alert.alert('저장 완료', 'DB 저장 및 라벨 인쇄가 완료되었습니다.\n다음 상품을 등록해주세요.');
    } catch (error) {
      console.error(error);
      Alert.alert('저장 실패', 'DB 연동 또는 출력 중 오류가 발생했습니다.');
    }
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container} 
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>⚡ 다중 컷 상품 등록</Text>
          <Text style={styles.headerSubtitle}>원하는 슬롯 터치 ➔ 단가 입력 ➔ QR 출력</Text>
        </View>

        <View style={styles.carouselSection}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.carouselContainer}>
            {images.map((uri, idx) => {
              const index = idx as SlotIndex;
              return (
                <View key={index} style={styles.slotWrapper}>
                  {uri ? (
                    <View style={styles.imagePreviewContainer}>
                      <Image source={{ uri }} style={styles.imagePreview} />
                      <TouchableOpacity style={styles.clearButton} onPress={() => clearSlot(index)}>
                        <Text style={styles.clearText}>삭제</Text>
                      </TouchableOpacity>
                      <View style={styles.badge}>
                        <Text style={styles.badgeText}>{SLOT_LABELS[index]}</Text>
                      </View>
                    </View>
                  ) : (
                    <TouchableOpacity style={styles.emptySlot} onPress={() => handleSlotPress(index)}>
                      <Text style={styles.emptyIcon}>+</Text>
                      <Text style={styles.emptyText}>{SLOT_LABELS[index]}</Text>
                    </TouchableOpacity>
                  )}
                </View>
              );
            })}
          </ScrollView>
        </View>

        <View style={styles.formSection}>
          <Text style={styles.label}>도매 단가 입력</Text>
          <TextInput
            ref={priceInputRef}
            style={styles.input}
            placeholder="숫자만 입력하세요 (예: 35000)"
            keyboardType="number-pad"
            value={price}
            onChangeText={setPrice}
            onSubmitEditing={saveAndPrint}
            returnKeyType="done"
          />
        </View>

        <TouchableOpacity 
          style={[styles.saveButton, (!images.some(u => u !== null) || !price) && styles.saveButtonDisabled]} 
          onPress={saveAndPrint}
          disabled={!images.some(u => u !== null) || !price}
        >
          <Text style={styles.saveButtonText}>💾 저장 및 QR 프린트</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  scrollContent: {
    padding: 20,
    flexGrow: 1,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 30,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#111',
  },
  headerSubtitle: {
    fontSize: 16,
    color: '#666',
    marginTop: 8,
  },
  carouselSection: {
    marginBottom: 30,
  },
  carouselContainer: {
    flexDirection: 'row',
    paddingVertical: 10,
  },
  slotWrapper: {
    marginRight: 15,
  },
  emptySlot: {
    width: 160,
    height: 220,
    backgroundColor: '#f5f5f5',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#ddd',
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyIcon: {
    fontSize: 40,
    color: '#aaa',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 16,
    color: '#555',
    fontWeight: '600',
  },
  imagePreviewContainer: {
    width: 160,
    height: 220,
    borderRadius: 16,
    overflow: 'hidden',
    position: 'relative',
    borderWidth: 1,
    borderColor: '#eee',
  },
  imagePreview: {
    width: '100%',
    height: '100%',
  },
  clearButton: {
    position: 'absolute',
    top: 10,
    right: 10,
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 10,
  },
  clearText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  badge: {
    position: 'absolute',
    bottom: 10,
    left: 10,
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingVertical: 4,
    paddingHorizontal: 12,
    borderRadius: 12,
  },
  badgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  formSection: {
    marginBottom: 30,
  },
  label: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 10,
  },
  input: {
    borderWidth: 2,
    borderColor: '#eee',
    borderRadius: 12,
    padding: 15,
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111',
    backgroundColor: '#fafafa',
  },
  saveButton: {
    backgroundColor: '#000',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
  },
  saveButtonDisabled: {
    backgroundColor: '#ccc',
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 20,
    fontWeight: 'bold',
  },
});
