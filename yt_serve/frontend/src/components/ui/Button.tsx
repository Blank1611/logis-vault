import React from 'react'
import { Loader2 } from 'lucide-react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'warning' | 'success'
  size?: 'sm' | 'md' | 'lg'
  icon?: React.ReactNode
}

export const Button: React.FC<ButtonProps> = ({
  children,
  loading = false,
  variant = 'primary',
  size = 'md',
  icon,
  className = '',
  disabled,
  ...props
}) => {
  const baseClasses = 'font-semibold rounded-lg flex items-center justify-center gap-2 transition-all disabled:cursor-not-allowed'

  const sizeClasses = {
    sm: 'px-2.5 py-1 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  }

  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-400 dark:disabled:bg-gray-600 shadow-sm',
    secondary: 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 disabled:opacity-50',
    danger: 'bg-rose-600 hover:bg-rose-700 text-white disabled:bg-gray-400 dark:disabled:bg-gray-600 shadow-sm',
    ghost: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40',
    warning: 'bg-amber-500 hover:bg-amber-600 text-white disabled:bg-gray-400 shadow-sm',
    success: 'bg-emerald-600 hover:bg-emerald-700 text-white disabled:bg-gray-400 shadow-sm',
  }

  return (
    <button
      disabled={disabled || loading}
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" /> : icon ? <span className="flex-shrink-0">{icon}</span> : null}
      {children}
    </button>
  )
}
