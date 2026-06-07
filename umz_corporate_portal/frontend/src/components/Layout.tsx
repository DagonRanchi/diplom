import {
  Archive,
  Bell,
  BriefcaseBusiness,
  ClipboardList,
  FileSpreadsheet,
  FolderKanban,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  ShieldCheck,
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
  if (!user) return <Navigate to="/staff/login" replace />;
  if (allowed && !allowed.includes(user.role) && user.role !== "tech_admin") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

const portalLinks = [
  { to: "/portal/overview", label: "Обзор", icon: LayoutDashboard, roles: ["tech_admin", "hr_admin", "document_admin"] },
  { to: "/portal/registry", label: "Реестр", icon: FileSpreadsheet, roles: ["tech_admin", "hr_admin", "document_admin"] },
  { to: "/portal/archive", label: "Архив", icon: Archive, roles: ["tech_admin", "hr_admin", "document_admin"] },
  { to: "/portal/messages", label: "Сообщения", icon: MessageCircle, roles: ["tech_admin", "hr_admin", "document_admin", "assistant"] },
  { to: "/portal/users", label: "Пользователи", icon: Users, roles: ["tech_admin"] },
  { to: "/portal/settings", label: "Система", icon: Settings, roles: ["tech_admin", "hr_admin", "document_admin"] },
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

  const links = portalLinks.filter((link) => link.roles.includes(user.role));
  if (user.role === "department_manager") {
    links.push({ to: "/department/cases", label: "Мои карточки", icon: BriefcaseBusiness, roles: ["department_manager"] });
  }
  if (user.role === "assistant") {
    links.push({ to: "/operator/messages", label: "Сообщения", icon: MessageCircle, roles: ["assistant"] });
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <button className="brand-button" onClick={() => navigate("/")}>
          <img src="/logo_umz.svg" alt="УМЗ" />
          <span>УМЗ Portal</span>
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
          <ShieldCheck size={18} />
          <span>{roleLabels[user.role]}</span>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Корпоративная рабочая зона</p>
            <h1>Документооборот УМЗ</h1>
          </div>
          <div className="topbar-actions">
            <div className="notification-pill" title="Непрочитанные уведомления">
              <Bell size={18} />
              <span>{unread}</span>
            </div>
            <div className="user-chip">
              <ClipboardList size={16} />
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
      <ClipboardList size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div>
        <strong>Корпоративный портал УМЗ</strong>
        <span>Республика Казахстан, г. Усть-Каменогорск</span>
      </div>
      <div>
        <span>Электронный документооборот, анкеты сотрудников и служебные обращения</span>
        <a href="mailto:portal@umz.local">portal@umz.local</a>
      </div>
    </footer>
  );
}
