import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image, TextInput, Alert, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Print from 'expo-print';

export default function SpeedRegistration() {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [price, setPrice] = useState<string>('');
  const priceInputRef = useRef<TextInput>(null);

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('권한 필요', '카메라 접근 권한이 필요합니다.');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });

    if (!result.canceled) {
      setImageUri(result.assets[0].uri);
      // 사진 촬영 직후 단가 입력창으로 자동 포커스 이동 (컨베이어 벨트 UX)
      setTimeout(() => {
        priceInputRef.current?.focus();
      }, 500);
    }
  };

  const saveAndPrint = async () => {
    if (!imageUri || !price) {
      Alert.alert('입력 누락', '사진과 단가를 모두 입력해주세요.');
      return;
    }

    const numericPrice = parseInt(price.replace(/[^0-9]/g, ''), 10);
    const skuCode = `SKU-${Date.now().toString().slice(-6)}`; // 임시 고유 바코드

    // QR 인쇄용 HTML (감열지 프린터 최적화)
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
          <!-- 실제 환경에서는 여기에 QR 코드 이미지가 들어갑니다 -->
          <div class="qr-box">[QR CODE<br/>${skuCode}]</div>
        </body>
      </html>
    `;

    try {
      await Print.printAsync({ html });
      // 인쇄 완료 후 폼 초기화 및 다음 촬영 준비 (무한 루프)
      setImageUri(null);
      setPrice('');
      Alert.alert('저장 완료', '상품 등록 및 라벨 인쇄가 완료되었습니다.\n다음 상품을 촬영해주세요.');
    } catch (error) {
      console.error(error);
      Alert.alert('인쇄 실패', '라벨 출력 중 오류가 발생했습니다.');
    }
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container} 
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>⚡ 초고속 상품 등록</Text>
          <Text style={styles.headerSubtitle}>사진 촬영 ➔ 단가 입력 ➔ QR 출력</Text>
        </View>

        <View style={styles.cameraSection}>
          {imageUri ? (
            <View style={styles.imagePreviewContainer}>
              <Image source={{ uri: imageUri }} style={styles.imagePreview} />
              <TouchableOpacity style={styles.retakeButton} onPress={takePhoto}>
                <Text style={styles.retakeText}>다시 촬영</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity style={styles.cameraButton} onPress={takePhoto}>
              <Text style={styles.cameraIcon}>📷</Text>
              <Text style={styles.cameraButtonText}>상품 촬영 (터치)</Text>
            </TouchableOpacity>
          )}
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
          style={[styles.saveButton, (!imageUri || !price) && styles.saveButtonDisabled]} 
          onPress={saveAndPrint}
          disabled={!imageUri || !price}
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
  cameraSection: {
    alignItems: 'center',
    marginBottom: 30,
  },
  cameraButton: {
    width: 250,
    height: 350,
    backgroundColor: '#f5f5f5',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#ddd',
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cameraIcon: {
    fontSize: 50,
    marginBottom: 10,
  },
  cameraButtonText: {
    fontSize: 18,
    color: '#555',
    fontWeight: '600',
  },
  imagePreviewContainer: {
    width: 250,
    height: 350,
    borderRadius: 16,
    overflow: 'hidden',
    position: 'relative',
  },
  imagePreview: {
    width: '100%',
    height: '100%',
  },
  retakeButton: {
    position: 'absolute',
    bottom: 15,
    alignSelf: 'center',
    backgroundColor: 'rgba(0,0,0,0.7)',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 20,
  },
  retakeText: {
    color: '#fff',
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
