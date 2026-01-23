# BESS Agent Frontend

Draggable card system frontend application based on React Flow

## Technology Stack

- **React 18** + **TypeScript** - UI framework
- **React Flow** - Node editor and flowchart
- **Tailwind CSS** - Styling system
- **Framer Motion** - Animation library
- **Zustand** - State management
- **Vite** - Build tool

## Project Structure

```
frontend/
├── src/
│   ├── components/        # React components
│   │   ├── flow/          # React Flow components
│   │   ├── ui/            # UI components
│   │   └── layout/        # Layout components
│   ├── pages/             # Page components
│   ├── hooks/             # Custom React hooks
│   ├── store/             # Zustand stores
│   ├── api/               # API client and functions
│   ├── types/             # TypeScript type definitions
│   ├── config/            # Configuration files
│   └── utils/             # Utility functions
├── public/
└── package.json
```

## Key Features

### Modular Architecture
- **No hardcoding**: All configuration in `src/config/`
- **Type-safe**: Full TypeScript coverage
- **Small files**: Each file < 1000 lines
- **Separation of concerns**: Clear module boundaries

### Configuration
- **App Config** (`src/config/app.config.ts`): Application settings
- **Constants** (`src/config/constants.ts`): All constants centralized
- **Environment variables**: Support for `.env` files

### State Management
- **Zustand stores**: Lightweight, modular stores
  - `useDeviceStore`: Device state
  - `useAlarmStore`: Alarm state
  - `useDiagnosticStore`: Diagnostic state
  - `useFlowStore`: Flow canvas state

### API Layer
- **Centralized client** (`src/api/client.ts`): Axios instance with interceptors
- **Modular API functions**: Separate files for each resource
  - `devices.ts`: Device API
  - `alarms.ts`: Alarm API
  - `diagnostics.ts`: Diagnostic API
  - `health.ts`: Health check API

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build production version
npm run build
```

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=30000
VITE_THEME=dark
VITE_ITEMS_PER_PAGE=20
VITE_ENABLE_REALTIME=true
VITE_ENABLE_NOTIFICATIONS=true
VITE_ENABLE_EXPORT=true
```

## Development Guidelines

1. **No hardcoding**: Use constants and config files
2. **File size limit**: Keep files under 1000 lines
3. **Modular design**: Split large components into smaller ones
4. **Type safety**: Use TypeScript types everywhere
5. **English only**: All code and comments in English

## Next Steps

1. Implement React Flow components
2. Create UI components (cards, badges, buttons)
3. Implement page components with full functionality
4. Add real-time updates
5. Add animations and transitions
