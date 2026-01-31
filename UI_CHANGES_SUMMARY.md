# UI Changes Summary - January 31, 2026

## Changes Implemented

### 1. **ChatBot Title**
- Changed main title from "CV Chat PoC" to "ChatBot"
- Centered the title at the top of the screen
- Added proper styling with appropriate padding and font weight

### 2. **PDF Attachment Preview**
- PDF files now appear **immediately** as an attachment message when selected
- Shows a 📎 (paperclip) icon with the filename
- No need to wait until "Send" is clicked to see the attachment
- Attachment appears in the chat area as a styled message card

### 3. **Fixed Input Box**
- Input box is now **fixed at the bottom** of the viewport
- Input box stays in place when user scrolls
- Clean sticky positioning with proper z-index

### 4. **Scrollable Chat Area**
- Chat messages area is now scrollable
- Only the message area scrolls while title and input remain fixed
- Smooth scrolling animation when new messages arrive
- Proper viewport height (100vh) layout

### 5. **Centered Responses**
- Assistant responses are now **centered** on the screen
- Response text is center-aligned for better readability
- Max width of 600px for optimal reading experience
- User messages remain right-aligned

## Technical Details

### Files Modified
1. **frontend/src/App.jsx**
   - Updated title to "ChatBot" with className "app-title"
   - Added support for "attachment" message type
   - Moved Upload component to bottom (after chat area)

2. **frontend/src/Upload.jsx**
   - Modified file input onChange to immediately show attachment
   - Sends `{ type: "attachment", filename: ... }` message when file selected

3. **frontend/src/styles.css**
   - Added `.app-title` styling for centered header
   - Modified `.container` to use `height: 100vh` flex layout
   - Made `.chat` scrollable with `overflow-y: auto`
   - Made `.upload` sticky with `position: sticky; bottom: 0`
   - Centered `.assistant-message` and `.assistant-reply`
   - Added `.attachment-message` styling for file attachments
   - Set body `overflow: hidden` to prevent double scrollbars

4. **CHANGELOG.md**
   - Added entry documenting all UI improvements

## Layout Structure

```
┌─────────────────────────────┐
│   ChatBot (title - fixed)   │
├─────────────────────────────┤
│                             │
│   Scrollable Chat Area      │
│   - Attachment messages     │
│   - User messages (right)   │
│   - Bot responses (center)  │
│   - Info/error messages     │
│                             │
│         ↕ (scrolls)          │
│                             │
├─────────────────────────────┤
│  [+] [Input] [Send]         │
│     (fixed at bottom)       │
└─────────────────────────────┘
```

## User Experience Flow

1. **Upload PDF**
   - User clicks the `+` button
   - Selects a PDF file
   - **Attachment immediately appears** in chat with filename
   - No action needed - file is ready to be processed

2. **Send Message**
   - User types in "Ask anything" input box
   - Clicks "Send" button
   - If file was attached, it gets uploaded and processed
   - User's question appears (right-aligned)
   - Bot's response appears below (centered)

3. **Scroll Behavior**
   - New messages auto-scroll into view
   - Smooth animation with offset
   - Input box always visible at bottom
   - Title always visible at top

## Testing the Changes

The dev server is running at: http://localhost:5174 (or check terminal output)

### Test Checklist
- [ ] Title "ChatBot" is centered at top
- [ ] Click `+` and select PDF - attachment should appear immediately
- [ ] Input box stays fixed when scrolling
- [ ] Chat area scrolls independently
- [ ] Bot responses are centered
- [ ] User messages are right-aligned
- [ ] Smooth scroll animation works
- [ ] Layout works on different screen sizes

## Next Steps (Optional)
- Add ability to remove/clear attachment before sending
- Add loading indicator on the attachment while processing
- Add file size validation
- Improve mobile responsiveness
- Add animation when attachment appears
