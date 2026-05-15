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
import { DragEvent as ReactDragEvent, FormEvent, MouseEvent as ReactMouseEvent, useEffect, useMemo, useRef, useState } from "react";
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
                <td><Link to={`/admin/applications/${app.id}${selected.includes(app.id) && selected.length > 1 ? `?bulk=${selected.join(",")}` : ""}`}>{app.full_name}</Link></td>
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
  const navigate = useNavigate();
  const [tree, setTree] = useState<FolderNode[]>([]);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [draggingIds, setDraggingIds] = useState<number[]>([]);
  const [dropTargetId, setDropTargetId] = useState<number | null>(null);
  const [selectionBox, setSelectionBox] = useState<{ startX: number; startY: number; x: number; y: number } | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);

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

  const moveApplications = async (applicationIds: number[], targetFolderId: number) => {
    if (!token || !targetFolderId || !applicationIds.length) return;
    await apiFetch("/folders/move-items", {
      method: "POST",
      token,
      body: JSON.stringify({ application_ids: applicationIds, target_folder_id: targetFolderId })
    });
    await loadApps();
    await loadTree();
  };

  const startSelection = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest(".file-card")) return;
    const grid = gridRef.current;
    if (!grid) return;
    const bounds = grid.getBoundingClientRect();
    const startX = event.clientX - bounds.left;
    const startY = event.clientY - bounds.top;
    setSelected([]);
    setSelectionBox({ startX, startY, x: startX, y: startY });

    const selectInsideBox = (x: number, y: number) => {
      const left = Math.min(startX, x);
      const top = Math.min(startY, y);
      const right = Math.max(startX, x);
      const bottom = Math.max(startY, y);
      const ids = Array.from(grid.querySelectorAll<HTMLElement>("[data-app-id]"))
        .filter((card) => {
          const rect = card.getBoundingClientRect();
          const cardLeft = rect.left - bounds.left;
          const cardTop = rect.top - bounds.top;
          const cardRight = cardLeft + rect.width;
          const cardBottom = cardTop + rect.height;
          return cardLeft < right && cardRight > left && cardTop < bottom && cardBottom > top;
        })
        .map((card) => Number(card.dataset.appId))
        .filter(Boolean);
      setSelected(ids);
    };

    const onMouseMove = (moveEvent: MouseEvent) => {
      const x = moveEvent.clientX - bounds.left;
      const y = moveEvent.clientY - bounds.top;
      setSelectionBox({ startX, startY, x, y });
      selectInsideBox(x, y);
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setSelectionBox(null);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  const openApplication = (appId: number) => {
    const bulkIds = selected.includes(appId) && selected.length > 1 ? selected : [appId];
    const query = bulkIds.length > 1 ? `?bulk=${bulkIds.join(",")}` : "";
    navigate(`/admin/applications/${appId}${query}`);
  };

  const clickCard = (appId: number, event: ReactMouseEvent<HTMLElement>) => {
    if (event.ctrlKey || event.metaKey) {
      setSelected((current) => current.includes(appId) ? current.filter((id) => id !== appId) : [...current, appId]);
      return;
    }
    setSelected((current) => current.includes(appId) && current.length > 1 ? current : [appId]);
  };

  const beginDrag = (appId: number, event: ReactDragEvent<HTMLElement>) => {
    const ids = selected.includes(appId) ? selected : [appId];
    if (!selected.includes(appId)) setSelected(ids);
    setDraggingIds(ids);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/json", JSON.stringify(ids));
  };

  const endDrag = () => {
    setDraggingIds([]);
    setDropTargetId(null);
  };

  const selectionStyle = selectionBox
    ? {
        left: Math.min(selectionBox.startX, selectionBox.x),
        top: Math.min(selectionBox.startY, selectionBox.y),
        width: Math.abs(selectionBox.x - selectionBox.startX),
        height: Math.abs(selectionBox.y - selectionBox.startY),
      }
    : undefined;

  const renderNode = (node: FolderNode, depth = 0) => (
    <div key={node.id}>
      <button
        className={[
          "folder-node",
          node.id === folderId ? "active" : "",
          node.id === dropTargetId ? "drop-target" : "",
        ].filter(Boolean).join(" ")}
        style={{ paddingLeft: 12 + depth * 14 }}
        onClick={() => setFolderId(node.id)}
        onDragOver={(event) => {
          if (!draggingIds.length) return;
          event.preventDefault();
          setDropTargetId(node.id);
        }}
        onDragLeave={() => setDropTargetId((current) => current === node.id ? null : current)}
        onDrop={(event) => {
          event.preventDefault();
          const payload = event.dataTransfer.getData("application/json");
          const ids = payload ? JSON.parse(payload) as number[] : draggingIds;
          void moveApplications(ids, node.id);
          endDrag();
        }}
      >
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
          <span className="muted">Выделите рамкой или кликом, затем перетащите в папку слева.</span>
        </div>
        <div className="file-grid-shell" ref={gridRef} onMouseDown={startSelection}>
          {selectionBox && <div className="selection-box" style={selectionStyle} />}
          <div className="file-grid">
            {apps.map((app) => (
              <article
                key={app.id}
                data-app-id={app.id}
                draggable
                className={selected.includes(app.id) ? "file-card selected" : "file-card"}
                onClick={(event) => clickCard(app.id, event)}
                onDoubleClick={() => openApplication(app.id)}
                onDragStart={(event) => beginDrag(app.id, event)}
                onDragEnd={endDrag}
              >
                <h3>{app.full_name}</h3>
                <p>{app.iin}</p>
                <StatusBadge status={app.status} />
              </article>
            ))}
          </div>
        </div>
      </main>
    </section>
  );
}

