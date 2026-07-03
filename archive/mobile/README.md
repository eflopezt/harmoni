# Harmoni Mobile

React Native (Expo) mobile app for the Harmoni ERP system. Provides employees with self-service access to attendance, payslips, vacation requests, and profile management.

## Prerequisites

- Node.js 18+
- Expo CLI (`npm install -g expo-cli`)
- Expo Go app on your phone (iOS or Android)

## Setup

```bash
cd mobile
npm install
```

## Running

```bash
# Start the Expo dev server
npx expo start

# Or target a specific platform
npx expo start --android
npx expo start --ios
```

Scan the QR code with Expo Go to open on your device.

## Configuration

### API Server (Development)

Edit `src/api/client.js` and update the LAN IP in `buildBaseUrl()` to point to your local Django server:

```js
return 'http://192.168.1.100:8000';  // Replace with your machine's IP
```

### Production

The app resolves `https://<subdomain>.harmoni.pe` automatically based on the company subdomain entered at login.

## Project Structure

```
mobile/
  App.js                          # Root component (AuthProvider + NavigationContainer)
  package.json
  src/
    api/
      client.js                   # Axios instance with JWT interceptors
      auth.js                     # Login / logout / token refresh
      asistencia.js               # Attendance endpoints
      nominas.js                  # Payslip endpoints + PDF download
      personal.js                 # Employee profile endpoints
      vacaciones.js               # Vacation balance + requests
    context/
      AuthContext.js              # Auth state management (useReducer)
    navigation/
      AppNavigator.js             # Stack + bottom tab navigators
    screens/
      LoginScreen.js              # Company subdomain + credentials
      HomeScreen.js               # Dashboard with KPIs + quick actions
      AsistenciaScreen.js         # Calendar, today's status, mark attendance
      BoletasScreen.js            # Payslip list + PDF download
      VacacionesScreen.js         # Balance, request form, history
      PerfilScreen.js             # Employee info, settings, logout
      NotificacionesScreen.js     # Notification list with read/unread
    components/
      KPICard.js                  # Colored metric card with icon
      NotificationBadge.js        # Red circle badge with count
      LoadingSpinner.js           # Centered spinner
      EmptyState.js               # Empty list placeholder
      StatusBadge.js              # Colored status label (APROBADA, PENDIENTE, etc.)
    utils/
      format.js                   # Currency, date, time formatting (Peruvian)
      storage.js                  # AsyncStorage helpers for tokens + user data
```

## Tech Stack

- React Native 0.73 via Expo SDK 50
- React Navigation 6 (native-stack + bottom-tabs)
- Axios with JWT auto-refresh
- AsyncStorage for persistence
- Expo Vector Icons (Ionicons)
- Expo File System + Sharing for PDF downloads
