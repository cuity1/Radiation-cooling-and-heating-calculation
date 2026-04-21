# Radiation Cooling & Heating Web Platform (Frontend)

Modern, responsive web interface for the Radiation Cooling & Heating Calculation platform. Built with React, Vite, and TypeScript.

## Features

- 🌍 Bilingual support (English/中文)
- 🎨 Clean, research-focused UI with scientific theming
- 📊 Ready for data visualization with Plotly.js
- ⚡ Fast development with Vite
- 🎯 Type-safe with TypeScript

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install
# or
yarn install

# Start development server
npm run dev
# or
yarn dev
```

### Building for Production

```bash
npm run build
# or
yarn build
```

## Project Structure

```
frontend/
├── public/              # Static files
├── src/
│   ├── assets/          # Images, fonts, etc.
│   ├── components/      # Reusable UI components
│   ├── config/          # App configuration
│   ├── hooks/           # Custom React hooks
│   ├── i18n/            # Internationalization
│   ├── layouts/         # Page layouts
│   ├── lib/             # Utility functions
│   ├── pages/           # Page components
│   ├── services/        # API services
│   ├── store/           # State management
│   ├── styles/          # Global styles
│   ├── types/           # TypeScript type definitions
│   ├── App.tsx          # Main App component
│   └── main.tsx         # App entry point
├── .env                 # Environment variables
├── index.html           # HTML template
├── package.json
├── tsconfig.json        # TypeScript config
└── vite.config.ts       # Vite config
```

## Internationalization

This project uses `i18next` for internationalization. To add new translations:

1. Add new language files in `src/i18n/locales/`
2. Update `src/i18n/config.ts` to include the new language

## Styling

This project uses:
- Tailwind CSS for utility-first styling
- Custom theme configuration in `tailwind.config.js`
- Custom CSS in `src/styles/`

## License

MIT