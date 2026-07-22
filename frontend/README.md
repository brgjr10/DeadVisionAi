# Dead Vision AI Frontend

## Quick Start

1. **Make sure the backend is running** (in another terminal):
   ```bash
   cd F:\DeadVisionAi\backend
   python main.py
   ```

2. **Start the frontend**:
   ```bash
   cd F:\DeadVisionAi\frontend
   npm install
   npm run dev
   ```

3. **Open your browser** to: http://localhost:3000

## Features

- ✅ Real-time backend status monitoring
- ✅ Live tools listing from your MCP server
- ✅ Chat interface with Dead Vision AI
- ✅ System metrics and activity logging
- ✅ Responsive design with Dead Vision branding
- ✅ Dark/light mode ready

## Backend Integration

The frontend connects to your HAIOS backend at `http://localhost:8000` and provides:
- Status checks for the MCP server integration
- Real-time tool listing (filesystem, shell, SQLite, Brave Search, Context7, Playwright)
- Chat interface that routes requests through your AI pipeline
- Visual feedback on tool usage and processing

## Customization

- Edit `src/App.jsx` to modify the chat interface
- Update `src/App.css` for styling changes
- Modify `tailwind.config.cjs` to adjust the Dead Vision color scheme
- Replace logo assets in the public directory when available

## API Endpoints Used

- `GET /` - Backend health check
- `GET /tools` - Available MCP tools listing
- `POST /chat` - Main chat interface with AI