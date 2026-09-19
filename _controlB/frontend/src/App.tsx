/**
 * App.tsx - Roteamento Central da Aplicação SPA (React Router DOM)
 * 
 * Gerencia as rotas públicas (Login) e privadas (Dashboard, Compras, Cadastros)
 * com proteção de autenticação, redirecionamentos e ThemeProvider (Dark / Light).
 */

import React, { Suspense, lazy } from 'react';
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { ThemeProvider } from '@/context/ThemeContext';
import { ToastProvider } from '@/components/Toast/ToastProvider';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { PublicRoute } from '@/components/PublicRoute';
import { AppLayout } from '@/components/AppLayout';

// 🚀 Lazy Loading de Páginas (Code-Splitting por Rota)
const Login = lazy(() => import('@/pages/Login/Login').then(m => ({ default: m.Login })));
const Dashboard = lazy(() => import('@/pages/Dashboard/Dashboard').then(m => ({ default: m.Dashboard })));
const Purchasing = lazy(() => import('@/pages/Purchasing/Purchasing').then(m => ({ default: m.Purchasing })));
const Inventory = lazy(() => import('@/pages/Inventory/Inventory').then(m => ({ default: m.Inventory })));
const CRM = lazy(() => import('@/pages/CRM/CRM').then(m => ({ default: m.CRM })));
const Sales = lazy(() => import('@/pages/Sales/Sales').then(m => ({ default: m.Sales })));
const POS = lazy(() => import('@/pages/POS/POS').then(m => ({ default: m.POS })));
const Finance = lazy(() => import('@/pages/Finance/Finance').then(m => ({ default: m.Finance })));
const Billing = lazy(() => import('@/pages/Billing/Billing').then(m => ({ default: m.Billing })));
const Cadastros = lazy(() => import('@/pages/Cadastros/Cadastros').then(m => ({ default: m.Cadastros })));
const OrganizationRecordFormPage = lazy(() => import('@/pages/Cadastros/records/OrganizationRecordFormPage').then(m => ({ default: m.OrganizationRecordFormPage })));
const UserRecordFormPage = lazy(() => import('@/pages/Cadastros/records/UserRecordFormPage').then(m => ({ default: m.UserRecordFormPage })));
const RoleRecordFormPage = lazy(() => import('@/pages/Cadastros/records/RoleRecordFormPage').then(m => ({ default: m.RoleRecordFormPage })));
const Documents = lazy(() => import('@/pages/Documents/Documents').then(m => ({ default: m.Documents })));
const Projects = lazy(() => import('@/pages/Projects/Projects').then(m => ({ default: m.Projects })));
const ProjectRecordFormPage = lazy(() => import('@/pages/Projects/records/ProjectRecordFormPage').then(m => ({ default: m.ProjectRecordFormPage })));
const WorkOrderRecordFormPage = lazy(() => import('@/pages/Projects/records/WorkOrderRecordFormPage').then(m => ({ default: m.WorkOrderRecordFormPage })));
const TaskRecordFormPage = lazy(() => import('@/pages/Projects/records/TaskRecordFormPage').then(m => ({ default: m.TaskRecordFormPage })));
const IssueRecordFormPage = lazy(() => import('@/pages/Projects/records/IssueRecordFormPage').then(m => ({ default: m.IssueRecordFormPage })));
const ProjectTypeRecordFormPage = lazy(() => import('@/pages/Projects/records/TypeRecordFormPage').then(m => ({ default: m.ProjectTypeRecordFormPage })));
const WorkOrderTypeRecordFormPage = lazy(() => import('@/pages/Projects/records/TypeRecordFormPage').then(m => ({ default: m.WorkOrderTypeRecordFormPage })));
const WorkflowRecordFormPage = lazy(() => import('@/pages/Projects/records/WorkflowRecordFormPage').then(m => ({ default: m.WorkflowRecordFormPage })));

const PageLoadingFallback: React.FC = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    width: '100%',
    color: 'var(--text-secondary, #94a3b8)',
    gap: '0.6rem',
    fontSize: '0.875rem'
  }}>
    <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
    <span>Carregando módulo...</span>
  </div>
);

const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <PublicRoute>
        <Login />
      </PublicRoute>
    ),
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/dashboard', element: <Dashboard /> },
          { path: '/crm', element: <CRM /> },
          { path: '/vendas', element: <Sales /> },
          { path: '/pdv', element: <POS /> },
          { path: '/faturamento', element: <Billing /> },
          { path: '/financeiro', element: <Finance /> },
          { path: '/finance', element: <Navigate to="/financeiro" replace /> },
          { path: '/estoque', element: <Inventory /> },
          { path: '/compras', element: <Purchasing /> },
          { path: '/documentos', element: <Documents /> },
          { path: '/projetos', element: <Projects /> },
          { path: '/projetos/projetos/:recordId', element: <ProjectRecordFormPage /> },
          { path: '/projetos/ordens-de-trabalho/:recordId', element: <WorkOrderRecordFormPage /> },
          { path: '/projetos/tarefas/:recordId', element: <TaskRecordFormPage /> },
          { path: '/projetos/ocorrencias/:recordId', element: <IssueRecordFormPage /> },
          { path: '/projetos/tipos-de-projeto/:recordId', element: <ProjectTypeRecordFormPage /> },
          { path: '/projetos/tipos-de-ordem/:recordId', element: <WorkOrderTypeRecordFormPage /> },
          { path: '/projetos/workflows/:recordId', element: <WorkflowRecordFormPage /> },
          { path: '/cadastros', element: <Cadastros /> },
          { path: '/cadastros/organizacoes/:recordId', element: <OrganizationRecordFormPage /> },
          { path: '/cadastros/usuarios/:recordId', element: <UserRecordFormPage /> },
          { path: '/cadastros/cargos/:recordId', element: <RoleRecordFormPage /> },
          { path: '/organizacoes', element: <Cadastros initialMenu="organizacoes" /> },
          { path: '/usuarios', element: <Cadastros initialMenu="usuarios" /> },
          { path: '/cargos', element: <Cadastros initialMenu="cargos" /> },
          { path: '/', element: <Navigate to="/dashboard" replace /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/dashboard" replace /> },
]);

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <ToastProvider>
        <Suspense fallback={<PageLoadingFallback />}>
          <RouterProvider router={router} />
        </Suspense>
      </ToastProvider>
    </ThemeProvider>
  );
};

export default App;
