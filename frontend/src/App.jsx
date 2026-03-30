import { useState } from 'react'
import { APP_CLASSES } from './constants/appData'
import CreateAccountPage from './pages/CreateAccountPage'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'

function App() {
  const [currentPage, setCurrentPage] = useState('home')

  return (
    <main className={APP_CLASSES.main}>
      <div className={APP_CLASSES.backgroundOverlay} />

      {currentPage === 'home' && (
        <HomePage
          onLoginClick={() => setCurrentPage('login')}
          onStartComputingClick={() => setCurrentPage('create-account')}
        />
      )}

      {currentPage === 'login' && (
        <LoginPage
          onCreateAccountClick={() => setCurrentPage('create-account')}
          onLoginSuccess={() => setCurrentPage('dashboard')}
        />
      )}

      {currentPage === 'create-account' && (
        <CreateAccountPage
          onBackToLogin={() => setCurrentPage('login')}
          onCreateAccountSuccess={() => setCurrentPage('dashboard')}
        />
      )}

      {currentPage === 'dashboard' && (
        <DashboardPage onBackHome={() => setCurrentPage('home')} />
      )}
    </main>
  )
}

export default App