type DetailsTab = "main" | "admissions" | "education" | "student";

export function ApplicationDetailsPage() {
  const { token, user } = useAuth();
  const { applicationId } = useParams();
  const location = useLocation();
  const [app, setApp] = useState<Application | null>(null);
  const [teachers, setTeachers] = useState<User[]>([]);
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [activeTab, setActiveTab] = useState<DetailsTab>("main");

  const bulkApplicationIds = useMemo(() => {
    const raw = new URLSearchParams(location.search).get("bulk");
    if (!raw) return [];
    return Array.from(new Set(raw.split(",").map((item) => Number(item)).filter((item) => Number.isInteger(item) && item > 0)));
  }, [location.search]);

  const isBulkMode = bulkApplicationIds.length > 1;

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
  useEffect(() => { setActiveTab("main"); }, [applicationId]);

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
      if (isBulkMode) {
        await apiFetch<Application[]>("/admin/applications/bulk/update", {
          method: "PATCH",
          token,
          body: JSON.stringify({ application_ids: bulkApplicationIds, update: body })
        });
        await load();
      } else {
        const updated = await apiFetch<Application>(`/admin/applications/${app.id}`, { method: "PATCH", token, body: JSON.stringify(body) });
        setApp(updated);
      }
      setSaved(isBulkMode ? `Сохранено для ${bulkApplicationIds.length} студентов` : "Сохранено");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const saveEducation = async (complete = false) => {
    if (!token || !app?.education_details) return;
    setError("");
    setSaved("");
    try {
      const details = app.education_details;
      const update = {
        curator_id: details.curator_id,
        group_number: details.group_number,
        course: details.course,
        payment_type: details.payment_type,
        is_state_grant: details.is_state_grant
      };
      if (isBulkMode) {
        await apiFetch("/education/applications/bulk/details", {
          method: "PATCH",
          token,
          body: JSON.stringify({ application_ids: bulkApplicationIds, update })
        });
        if (complete) {
          await apiFetch("/education/applications/bulk/save", {
            method: "POST",
            token,
            body: JSON.stringify({ application_ids: bulkApplicationIds })
          });
        }
      } else {
        await apiFetch(`/education/applications/${app.id}/details`, {
          method: "PATCH",
          token,
          body: JSON.stringify(update)
        });
        if (complete) {
          await apiFetch<Application>(`/education/applications/${app.id}/save`, { method: "POST", token });
        }
      }
      await load();
      setSaved(isBulkMode ? `Сохранено для ${bulkApplicationIds.length} студентов` : "Сохранено");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const action = async (name: "archive" | "accept" | "reject") => {
    if (!token || !app) return;
    setError("");
    try {
      if (name === "reject") {
        const reason = window.prompt("Причина отказа");
        if (!reason) return;
        await apiFetch(isBulkMode ? "/admin/applications/bulk/reject" : `/admin/applications/${app.id}/reject`, {
          method: "POST",
          token,
          body: JSON.stringify(isBulkMode ? { application_ids: bulkApplicationIds, reason } : { reason })
        });
      } else {
        await apiFetch(isBulkMode ? `/admin/applications/bulk/${name}` : `/admin/applications/${app.id}/${name}`, {
          method: "POST",
          token,
          body: isBulkMode ? JSON.stringify({ application_ids: bulkApplicationIds }) : undefined
        });
      }
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  if (!app) return <div className="admin-page"><EmptyState title="Загрузка" text="Открываем анкету." /></div>;
  const isTeacher = user?.role === "teacher";
  const canEducation = user?.role === "education_admin" || user?.role === "tech_admin";
  const hasStudentSheet = ["completed", "enrolled"].includes(app.status);
  const curatorName = teachers.find((teacher) => teacher.id === app.education_details?.curator_id)?.full_name ?? "Не назначен";
  const paymentLabel = app.education_details?.payment_type === "free"
    ? "Бесплатно"
    : app.education_details?.payment_type === "paid"
      ? "Платно"
      : "Не указано";
  const tabs: { id: DetailsTab; label: string }[] = [
    { id: "main", label: "Основные данные" },
    ...(!isTeacher ? [{ id: "admissions" as DetailsTab, label: "Приемная комиссия" }] : []),
    ...(canEducation ? [{ id: "education" as DetailsTab, label: "Учебная часть" }] : []),
    ...(hasStudentSheet ? [{ id: "student" as DetailsTab, label: "Данные студента" }] : []),
  ];

  return (
    <section className="admin-page details-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Анкета #{app.id}</p>
          <h2>{app.full_name}</h2>
        </div>
        <StatusBadge status={app.status} />
      </div>
      {isBulkMode && (
        <div className="bulk-edit-banner">
          <strong>Сейчас вы меняете {bulkApplicationIds.length} студентов.</strong>
          <span>Сохранение применит значения из этой анкеты ко всем выбранным карточкам.</span>
        </div>
      )}
      {error && <div className="form-error">{error}</div>}
      {saved && <div className="form-success">{saved}</div>}

      <section className="details-shell">
        <div className="details-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={tab.id === activeTab ? "details-tab active" : "details-tab"}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "main" && (
          <form className="panel-form tab-panel">
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
        )}

        {activeTab === "admissions" && !isTeacher && (
          <form className="panel-form tab-panel">
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
              <button type="button" onClick={() => saveApplication()}><Save size={16} /> Сохранить</button>
              <button type="button" onClick={() => action("archive")}><Archive size={16} /> Архивировать</button>
              <button type="button" onClick={() => action("reject")}><X size={16} /> Отклонить</button>
              <button type="button" onClick={() => action("accept")}><Check size={16} /> Принять</button>
            </div>
          </form>
        )}

        {activeTab === "education" && canEducation && (
          <form className="panel-form tab-panel">
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

        {activeTab === "student" && hasStudentSheet && (
          <div className="student-sheet">
            <dl>
              <div><dt>ИИН</dt><dd>{app.iin}</dd></div>
              <div><dt>ФИО</dt><dd>{app.full_name}</dd></div>
              <div><dt>Дата рождения</dt><dd>{formatDate(app.birth_date)}</dd></div>
              <div><dt>Место жительства</dt><dd>{app.admission_details?.residence_address ?? "Не указано"}</dd></div>
              <div><dt>Email</dt><dd>{app.email}</dd></div>
              <div><dt>Телефон</dt><dd>{app.phone}</dd></div>
              <div><dt>База поступления</dt><dd>{app.admission_details?.base_class ?? "Не указано"}</dd></div>
              <div><dt>Курс</dt><dd>{app.education_details?.course ?? "Не указано"}</dd></div>
              <div><dt>Группа</dt><dd>{app.education_details?.group_number ?? "Не указана"}</dd></div>
              <div><dt>Куратор</dt><dd>{curatorName}</dd></div>
              <div><dt>Квалификация</dt><dd>{app.admission_details?.qualification ?? "Не указана"}</dd></div>
              <div><dt>Специальность</dt><dd>{app.admission_details?.specialty ?? "Не указана"}</dd></div>
              <div><dt>Оплата</dt><dd>{paymentLabel}</dd></div>
            </dl>
          </div>
        )}
      </section>
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
