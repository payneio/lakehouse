import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { MainLayout } from '@/components/layout/MainLayout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { LoginPage } from '@/pages/Login'
import { HomePage } from '@/pages/Home'
import { BundlesPage } from '@/pages/Bundles'
import { ProjectsPage } from '@/pages/Projects'
import { SessionView } from '@/features/session'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/home" replace />} />
          <Route path="home" element={<HomePage />} />
          <Route path="bundles" element={<BundlesPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/sessions/:sessionId" element={<SessionView />} />
          {/* Backward compatibility redirects */}
          <Route path="directories" element={<Navigate to="/projects" replace />} />
          <Route path="directories/sessions/:sessionId" element={<Navigate to="/projects/sessions/:sessionId" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
