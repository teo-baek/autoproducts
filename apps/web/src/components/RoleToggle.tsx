'use client';

import { useRoleStore } from '@/store/useRoleStore';

export default function RoleToggle() {
  const { role, toggleRole } = useRoleStore();

  return (
    <div className="fixed top-4 right-4 z-50">
      <button
        onClick={toggleRole}
        className="px-6 py-3 bg-black/80 backdrop-blur-md text-white rounded-full shadow-2xl font-bold border border-white/10 hover:bg-black transition-colors"
      >
        {role === 'wholesaler' ? '🏢 도매상 모드' : '🛒 소매상 모드'}
      </button>
    </div>
  );
}
