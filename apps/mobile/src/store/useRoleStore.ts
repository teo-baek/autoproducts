import { create } from 'zustand';

interface RoleState {
  role: 'wholesaler' | 'retailer';
  toggleRole: () => void;
}

export const useRoleStore = create<RoleState>((set) => ({
  role: 'wholesaler', // 기본값: 도매상
  toggleRole: () =>
    set((state) => ({
      role: state.role === 'wholesaler' ? 'retailer' : 'wholesaler',
    })),
}));
