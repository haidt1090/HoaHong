import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/auth/LoginPage.vue'),
    meta: { guest: true },
  },
  {
    path: '/change-password',
    name: 'change-password',
    component: () => import('@/pages/auth/ChangePasswordPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/pages/DashboardPage.vue'),
      },
      {
        path: 'patients',
        name: 'patient-list',
        component: () => import('@/pages/patients/PatientListPage.vue'),
      },
      {
        path: 'patients/create',
        name: 'patient-create',
        component: () => import('@/pages/patients/PatientCreatePage.vue'),
      },
      {
        path: 'patients/:id',
        name: 'patient-detail',
        component: () => import('@/pages/patients/PatientDetailPage.vue'),
      },
      {
        path: 'patients/:id/edit',
        name: 'patient-edit',
        component: () => import('@/pages/patients/PatientEditPage.vue'),
      },
      {
        path: 'companies',
        name: 'company-list',
        component: () => import('@/pages/companies/CompanyListPage.vue'),
        meta: { roles: ['admin', 'doctor'] as Role[] },
      },
      {
        path: 'companies/create',
        name: 'company-create',
        component: () => import('@/pages/companies/CompanyCreatePage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'companies/:id',
        name: 'company-detail',
        component: () => import('@/pages/companies/CompanyDetailPage.vue'),
        meta: { roles: ['admin', 'doctor'] as Role[] },
      },
      {
        path: 'companies/:id/edit',
        name: 'company-edit',
        component: () => import('@/pages/companies/CompanyEditPage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'companies/:id/packages',
        name: 'company-packages',
        component: () => import('@/pages/companies/CompanyPackagesPage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'examinations',
        name: 'exam-list',
        component: () => import('@/pages/examinations/ExaminationListPage.vue'),
      },
      {
        path: 'examinations/create',
        name: 'exam-create',
        component: () => import('@/pages/examinations/ExaminationCreatePage.vue'),
        meta: { roles: ['admin', 'doctor', 'nurse', 'labtech'] as Role[] },
      },
      {
        path: 'examinations/:id',
        name: 'exam-detail',
        component: () => import('@/pages/examinations/ExaminationDetailPage.vue'),
      },
      {
        path: 'examinations/:id/edit',
        name: 'exam-edit',
        component: () => import('@/pages/examinations/ExaminationEditPage.vue'),
        meta: { roles: ['admin', 'doctor', 'nurse', 'labtech'] as Role[] },
      },
      {
        path: 'import',
        name: 'import',
        component: () => import('@/pages/import/ExcelImportPage.vue'),
        meta: { roles: ['admin', 'doctor', 'nurse', 'labtech'] as Role[] },
      },
      {
        path: 'diagnosis/keywords',
        name: 'keyword-list',
        component: () => import('@/pages/diagnosis/KeywordListPage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'reports',
        name: 'report-list',
        component: () => import('@/pages/reports/ReportListPage.vue'),
        meta: { roles: ['admin', 'doctor'] as Role[] },
      },
      {
        path: 'reports/generate',
        name: 'report-generate',
        component: () => import('@/pages/reports/ReportGeneratePage.vue'),
        meta: { roles: ['admin', 'doctor'] as Role[] },
      },
      {
        path: 'sync',
        name: 'national-sync',
        component: () => import('@/pages/sync/NationalSyncPage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'sync/usb-signer',
        name: 'usb-signer',
        component: () => import('@/pages/sync/UsbSignerPage.vue'),
        meta: { roles: ['admin', 'doctor'] as Role[] },
      },
      {
        path: 'sync/mapping',
        name: 'sync-field-mapping',
        component: () => import('@/pages/sync/SyncMappingPage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'report-print',
        name: 'report-print',
        component: () => import('@/pages/reports/ReportPrintPage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
      {
        path: 'sync/signatures',
        name: 'doctor-signatures',
        component: () => import('@/pages/sync/DoctorSignaturePage.vue'),
        meta: { roles: ['admin'] as Role[] },
      },
    ],
  },
  {
    path: '/403',
    name: 'forbidden',
    component: () => import('@/pages/error/ForbiddenPage.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/error/NotFoundPage.vue'),
  },
]

const router = createRouter({
  history: createWebHistory('/khamsk/'),
  routes,
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (!authStore.user && authStore.accessToken) {
    await authStore.fetchMe()
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guest && authStore.isAuthenticated) {
    return { name: 'dashboard' }
  }

  if (authStore.isAuthenticated && authStore.mustChangePassword && to.name !== 'change-password') {
    return { name: 'change-password' }
  }

  const roles = to.meta.roles as Role[] | undefined
  if (roles && roles.length > 0 && !authStore.isRole(...roles)) {
    return { name: 'forbidden' }
  }

  return true
})

export default router
