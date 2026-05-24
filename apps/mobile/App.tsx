import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View, TouchableOpacity, SafeAreaView } from 'react-native';
import { useState } from 'react';
import { useRoleStore } from './src/store/useRoleStore';
import PosTerminal from './src/screens/PosTerminal';
import SpeedRegistration from './src/screens/SpeedRegistration';

export default function App() {
  const role = useRoleStore((state) => state.role);
  const toggleRole = useRoleStore((state) => state.toggleRole);
  const [activeTab, setActiveTab] = useState<'pos' | 'registration'>('pos');

  return (
    <SafeAreaView style={styles.container}>
      {/* 도매상 모드일 때만 상단 탭 렌더링 */}
      {role === 'wholesaler' && (
        <View style={styles.tabContainer}>
          <TouchableOpacity 
            style={[styles.tabButton, activeTab === 'pos' && styles.activeTab]}
            onPress={() => setActiveTab('pos')}
          >
            <Text style={[styles.tabText, activeTab === 'pos' && styles.activeTabText]}>💳 결제 POS</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.tabButton, activeTab === 'registration' && styles.activeTab]}
            onPress={() => setActiveTab('registration')}
          >
            <Text style={[styles.tabText, activeTab === 'registration' && styles.activeTabText]}>📦 초고속 등록</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* 메인 뷰 분기 */}
      <View style={styles.mainContent}>
        {role === 'wholesaler' ? (
          activeTab === 'pos' ? <PosTerminal /> : <SpeedRegistration />
        ) : (
          <View style={styles.retailerContainer}>
            <Text style={styles.mainText}>소매상 카탈로그 화면 (개발 예정)</Text>
          </View>
        )}
      </View>

      {/* 마법의 권한 스위치 (개발자용 UI 위에 오버레이) */}
      <TouchableOpacity style={styles.toggleButton} onPress={toggleRole}>
        <Text style={styles.toggleText}>
          {role === 'wholesaler' ? '🏢 도매상 모드' : '🛒 소매상 모드'}
        </Text>
      </TouchableOpacity>
      
      <StatusBar style="auto" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  tabContainer: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 10,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderColor: '#eee',
  },
  tabButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 8,
    marginHorizontal: 5,
    backgroundColor: '#f5f5f5',
  },
  activeTab: {
    backgroundColor: '#000',
  },
  tabText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#666',
  },
  activeTabText: {
    color: '#fff',
  },
  mainContent: {
    flex: 1,
  },
  retailerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  toggleButton: {
    position: 'absolute',
    top: 50,
    right: 20,
    backgroundColor: '#333',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
  },
  toggleText: {
    color: 'white',
    fontWeight: 'bold',
  },
  mainText: {
    fontSize: 24,
    fontWeight: 'bold',
  }
});
