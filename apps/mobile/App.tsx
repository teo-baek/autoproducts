import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View, TouchableOpacity, SafeAreaView } from 'react-native';
import { useRoleStore } from './src/store/useRoleStore';
import PosTerminal from './src/screens/PosTerminal';

export default function App() {
  const role = useRoleStore((state) => state.role);
  const toggleRole = useRoleStore((state) => state.toggleRole);

  return (
    <SafeAreaView style={styles.container}>
      {role === 'wholesaler' ? (
        <PosTerminal />
      ) : (
        <View style={styles.retailerContainer}>
          <Text style={styles.mainText}>소매상 카탈로그 화면 (개발 예정)</Text>
        </View>
      )}

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
