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
import { TeacherStudentsPage } from "./pages/teacher/TeacherPages";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/apply" element={<ApplyPage />} />
      <Route path="/chat/:applicationId" element={<PublicChatPage />} />
      <Route path="/admin/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AdminShell />
          </ProtectedRoute>
        }
      >
        <Route path="/admin/dashboard" element={<DashboardPage />} />
        <Route path="/admin/applications" element={<ApplicationsPage />} />
        <Route path="/admin/file-manager" element={<FileManagerPage />} />
        <Route path="/admin/applications/:applicationId" element={<ApplicationDetailsPage />} />
        <Route path="/admin/chats" element={<ChatsPage />} />
        <Route path="/admin/chats/:chatId" element={<ChatsPage />} />
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/settings" element={<SettingsPage />} />
        <Route path="/teacher/students" element={<TeacherStudentsPage />} />
        <Route path="/teacher/students/:applicationId" element={<ApplicationDetailsPage />} />
        <Route path="/assistant/chats" element={<AssistantChatsPage />} />
        <Route path="/assistant/chats/:chatId" element={<AssistantChatsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
