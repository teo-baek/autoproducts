import 'react-native-url-polyfill/auto';
import { createClient } from '@supabase/supabase-js';

// Note: For Android Emulator, localhost is 10.0.2.2. For iOS it's 127.0.0.1.
const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || 'http://10.0.2.2:54321';
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRlZmF1bHQiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTY5MzU1MjAwMCwiZXhwIjoxOTk3NjMyMDAwfQ.XYZ123_MOCK_KEY_FOR_LOCAL_DEV';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
