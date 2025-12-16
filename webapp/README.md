# Amplifier Web Application

React + TypeScript web UI for the Amplifier system, backed by the [Amplifier Daemon](../amplifierd/amplifierd/README.md).

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router 7** - Client-side routing
- **TanStack Query** - Server state management
- **Tailwind CSS 4** - Styling
- **Lucide React** - Icons

## Development

```bash
# Install dependencies
pnpm install

# Start dev server (http://localhost:5173)
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview
```
## Environment Variables

Create a `.env` file (defaults shown):

```bash
VITE_API_URL=http://localhost:8420
```

### LAN Access

To access the webapp from other devices on your network:

1. Configure daemon for LAN access
2. Create `.env.local` with your machine's network address
3. Restart the webapp

**📖 See [../LAN.md](../LAN.md) for complete setup instructions, troubleshooting, and security considerations.**

