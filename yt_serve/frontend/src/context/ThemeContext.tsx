import React, { createContext, useContext, useEffect } from 'react'

interface ThemeContextType {
  darkMode: boolean
  toggleDarkMode: () => void
  setDarkMode: (val: boolean) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  useEffect(() => {
    // Unconditionally enforce dark mode and migrate any legacy 'false' localStorage
    document.documentElement.classList.add('dark')
    try {
      localStorage.setItem('darkMode', 'true')
    } catch (e) {
      console.error('Failed to save darkMode in localStorage', e)
    }
  }, [])

  const toggleDarkMode = () => {
    // Locked in Dark Mode
  }

  const setDarkMode = (_val: boolean) => {
    // Locked in Dark Mode
  }

  return (
    <ThemeContext.Provider value={{ darkMode: true, toggleDarkMode, setDarkMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
