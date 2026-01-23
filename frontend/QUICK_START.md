# Frontend Quick Start Guide

## Prerequisites

Make sure you have Node.js (v18+) and npm installed.

## Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

## Running the Frontend

### Development Mode

```bash
npm run dev
```

This will start the Vite development server, typically at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Environment Variables

Create a `.env` file in the `frontend` directory:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=30000
VITE_THEME=dark
VITE_ITEMS_PER_PAGE=20
VITE_ENABLE_REALTIME=true
VITE_ENABLE_NOTIFICATIONS=true
VITE_ENABLE_EXPORT=true
```

## Quick Command Reference

```bash
# Install dependencies
cd frontend && npm install

# Start development server
cd frontend && npm run dev

# Build for production
cd frontend && npm run build

# Run from project root (one-liner)
cd frontend && npm install && npm run dev
```

