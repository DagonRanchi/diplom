import {
  Bell,
  BookOpen,
  Boxes,
  FileText,
  FolderTree,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  Users,
} from "lucide-react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { ReactNode, useEffect, useState } from "react";
import { apiFetch, Notification, Role, roleLabels, statusLabels } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{statusLabels[status] ?? status}</span>;
}

export function ProtectedRoute({ allowed, children }: { allowed?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="screen-loader">Загрузка...</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  if (allowed && !allowed.includes(user.role) && user.role !== "tech_admin") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

const adminLinks = [
  { to: "/admin/dashboard", label: "Дашборд", icon: LayoutDashboard, roles: ["tech_admin", "admissions_admin", "education_admin"] },
  { to: "/admin/applications", label: "Заявки", icon: FileText, roles: ["tech_admin", "admissions_admin", "education_admin"] },
  { to: "/admin/file-manager", label: "Папки", icon: FolderTree, roles: ["tech_admin", "admissions_admin", "education_admin"] },
  { to: "/admin/chats", label: "Чаты", icon: MessageCircle, roles: ["tech_admin", "admissions_admin", "education_admin", "assistant"] },
  { to: "/admin/users", label: "Пользователи", icon: Users, roles: ["tech_admin"] },
  { to: "/admin/settings", label: "Настройки", icon: Settings, roles: ["tech_admin", "admissions_admin", "education_admin"] },
];

export function AdminShell() {
  const { user, token, logout } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      const items = await apiFetch<Notification[]>("/notifications", { token });
      setNotifications(items);
    };
    void load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [token]);

  if (!user) return null;
  const unread = notifications.filter((item) => !item.is_read).length;

  const links = adminLinks.filter((link) => link.roles.includes(user.role));
  if (user.role === "teacher") {
    links.push({ to: "/teacher/students", label: "Студенты", icon: GraduationCap, roles: ["teacher"] });
  }
  if (user.role === "assistant") {
    links.push({ to: "/assistant/chats", label: "Чаты", icon: MessageCircle, roles: ["assistant"] });
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <button className="brand-button" onClick={() => navigate("/")}>
          <img src="/logo_cet.png" alt="CET" />
          <span>КЭТ</span>
        </button>
        <nav>
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink key={link.to} to={link.to} className={({ isActive }) => (isActive ? "active" : "")}>
                <Icon size={18} />
                <span>{link.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <BookOpen size={18} />
          <span>{roleLabels[user.role]}</span>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Административная система</p>
            <h1>Колледж экономики и техники</h1>
          </div>
          <div className="topbar-actions">
            <div className="notification-pill" title="Непрочитанные уведомления">
              <Bell size={18} />
              <span>{unread}</span>
            </div>
            <div className="user-chip">
              <Boxes size={16} />
              <span>{user.full_name}</span>
            </div>
            <button className="icon-button" onClick={logout} title="Выйти">
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}

export function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty-state">
      <FileText size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
