import {
  Archive,
  Check,
  ChevronRight,
  FolderPlus,
  MessageCircle,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  apiFetch,
  apiMessage,
  Application,
  Chat,
  ChatMessage,
  FolderNode,
  roleLabels,
  Specialty,
  statusLabels,
  User,
} from "../../api/client";
import { EmptyState, StatusBadge } from "../../components/Layout";
import { useAuth } from "../../context/AuthContext";

const statusOptions = Object.keys(statusLabels);

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU").format(new Date(value));
}

function flattenFolders(nodes: FolderNode[]): FolderNode[] {
  return nodes.flatMap((node) => [node, ...flattenFolders(node.children ?? [])]);
}

export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("tech@cet.local");
  const [password, setPassword] = useState("admin12345");
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) navigate("/admin/dashboard");
  }, [user, navigate]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/admin/dashboard");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <img src="/logo_cet.png" alt="КЭТ" />
        <p className="eyebrow">Административный вход</p>
        <h1>Система приема</h1>
        <label>
          <span>Email</span>
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label>
          <span>Пароль</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="primary-button">Войти</button>
      </form>
    </div>
  );
}

export function DashboardPage() {
  const { token, user } = useAuth();
  const [apps, setApps] = useState<Application[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);

  useEffect(() => {
    if (!token) return;
    void apiFetch<Application[]>("/admin/applications?limit=500", { token }).then(setApps);
    void apiFetch<Chat[]>("/admin/chats", { token }).then(setChats).catch(() => setChats([]));
  }, [token]);

  const counts = statusOptions.map((status) => ({ status, count: apps.filter((app) => app.status === status).length }));

  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Обзор</p>
          <h2>Добро пожаловать, {user?.full_name}</h2>
        </div>
        <Link to="/admin/file-manager" className="secondary-button">Открыть папки</Link>
      </div>
      <div className="metric-grid">
        <article><strong>{apps.length}</strong><span>Заявок доступно</span></article>
        <article><strong>{apps.filter((app) => app.status === "new").length}</strong><span>Новых</span></article>
        <article><strong>{apps.filter((app) => app.status === "completed").length}</strong><span>Оформленных</span></article>
        <article><strong>{chats.length}</strong><span>Чатов</span></article>
      </div>
      <div className="status-board">
        {counts.map((item) => (
          <div key={item.status} className="status-row">
            <StatusBadge status={item.status} />
            <span>{item.count}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ApplicationsPage() {
  const { token } = useAuth();
  const [apps, setApps] = useState<Application[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");

  const load = async () => {
    if (!token) return;
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    const items = await apiFetch<Application[]>(`/admin/applications?${params.toString()}`, { token });
    setApps(items);
    setSelected([]);
  };

  useEffect(() => {
    void load();
  }, [token, status]);

  const toggle = (id: number) => {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const bulk = async (action: "archive" | "accept" | "reject") => {
    if (!token || !selected.length) return;
    setError("");
    try {
      if (action === "reject") {
        const reason = window.prompt("Укажите причину отказа");
        if (!reason) return;
        await apiFetch(`/admin/applications/bulk/reject`, { method: "POST", token, body: JSON.stringify({ application_ids: selected, reason }) });
      } else {
        await apiFetch(`/admin/applications/bulk/${action}`, { method: "POST", token, body: JSON.stringify({ application_ids: selected }) });
      }
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Реестр</p>
          <h2>Заявки и студенты</h2>
        </div>
        <button className="secondary-button" onClick={load}><RefreshCw size={16} /> Обновить</button>
      </div>
      <div className="toolbar">
        <div className="search-box">
          <Search size={18} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && load()} placeholder="ФИО, ИИН, телефон, email" />
        </div>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Все статусы</option>
          {statusOptions.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
        </select>
      </div>
      <div className="bulk-panel">
        <span>Выбрано: {selected.length}</span>
        <button onClick={() => bulk("archive")}><Archive size={16} /> Архивировать</button>
        <button onClick={() => bulk("accept")}><Check size={16} /> Принять</button>
        <button onClick={() => bulk("reject")}><X size={16} /> Отклонить</button>
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="data-table">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>ФИО</th>
              <th>ИИН</th>
              <th>Контакты</th>
              <th>Специальность</th>
              <th>Статус</th>
              <th>Дата</th>
            </tr>
          </thead>
          <tbody>
            {apps.map((app) => (
              <tr key={app.id}>
                <td><input type="checkbox" checked={selected.includes(app.id)} onChange={() => toggle(app.id)} /></td>
                <td><Link to={`/admin/applications/${app.id}`}>{app.full_name}</Link></td>
                <td>{app.iin}</td>
                <td>{app.phone}<br /><span>{app.email}</span></td>
                <td>{app.admission_details?.specialty ?? "Не выбрано"}</td>
                <td><StatusBadge status={app.status} /></td>
                <td>{formatDate(app.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!apps.length && <EmptyState title="Нет записей" text="Попробуйте изменить фильтры или обновить список." />}
      </div>
    </section>
  );
}

export function FileManagerPage() {
  const { token } = useAuth();
  const [tree, setTree] = useState<FolderNode[]>([]);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [targetFolderId, setTargetFolderId] = useState("");

  const folders = useMemo(() => flattenFolders(tree), [tree]);

  const loadTree = async () => {
    if (!token) return;
    const nodes = await apiFetch<FolderNode[]>("/folders/tree", { token });
    setTree(nodes);
    if (!folderId && nodes[0]) setFolderId(nodes[0].id);
  };

  const loadApps = async () => {
    if (!token || !folderId) return;
    const items = await apiFetch<Application[]>(`/admin/applications?folder_id=${folderId}&limit=500`, { token });
    setApps(items);
    setSelected([]);
  };

  useEffect(() => { void loadTree(); }, [token]);
  useEffect(() => { void loadApps(); }, [token, folderId]);

  const createFolder = async () => {
    if (!token) return;
    const name = window.prompt("Название папки");
    if (!name) return;
    await apiFetch("/folders", { method: "POST", token, body: JSON.stringify({ name, parent_id: folderId }) });
    await loadTree();
  };

  const renameFolder = async () => {
    if (!token || !folderId) return;
    const name = window.prompt("Новое название папки");
    if (!name) return;
    await apiFetch(`/folders/${folderId}`, { method: "PATCH", token, body: JSON.stringify({ name }) });
    await loadTree();
  };

  const deleteFolder = async () => {
    if (!token || !folderId || !window.confirm("Удалить пустую папку?")) return;
    await apiFetch(`/folders/${folderId}`, { method: "DELETE", token });
    setFolderId(null);
    await loadTree();
  };

  const moveSelected = async () => {
    if (!token || !targetFolderId || !selected.length) return;
    await apiFetch("/folders/move-items", {
      method: "POST",
      token,
      body: JSON.stringify({ application_ids: selected, target_folder_id: Number(targetFolderId) })
    });
    await loadApps();
    await loadTree();
  };

  const renderNode = (node: FolderNode, depth = 0) => (
    <div key={node.id}>
      <button className={node.id === folderId ? "folder-node active" : "folder-node"} style={{ paddingLeft: 12 + depth * 14 }} onClick={() => setFolderId(node.id)}>
        <ChevronRight size={14} />
        <span>{node.name}</span>
        <small>{node.item_count}</small>
      </button>
      {node.children.map((child) => renderNode(child, depth + 1))}
    </div>
  );

  return (
    <section className="file-manager">
      <aside className="folder-pane">
        <div className="pane-header">
          <h2>Папки</h2>
          <button className="icon-button" onClick={createFolder} title="Создать папку"><FolderPlus size={18} /></button>
        </div>
        <div className="folder-tree">{tree.map((node) => renderNode(node))}</div>
      </aside>
      <main className="file-pane">
        <div className="pane-header">
          <div>
            <p className="eyebrow">Файловый менеджер</p>
            <h2>{folders.find((item) => item.id === folderId)?.name ?? "Папка"}</h2>
          </div>
          <div className="toolbar compact">
            <button onClick={renameFolder}><Pencil size={16} /> Переименовать</button>
            <button onClick={deleteFolder}><Trash2 size={16} /> Удалить</button>
          </div>
        </div>
        <div className="bulk-panel">
          <span>Выбрано: {selected.length}</span>
          <select value={targetFolderId} onChange={(event) => setTargetFolderId(event.target.value)}>
            <option value="">Куда переместить</option>
            {folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
          </select>
          <button onClick={moveSelected}>Переместить</button>
        </div>
        <div className="file-grid">
          {apps.map((app) => (
            <article key={app.id} className={selected.includes(app.id) ? "file-card selected" : "file-card"} onClick={() => setSelected((current) => current.includes(app.id) ? current.filter((id) => id !== app.id) : [...current, app.id])}>
              <input type="checkbox" checked={selected.includes(app.id)} readOnly />
              <h3>{app.full_name}</h3>
              <p>{app.iin}</p>
              <StatusBadge status={app.status} />
              <Link to={`/admin/applications/${app.id}`}>Открыть анкету</Link>
            </article>
          ))}
        </div>
      </main>
    </section>
  );
}

export function ApplicationDetailsPage() {
  const { token, user } = useAuth();
  const { applicationId } = useParams();
  const [app, setApp] = useState<Application | null>(null);
  const [teachers, setTeachers] = useState<User[]>([]);
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = async () => {
    if (!token || !applicationId) return;
    const item = await apiFetch<Application>(`/admin/applications/${applicationId}`, { token });
    setApp(item);
    const users = await apiFetch<User[]>("/users?role=teacher", { token }).catch(() => []);
    setTeachers(users);
    const info = await apiFetch<{ specialties: Specialty[] }>("/public/college-info").catch(() => ({ specialties: [] }));
    setSpecialties(info.specialties);
  };

  useEffect(() => { void load(); }, [token, applicationId]);

  const updateRoot = (field: keyof Application, value: string) => {
    setApp((current) => current ? { ...current, [field]: value } : current);
  };

  const updateAdmission = (field: keyof NonNullable<Application["admission_details"]>, value: string) => {
    setApp((current) => current ? { ...current, admission_details: { id: current.admission_details?.id ?? 0, ...current.admission_details, [field]: value } } : current);
  };

  const updateEducation = (field: keyof NonNullable<Application["education_details"]>, value: string | boolean | number | null) => {
    setApp((current) => current ? { ...current, education_details: { id: current.education_details?.id ?? 0, is_state_grant: false, ...current.education_details, [field]: value } } : current);
  };

  const saveApplication = async () => {
    if (!token || !app) return;
    setError("");
    setSaved("");
    try {
      const body = user?.role === "teacher"
        ? { email: app.email, phone: app.phone }
        : {
            iin: app.iin,
            birth_date: app.birth_date,
            full_name: app.full_name,
            email: app.email,
            phone: app.phone,
            admission_details: app.admission_details
          };
      const updated = await apiFetch<Application>(`/admin/applications/${app.id}`, { method: "PATCH", token, body: JSON.stringify(body) });
      setApp(updated);
      setSaved("Сохранено");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const saveEducation = async (complete = false) => {
    if (!token || !app?.education_details) return;
    setError("");
    const details = app.education_details;
    await apiFetch(`/education/applications/${app.id}/details`, {
      method: "PATCH",
      token,
      body: JSON.stringify({
        curator_id: details.curator_id,
        group_number: details.group_number,
        course: details.course,
        payment_type: details.payment_type,
        is_state_grant: details.is_state_grant
      })
    });
    if (complete) {
      await apiFetch<Application>(`/education/applications/${app.id}/save`, { method: "POST", token });
    }
    await load();
    setSaved("Сохранено");
  };

  const action = async (name: "archive" | "accept" | "reject") => {
    if (!token || !app) return;
    if (name === "reject") {
      const reason = window.prompt("Причина отказа");
      if (!reason) return;
      await apiFetch(`/admin/applications/${app.id}/reject`, { method: "POST", token, body: JSON.stringify({ reason }) });
    } else {
      await apiFetch(`/admin/applications/${app.id}/${name}`, { method: "POST", token });
    }
    await load();
  };

  if (!app) return <div className="admin-page"><EmptyState title="Загрузка" text="Открываем анкету." /></div>;
  const isTeacher = user?.role === "teacher";
  const canEducation = user?.role === "education_admin" || user?.role === "tech_admin";

  return (
    <section className="admin-page details-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Анкета #{app.id}</p>
          <h2>{app.full_name}</h2>
        </div>
        <StatusBadge status={app.status} />
      </div>
      {error && <div className="form-error">{error}</div>}
      {saved && <div className="form-success">{saved}</div>}
      <div className="details-grid">
        <form className="panel-form">
          <h3>Основные данные</h3>
          {!isTeacher && (
            <>
              <label><span>ИИН</span><input value={app.iin} onChange={(e) => updateRoot("iin", e.target.value.replace(/\D/g, "").slice(0, 12))} /></label>
              <label><span>Дата рождения</span><input type="date" value={app.birth_date} onChange={(e) => updateRoot("birth_date", e.target.value)} /></label>
              <label><span>ФИО</span><input value={app.full_name} onChange={(e) => updateRoot("full_name", e.target.value)} /></label>
            </>
          )}
          <label><span>Email</span><input value={app.email} onChange={(e) => updateRoot("email", e.target.value)} /></label>
          <label><span>Телефон</span><input value={app.phone} onChange={(e) => updateRoot("phone", e.target.value)} /></label>
          <button type="button" className="primary-button" onClick={saveApplication}><Save size={16} /> Сохранить</button>
        </form>

        {!isTeacher && (
          <form className="panel-form">
            <h3>Приемная комиссия</h3>
            <label><span>Льготная группа</span><input value={app.admission_details?.benefit_group ?? ""} onChange={(e) => updateAdmission("benefit_group", e.target.value)} /></label>
            <label><span>Место жительства</span><input value={app.admission_details?.residence_address ?? ""} onChange={(e) => updateAdmission("residence_address", e.target.value)} /></label>
            <label><span>База поступления</span><input value={app.admission_details?.base_class ?? ""} onChange={(e) => updateAdmission("base_class", e.target.value)} placeholder="9 класс / 11 класс" /></label>
            <label>
              <span>Специальность</span>
              <select value={app.admission_details?.specialty ?? ""} onChange={(e) => {
                const specialty = specialties.find((item) => item.name === e.target.value);
                updateAdmission("specialty", e.target.value);
                updateAdmission("qualification", specialty?.qualification ?? "");
              }}>
                <option value="">Выберите</option>
                {specialties.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
              </select>
            </label>
            <label><span>Квалификация</span><input value={app.admission_details?.qualification ?? ""} onChange={(e) => updateAdmission("qualification", e.target.value)} /></label>
            <div className="action-row">
              <button type="button" onClick={() => action("archive")}><Archive size={16} /> Архивировать</button>
              <button type="button" onClick={() => action("reject")}><X size={16} /> Отклонить</button>
              <button type="button" onClick={() => action("accept")}><Check size={16} /> Принять</button>
            </div>
          </form>
        )}

        {canEducation && (
          <form className="panel-form">
            <h3>Учебная часть</h3>
            <label>
              <span>Куратор</span>
              <select value={app.education_details?.curator_id ?? ""} onChange={(e) => updateEducation("curator_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="">Выберите преподавателя</option>
                {teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.full_name}</option>)}
              </select>
            </label>
            <label><span>Номер группы</span><input value={app.education_details?.group_number ?? ""} onChange={(e) => updateEducation("group_number", e.target.value)} placeholder="ИС-1-24" /></label>
            <label><span>Курс</span><input type="number" min={1} max={4} value={app.education_details?.course ?? ""} onChange={(e) => updateEducation("course", Number(e.target.value))} /></label>
            <label>
              <span>Оплата</span>
              <select value={app.education_details?.payment_type ?? ""} onChange={(e) => updateEducation("payment_type", e.target.value)}>
                <option value="">Выберите</option>
                <option value="free">Бесплатно</option>
                <option value="paid">Платно</option>
              </select>
            </label>
            <label className="checkbox-line"><input type="checkbox" checked={Boolean(app.education_details?.is_state_grant)} onChange={(e) => updateEducation("is_state_grant", e.target.checked)} /> Госзаказ</label>
            <div className="action-row">
              <button type="button" onClick={() => saveEducation(false)}><Save size={16} /> Сохранить</button>
              <button type="button" className="primary-button" onClick={() => saveEducation(true)}><Check size={16} /> Оформить</button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

export function ChatsPage() {
  const { token } = useAuth();
  const { chatId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const base = location.pathname.startsWith("/assistant") ? "/assistant/chats" : "/admin/chats";
  const activeId = chatId ? Number(chatId) : chats[0]?.id;

  const loadChats = async () => {
    if (!token) return;
    const items = await apiFetch<Chat[]>("/admin/chats", { token });
    setChats(items);
    if (!chatId && items[0]) navigate(`${base}/${items[0].id}`, { replace: true });
  };

  const loadMessages = async () => {
    if (!token || !activeId) return;
    const items = await apiFetch<ChatMessage[]>(`/admin/chats/${activeId}/messages`, { token });
    setMessages(items);
  };

  useEffect(() => { void loadChats(); }, [token]);
  useEffect(() => { void loadMessages(); }, [token, activeId]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !activeId || !text.trim()) return;
    await apiFetch(`/admin/chats/${activeId}/messages`, { method: "POST", token, body: JSON.stringify({ message: text.trim() }) });
    setText("");
    await loadMessages();
  };

  return (
    <section className="chat-admin">
      <aside className="chat-list">
        <h2>Чаты</h2>
        {chats.map((chat) => (
          <button key={chat.id} className={chat.id === activeId ? "active" : ""} onClick={() => navigate(`${base}/${chat.id}`)}>
            <MessageCircle size={18} />
            <span>{chat.application?.full_name ?? `Заявка #${chat.application_id}`}</span>
            <small>#{chat.application_id}</small>
          </button>
        ))}
      </aside>
      <main className="chat-thread">
        <div className="thread-header">
          <h2>{chats.find((chat) => chat.id === activeId)?.application?.full_name ?? "Чат"}</h2>
        </div>
        <div className="chat-messages admin">
          {messages.map((message) => (
            <div key={message.id} className={`message-bubble ${message.sender_type === "applicant" ? "mine" : "staff"}`}>
              <span>{message.sender_type === "applicant" ? "Абитуриент" : roleLabels[message.sender_type as keyof typeof roleLabels] ?? "Сотрудник"}</span>
              <p>{message.message}</p>
            </div>
          ))}
        </div>
        <form className="chat-input" onSubmit={send}>
          <input value={text} onChange={(event) => setText(event.target.value)} placeholder="Ответить..." />
          <button className="primary-button">Отправить</button>
        </form>
      </main>
    </section>
  );
}

export function UsersPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "admin12345", role: "teacher" });

  const load = async () => {
    if (!token) return;
    setUsers(await apiFetch<User[]>("/users", { token }));
  };

  useEffect(() => { void load(); }, [token]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    await apiFetch("/users", { method: "POST", token, body: JSON.stringify(form) });
    setForm({ full_name: "", email: "", password: "admin12345", role: "teacher" });
    await load();
  };

  const deactivate = async (id: number) => {
    if (!token || !window.confirm("Деактивировать пользователя?")) return;
    await apiFetch(`/users/${id}/deactivate`, { method: "PATCH", token });
    await load();
  };

  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Технический отдел</p>
          <h2>Пользователи и роли</h2>
        </div>
      </div>
      <form className="inline-form" onSubmit={create}>
        <input placeholder="ФИО" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
        <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <input placeholder="Пароль" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          {Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button className="primary-button"><UserPlus size={16} /> Добавить</button>
      </form>
      <div className="user-grid">
        {users.map((item) => (
          <article key={item.id} className={item.is_active ? "user-card" : "user-card disabled"}>
            <h3>{item.full_name}</h3>
            <p>{item.email}</p>
            <span>{roleLabels[item.role]}</span>
            <button onClick={() => deactivate(item.id)}><Trash2 size={16} /> Деактивировать</button>
          </article>
        ))}
      </div>
    </section>
  );
}

export function SettingsPage() {
  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Настройки</p>
          <h2>Системная информация</h2>
        </div>
      </div>
      <div className="settings-grid">
        <article>
          <h3>Backend</h3>
          <p>FastAPI, PostgreSQL, SQLAlchemy, Alembic, JWT.</p>
        </article>
        <article>
          <h3>Frontend</h3>
          <p>React, Vite, TypeScript, роль-зависимые рабочие зоны.</p>
        </article>
        <article>
          <h3>Workflow</h3>
          <p>Новая заявка, приемная комиссия, учебная часть, группы, архив и отказы.</p>
        </article>
      </div>
    </section>
  );
}
