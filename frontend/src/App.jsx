import { useEffect, useState } from 'react'
import { APP_CLASSES } from './constants/appData'
import CreateAccountPage from './pages/CreateAccountPage'
import DashboardPage from './pages/DashboardPage'
import DemoArchitecturePage from './pages/DemoArchitecturePage'
import HomePage from './pages/HomePage'
import JobResultsPage from './pages/JobResultsPage'
import JobSubmissionPage from './pages/JobSubmissionPage'
import LoginPage from './pages/LoginPage'
import { getMe } from './lib/api'

const TOKEN_STORAGE_KEY = 'rvidia_access_token'

function App() {
  const [currentPage, setCurrentPage] = useState('home')
  const [authToken, setAuthToken] = useState(localStorage.getItem(TOKEN_STORAGE_KEY) || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState('')

  useEffect(() => {
    if (!authToken) {
      setCurrentUser(null)
      return
    }

    let active = true
    getMe(authToken)
      .then((user) => {
        if (active) {
          setCurrentUser(user)
        }
      })
      .catch(() => {
        if (active) {
          localStorage.removeItem(TOKEN_STORAGE_KEY)
          setAuthToken('')
          setCurrentUser(null)
        }
      })

    return () => {
      active = false
    }
  }, [authToken])

  const handleLoginSuccess = (token) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
    setAuthToken(token)
    setCurrentPage('dashboard')
  }

  const handleSignupSuccess = (token) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
    setAuthToken(token)
    setCurrentPage('dashboard')
  }

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setAuthToken('')
    setCurrentUser(null)
    setCurrentPage('home')
  }

  return (
    <main className={APP_CLASSES.main}>
      {currentPage !== 'demo-architecture' && <div className={APP_CLASSES.backgroundOverlay} />}

      {currentPage === 'home' && (
        <HomePage
          onLoginClick={() => setCurrentPage('login')}
          onStartComputingClick={() => setCurrentPage('create-account')}
          onDemoClick={() => setCurrentPage('demo-architecture')}
        />
      )}

      {currentPage === 'demo-architecture' && <DemoArchitecturePage />}

      {currentPage === 'login' && (
        <LoginPage
          onCreateAccountClick={() => setCurrentPage('create-account')}
          onLoginSuccess={handleLoginSuccess}
        />
      )}

      {currentPage === 'create-account' && (
        <CreateAccountPage
          onBackToLogin={() => setCurrentPage('login')}
          onCreateAccountSuccess={handleSignupSuccess}
        />
      )}

      {currentPage === 'dashboard' && (
        <DashboardPage
          authToken={authToken}
          currentUser={currentUser}
          onBackHome={() => setCurrentPage('home')}
          onGoResults={() => setCurrentPage('job-results')}
          onGoSubmit={() => setCurrentPage('job-submit')}
          onLogout={handleLogout}
        />
      )}

      {currentPage === 'job-submit' && (
        <JobSubmissionPage
          authToken={authToken}
          onBackDashboard={() => setCurrentPage('dashboard')}
          onJobCreated={(jobId) => {
            setSelectedJobId(jobId)
            setCurrentPage('job-results')
          }}
        />
      )}

      {currentPage === 'job-results' && (
        <JobResultsPage
          authToken={authToken}
          highlightedJobId={selectedJobId}
          onBackDashboard={() => setCurrentPage('dashboard')}
        />
      )}
    </main>
  )
}

export default App
