# Clickable Playlist Features

## New Features Added

### 1. Clickable Playlist Titles
- **What**: Playlist titles are now clickable and open the playlist folder in file explorer
- **Visual feedback**: 
  - Hover effect with blue glow background
  - Cursor changes to pointer
  - Color changes to blue on hover
- **Tooltip**: Shows "Open in explorer" on hover
- **Cross-platform**: Works on Windows, macOS, and Linux

### 2. Open in Browser Icon
- **What**: Small external link icon next to each playlist title
- **Function**: Opens the YouTube playlist in a new browser tab
- **Visual**: Subtle gray icon that turns blue on hover
- **Tooltip**: Shows "Open playlist in YouTube" on hover

## Implementation Details

### Backend API
**New Endpoint**: `POST /api/playlists/{playlist_id}/open-folder`

```python
@router.post("/{playlist_id}/open-folder")
async def open_playlist_folder(playlist_id: int, db: Session = Depends(get_db)):
    """Open playlist folder in file explorer"""
    # Cross-platform folder opening:
    # - Windows: os.startfile()
    # - macOS: subprocess.run(["open", folder])
    # - Linux: subprocess.run(["xdg-open", folder])
```

**Response**:
```json
{
  "message": "Folder opened successfully",
  "path": "/path/to/playlist/folder"
}
```

**Error Handling**:
- 404 if playlist not found
- 404 if playlist folder doesn't exist
- 500 if system can't open folder

### Frontend Changes

#### Grid View
```tsx
<h3 
  className="cursor-pointer hover:text-blue-600 transition-colors group"
  onClick={() => openFolder.mutate(playlist.id)}
  title="Open in explorer"
>
  <span className="group-hover:bg-blue-50 px-2 py-1 rounded">
    {playlist.title}
  </span>
</h3>
<button
  onClick={() => window.open(playlist.url, '_blank')}
  title="Open playlist in YouTube"
>
  <ExternalLink className="w-4 h-4" />
</button>
```

#### List View
```tsx
<h3 
  onClick={(e) => {
    e.stopPropagation() // Don't trigger row expansion
    openFolder.mutate(playlist.id)
  }}
  title="Open in explorer"
>
  {playlist.title}
</h3>
```

### API Service
```typescript
export const playlistsApi = {
  // ... existing methods
  openFolder: (id: number) => api.post<{ message: string; path: string }>(`/playlists/${id}/open-folder`),
}
```

### Mutation Hook
```typescript
const openFolder = useMutation({
  mutationFn: (id: number) => playlistsApi.openFolder(id),
  onError: (error: any) => {
    alert(`Could not open folder: ${error.response?.data?.detail || error.message}`)
  },
})
```

## User Experience

### Visual Feedback
1. **Hover State**: Title background glows with subtle blue highlight
2. **Cursor**: Changes to pointer to indicate clickability
3. **Color**: Text color shifts to blue on hover
4. **Icon**: External link icon appears next to title

### Interaction
1. **Click Title**: Opens playlist folder in default file manager
2. **Click Icon**: Opens YouTube playlist in new browser tab
3. **Error Handling**: Shows alert if folder can't be opened

### Accessibility
- **Tooltips**: Clear descriptions of what each element does
- **Keyboard**: Can be accessed via keyboard navigation
- **Screen readers**: Proper ARIA labels and semantic HTML

## Cross-Platform Support

### Windows
- Uses `os.startfile(folder_path)` to open in Windows Explorer
- Works with all Windows versions

### macOS
- Uses `subprocess.run(["open", folder_path])` to open in Finder
- Native macOS behavior

### Linux
- Uses `subprocess.run(["xdg-open", folder_path])` to open in default file manager
- Works with GNOME, KDE, XFCE, and other desktop environments

## Error Scenarios

### Folder Not Found
- **Cause**: Playlist exists in database but folder was deleted/moved
- **Response**: 404 error with clear message
- **User Experience**: Alert explaining the issue

### Permission Issues
- **Cause**: System doesn't have permission to open folder
- **Response**: 500 error with system error details
- **User Experience**: Alert with error message

### Playlist Not Found
- **Cause**: Playlist ID doesn't exist in database
- **Response**: 404 error
- **User Experience**: Alert explaining playlist not found

## Future Enhancements

### Potential Improvements
1. **Context Menu**: Right-click for more options (copy path, open in terminal, etc.)
2. **Keyboard Shortcuts**: Ctrl+O to open folder, Ctrl+B to open in browser
3. **Folder Status**: Visual indicator if folder exists/doesn't exist
4. **Recent Folders**: Quick access to recently opened folders
5. **Custom File Manager**: Option to use specific file manager on Linux

### Settings Integration
Could add settings for:
- Default file manager on Linux
- Whether to open in new window or existing window
- Keyboard shortcuts customization

## Testing

### Manual Testing
1. **Grid View**: Click playlist title → folder opens
2. **List View**: Click playlist title → folder opens (doesn't expand row)
3. **Browser Icon**: Click icon → YouTube opens in new tab
4. **Hover Effects**: Verify visual feedback works
5. **Error Cases**: Test with non-existent folders

### Cross-Platform Testing
- Test on Windows, macOS, and Linux
- Verify correct file manager opens on each platform
- Test error handling on each platform

The features provide intuitive access to both local files and the original YouTube playlist, significantly improving the user workflow for managing downloaded content.