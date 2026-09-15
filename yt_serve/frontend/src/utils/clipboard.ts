/**
 * Robust copy-to-clipboard helper that works in both secure contexts (HTTPS/localhost)
 * and non-secure environments (HTTP across LAN IP) using fallback execCommand.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false

  // Try modern Clipboard API if available
  if (typeof navigator !== 'undefined' && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (e) {
      console.warn('navigator.clipboard.writeText failed, falling back to execCommand', e)
    }
  }

  // Fallback using textarea + document.execCommand('copy')
  try {
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.top = '0'
    textArea.style.left = '-9999px'
    textArea.style.opacity = '0'
    textArea.setAttribute('readonly', '')
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    const successful = document.execCommand('copy')
    document.body.removeChild(textArea)
    return successful
  } catch (err) {
    console.error('Failed to copy text to clipboard using execCommand fallback', err)
    return false
  }
}
