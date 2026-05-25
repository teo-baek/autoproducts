import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

interface HeaderProps {
  title: string | React.ReactNode;
  subtitle?: string | React.ReactNode;
  onReset?: () => void;
  isResetDisabled?: boolean;
  rightActions?: React.ReactNode;
  transparent?: boolean;
}

export default function Header({ title, subtitle, onReset, isResetDisabled, rightActions, transparent = false }: HeaderProps) {
  return (
    <header className={`px-6 py-4 flex items-center justify-between sticky top-0 z-50 ${transparent ? 'bg-transparent text-white' : 'bg-white border-b border-zinc-200 shadow-sm'}`}>
      <div className="flex items-center gap-4">
        <Link href="/" className={`p-2 -ml-2 rounded-full transition-colors ${transparent ? 'hover:bg-white/20' : 'hover:bg-zinc-100'}`}>
          <ArrowLeft className={`w-6 h-6 ${transparent ? 'text-white' : 'text-zinc-600'}`} />
        </Link>
        <h1 className={`text-xl font-bold flex items-center gap-2 ${transparent ? 'text-white' : 'text-zinc-900'}`}>
          {title}
          {subtitle && <span className={`text-sm font-normal hidden md:inline ${transparent ? 'text-zinc-300' : 'text-zinc-500'}`}>{subtitle}</span>}
        </h1>
      </div>
      
      <div className="flex items-center gap-4">
        {rightActions}
        {onReset && (
          <button 
            type="button" 
            onClick={onReset}
            disabled={isResetDisabled}
            className={`text-sm font-semibold transition-colors flex items-center gap-1 disabled:opacity-50 ${transparent ? 'text-white hover:text-red-400' : 'text-zinc-500 hover:text-red-500'}`}
          >
            초기화
          </button>
        )}
      </div>
    </header>
  );
}
