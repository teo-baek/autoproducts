import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View, TouchableOpacity } from 'react-native';
import { useRoleStore } from './src/store/useRoleStore';

export default function App() {
  const role = useRoleStore((state) => state.role);
  const toggleRole = useRoleStore((state) => state.toggleRole);

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.toggleButton} onPress={toggleRole}>
        <Text style={styles.toggleText}>
          {role === 'wholesaler' ? '🏢 도매상 모드' : '🛒 소매상 모드'}
        </Text>
      </TouchableOpacity>
      
      <Text style={styles.mainText}>
        {role === 'wholesaler' ? 'POS 터미널 화면 (도매상)' : '카탈로그 화면 (소매상)'}
      </Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
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
