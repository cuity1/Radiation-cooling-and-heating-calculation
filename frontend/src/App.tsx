import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import ShellLayout from './layouts/ShellLayout'
import { RequireAdmin, RequireAuth } from './components/RequireAuth'
import { getMaintenanceStatus } from './services/maintenance'
import { useAuth } from './context/AuthContext'

// 懒加载所有页面组件
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const HomePage = lazy(() => import('./pages/HomePage'))
const JobsListPage = lazy(() => import('./pages/JobsListPage'))
const NewJobPage = lazy(() => import('./pages/NewJobPage'))
const JobDetailPage = lazy(() => import('./pages/JobDetailPage'))
const ConfigPage = lazy(() => import('./pages/ConfigPage'))
const ToolsIndexPage = lazy(() => import('./pages/ToolsIndexPage'))
const WindCloudPage = lazy(() => import('./pages/tools/WindCloudPage'))
const SolarEfficiencyPage = lazy(() => import('./pages/tools/SolarEfficiencyPage'))
const EmissivitySolarCloudPage = lazy(() => import('./pages/tools/EmissivitySolarCloudPage'))
const PowerComponentsPage = lazy(() => import('./pages/tools/PowerComponentsPage'))
const AngularPowerPage = lazy(() => import('./pages/tools/AngularPowerPage'))
const ModtranTransmittancePage = lazy(() => import('./pages/tools/ModtranTransmittancePage'))
const MaterialEnvTempCloudPage = lazy(() => import('./pages/tools/MaterialEnvTempCloudPage'))
const MaterialEnvTempCloudJobDetailPage = lazy(() => import('./pages/MaterialEnvTempCloudJobDetailPage'))
const UploadsPage = lazy(() => import('./pages/UploadsPage'))
const Era5ValidationPage = lazy(() => import('./pages/Era5ValidationPage'))
const MapVisualizationPage = lazy(() => import('./pages/MapVisualizationPage'))
const MaterialComparisonDetailPage = lazy(() => import('./pages/MaterialComparisonDetailPage'))
const PowerMapPage = lazy(() => import('./pages/PowerMapPage'))
const PowerMapDetailPage = lazy(() => import('./pages/PowerMapDetailPage'))
const MaterialEnvTempMapPage = lazy(() => import('./pages/MaterialEnvTempMapPage'))
const MaterialEnvTempMapDetailPage = lazy(() => import('./pages/MaterialEnvTempMapDetailPage'))
const RadiationCoolingClothingPage = lazy(() => import('./pages/RadiationCoolingClothingPage'))
const RadiationCoolingClothingDetailPage = lazy(() => import('./pages/RadiationCoolingClothingDetailPage'))
const MapRedrawPage = lazy(() => import('./pages/MapRedrawPage'))
const GlassMapPage = lazy(() => import('./pages/GlassMapPage'))
const GlassComparisonDetailPage = lazy(() => import('./pages/GlassComparisonDetailPage'))
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage'))
const QaIndexPage = lazy(() => import('./pages/QaIndexPage'))
const QaDetailPage = lazy(() => import('./pages/QaDetailPage'))
const AIChatPage = lazy(() => import('./pages/AIChatPage'))
const UserManualPage = lazy(() => import('./pages/UserManualPage'))
const MaintenancePage = lazy(() => import('./pages/MaintenancePage'))

