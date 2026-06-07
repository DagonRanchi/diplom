import { Navigate, Route, Routes } from "react-router-dom";
import { AdminShell, ProtectedRoute } from "./components/Layout";
import {
  ApplicationDetailsPage,
  ApplicationsPage,
  ChatsPage,
  DashboardPage,
  FileManagerPage,
  LoginPage,
  SettingsPage,
  UsersPage,
} from "./pages/admin/AdminPages";
import { AssistantChatsPage } from "./pages/assistant/AssistantPages";
import { ApplyPage, HomePage, PublicChatPage } from "./pages/public/PublicPages";
import { DepartmentCasesPage } from "./pages/department/DepartmentPages";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/request" element={<ApplyPage />} />
      <Route path="/case/:applicationId" element={<PublicChatPage />} />
      <Route path="/staff/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AdminShell />
          </ProtectedRoute>
        }
      >
        <Route path="/portal/overview" element={<DashboardPage />} />
        <Route path="/portal/registry" element={<ApplicationsPage />} />
        <Route path="/portal/archive" element={<FileManagerPage />} />
        <Route path="/portal/cases/:applicationId" element={<ApplicationDetailsPage />} />
        <Route path="/portal/messages" element={<ChatsPage />} />
        <Route path="/portal/messages/:chatId" element={<ChatsPage />} />
        <Route path="/portal/users" element={<UsersPage />} />
        <Route path="/portal/settings" element={<SettingsPage />} />
        <Route path="/department/cases" element={<DepartmentCasesPage />} />
        <Route path="/department/cases/:applicationId" element={<ApplicationDetailsPage />} />
        <Route path="/operator/messages" element={<AssistantChatsPage />} />
        <Route path="/operator/messages/:chatId" element={<AssistantChatsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