// Loading spinner
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[200px]">
      <div className="flex flex-col items-center gap-3">
        <div className="relative h-10 w-10">
          <div className="absolute inset-0 rounded-full border-2 border-accent/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
          <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-accent/40 animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const { user, loading } = useAuth()
  const [isMaintenance, setIsMaintenance] = useState(false)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const enabled = await getMaintenanceStatus()
        if (!cancelled) {
          setIsMaintenance(enabled)
          setChecked(true)
        }
      } catch {
        if (!cancelled) {
          setIsMaintenance(false)
          setChecked(true)
        }
      }
    }

    check()
    const id = setInterval(check, 30_000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  if (!checked || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <div className="relative h-12 w-12">
            <div className="absolute inset-0 rounded-full border-2 border-accent/20" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
            <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-accent/40 animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
            <div className="absolute inset-4 rounded-full border-2 border-transparent border-t-accent/20 animate-spin" style={{ animationDuration: '2s' }} />
          </div>
          <span className="text-sm text-text-secondary font-medium">Loading...</span>
        </div>
      </div>
    )
  }

  const isAdminUser = user?.id === 1
  const showMaintenance = isMaintenance && !isAdminUser

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/maintenance" element={<MaintenancePage />} />

        {showMaintenance && (
          <Route path="*" element={<MaintenancePage />} />
        )}

        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

            {!showMaintenance && (
            <>
            <Route
              path="/"
              element={
                <ShellLayout>
                  <HomePage />
                </ShellLayout>
              }
            />

            <Route path="/user-manual" element={<UserManualPage />} />

            <Route
              path="/admin"
              element={
                <ShellLayout>
                  <RequireAdmin>
                    <AdminDashboardPage />
                  </RequireAdmin>
                </ShellLayout>
              }
            />

            <Route
              path="/*"
              element={
                <ShellLayout>
                  <Routes>
                    <Route
                      path="/qa"
                      element={
                        <RequireAuth>
                          <QaIndexPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/qa/:questionId"
                      element={
                        <RequireAuth>
                          <QaDetailPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/jobs"
                      element={
                        <RequireAuth>
                          <JobsListPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/jobs/new"
                      element={
                        <RequireAuth>
                          <NewJobPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/jobs/:jobId"
                      element={
                        <RequireAuth>
                          <JobDetailPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/materials/:jobId"
                      element={
                        <RequireAuth>
                          <MaterialComparisonDetailPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/config"
                      element={
                        <RequireAuth>
                          <ConfigPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/tools"
                      element={
                        <RequireAuth>
                          <ToolsIndexPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/wind-cloud"
                      element={
                        <RequireAuth>
                          <WindCloudPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/solar-efficiency"
                      element={
                        <RequireAuth>
                          <SolarEfficiencyPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/emissivity-solar"
                      element={
                        <RequireAuth>
                          <EmissivitySolarCloudPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/power-components"
                      element={
                        <RequireAuth>
                          <PowerComponentsPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/angular-power"
                      element={
                        <RequireAuth>
                          <AngularPowerPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/modtran-transmittance"
                      element={
                        <RequireAuth>
                          <ModtranTransmittancePage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/material-env-temp-cloud"
                      element={
                        <RequireAuth>
                          <MaterialEnvTempCloudPage />
                        </RequireAuth>
                      }
                    />
                    <Route
                      path="/tools/material-env-temp-cloud/:jobId"
                      element={
                        <RequireAuth>
                          <MaterialEnvTempCloudJobDetailPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/uploads"
                      element={
                        <RequireAuth>
                          <UploadsPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/era5"
                      element={
                        <RequireAuth>
                          <Era5ValidationPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/map"
                      element={
                        <RequireAuth>
                          <MapVisualizationPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/power-map"
                      element={
                        <RequireAuth>
                          <PowerMapPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/power-map/:jobId"
                      element={
                        <RequireAuth>
                          <PowerMapDetailPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/material-env-temp-map"
                      element={
                        <RequireAuth>
                          <MaterialEnvTempMapPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/material-env-temp-map/:jobId"
                      element={
                        <RequireAuth>
                          <MaterialEnvTempMapDetailPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/radiation-cooling-clothing"
                      element={
                        <RequireAuth>
                          <RadiationCoolingClothingPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/radiation-cooling-clothing/:jobId"
                      element={
                        <RequireAuth>
                          <RadiationCoolingClothingDetailPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/map-redraw"
                      element={
                        <RequireAuth>
                          <MapRedrawPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/glass-map"
                      element={
                        <RequireAuth>
                          <GlassMapPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/glass-comparison/:jobId"
                      element={
                        <RequireAuth>
                          <GlassComparisonDetailPage />
                        </RequireAuth>
                      }
                    />

                    <Route
                      path="/ai-chat"
                      element={
                        <RequireAuth>
                          <AIChatPage />
                        </RequireAuth>
                      }
                    />

                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </ShellLayout>
              }
            />
            </>
            )}
      </Routes>
    </Suspense>
  )
}
