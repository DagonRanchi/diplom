import {
  Archive,
  Check,
  ChevronRight,
  FileSpreadsheet,
  FolderPlus,
  MessageCircle,
  Pencil,
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
  DocumentType,
  FolderNode,
  PortalInfo,
  roleLabels,
  statusLabels,
  User,
} from "../../api/client";
import { EmptyState, StatusBadge } from "../../components/Layout";
import { useAuth } from "../../context/AuthContext";

const statusOptions = Object.keys(statusLabels);

type CaseDraft = {
  iin: string;
  birth_date: string;
  full_name: string;
  email: string;
  phone: string;
  status: string;
  document_type: string;
  department: string;
  position: string;
  registry_number: string;
  topic: string;
};

type DetailsTab = "person" | "document" | "execution" | "summary";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU").format(new Date(value));
}

function caseDraft(app: Application): CaseDraft {
  return {
    iin: app.iin,
    birth_date: app.birth_date,
    full_name: app.full_name,
    email: app.email,
    phone: app.phone,
    status: app.status,
    document_type: app.admission_details?.benefit_group ?? "",
    department: app.admission_details?.residence_address ?? "",
    position: app.admission_details?.base_class ?? "",
    registry_number: app.admission_details?.qualification ?? "",
    topic: app.admission_details?.specialty ?? "",
  };
}

function flattenFolders(nodes: FolderNode[]): FolderNode[] {
  return nodes.flatMap((node) => [node, ...flattenFolders(node.children ?? [])]);
}

export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("tech@umz.local");
  const [password, setPassword] = useState("admin12345");
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) navigate("/portal/overview");
  }, [user, navigate]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/portal/overview");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <img src="/logo_umz.svg" alt="УМЗ" />
        <p className="eyebrow">Вход сотрудников</p>
        <h1>Портал документооборота</h1>
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
  const [cases, setCases] = useState<Application[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);

  useEffect(() => {
    if (!token) return;
    void apiFetch<Application[]>("/admin/applications?limit=500", { token }).then(setCases);
    void apiFetch<Chat[]>("/admin/chats", { token }).then(setChats).catch(() => setChats([]));
  }, [token]);

  const counts = statusOptions.map((status) => ({ status, count: cases.filter((item) => item.status === status).length }));

  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Сводка</p>
          <h2>Рабочий день, {user?.full_name}</h2>
        </div>
        <Link to="/portal/registry" className="secondary-button"><FileSpreadsheet size={16} /> Открыть реестр</Link>
      </div>
      <div className="metric-grid">
        <article><strong>{cases.length}</strong><span>Карточек доступно</span></article>
        <article><strong>{cases.filter((item) => item.status === "new").length}</strong><span>Новых</span></article>
        <article><strong>{cases.filter((item) => item.status === "document_review").length}</strong><span>На регистрации</span></article>
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
  const [cases, setCases] = useState<Application[]>([]);
  const [drafts, setDrafts] = useState<Record<number, CaseDraft>>({});
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    if (!token) return;
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    params.set("limit", "500");
    const items = await apiFetch<Application[]>(`/admin/applications?${params.toString()}`, { token });
    setCases(items);
    setDrafts(Object.fromEntries(items.map((item) => [item.id, caseDraft(item)])));
    setSelected([]);
  };

  useEffect(() => {
    void apiFetch<PortalInfo>("/public/portal-info").then((info) => setDocumentTypes(info.specialties));
  }, []);

  useEffect(() => {
    void load();
  }, [token, status]);

  const updateDraft = (id: number, field: keyof CaseDraft, value: string) => {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], [field]: value } }));
  };

  const saveRow = async (id: number) => {
    if (!token) return;
    const draft = drafts[id];
    setError("");
    setMessage("");
    try {
      await apiFetch<Application>(`/admin/applications/${id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          iin: draft.iin,
          birth_date: draft.birth_date,
          full_name: draft.full_name,
          email: draft.email,
          phone: draft.phone,
          status: draft.status,
          admission_details: {
            benefit_group: draft.document_type,
            residence_address: draft.department,
            base_class: draft.position,
            qualification: draft.registry_number,
            specialty: draft.topic,
          },
        }),
      });
      setMessage(`Строка #${id} сохранена`);
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const saveSelected = async () => {
    for (const id of selected) {
      await saveRow(id);
    }
  };

  const bulk = async (action: "archive" | "accept" | "reject") => {
    if (!token || !selected.length) return;
    setError("");
    try {
      if (action === "reject") {
        const reason = window.prompt("Причина отклонения");
        if (!reason) return;
        await apiFetch("/admin/applications/bulk/reject", { method: "POST", token, body: JSON.stringify({ application_ids: selected, reason }) });
      } else {
        await apiFetch(`/admin/applications/bulk/${action}`, { method: "POST", token, body: JSON.stringify({ application_ids: selected }) });
      }
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const toggle = (id: number) => {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  return (
    <section className="admin-page registry-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Табличная обработка</p>
          <h2>Реестр документов и анкет</h2>
        </div>
        <button className="secondary-button" onClick={load}><RefreshCw size={16} /> Обновить</button>
      </div>

      <div className="toolbar">
        <div className="search-box">
          <Search size={18} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && load()} placeholder="ФИО, ИИН, телефон, email, тема" />
        </div>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Все статусы</option>
          {statusOptions.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
        </select>
      </div>

      <div className="bulk-panel">
        <span>Выбрано: {selected.length}</span>
        <button onClick={saveSelected}><Save size={16} /> Сохранить выбранные</button>
        <button onClick={() => bulk("accept")}><Check size={16} /> В канцелярию</button>
        <button onClick={() => bulk("archive")}><Archive size={16} /> В архив</button>
        <button onClick={() => bulk("reject")}><X size={16} /> Отклонить</button>
      </div>
      {message && <div className="form-success">{message}</div>}
      {error && <div className="form-error">{error}</div>}

      <div className="data-table registry-table">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Сотрудник</th>
              <th>ИИН / дата</th>
              <th>Контакты</th>
              <th>Тип</th>
              <th>Подразделение</th>
              <th>Тема / номер</th>
              <th>Статус</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => {
              const draft = drafts[item.id] ?? caseDraft(item);
              return (
                <tr key={item.id}>
                  <td><input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} /></td>
                  <td>
                    <input value={draft.full_name} onChange={(event) => updateDraft(item.id, "full_name", event.target.value)} />
                    <Link to={`/portal/cases/${item.id}`}>Карточка #{item.id}</Link>
                  </td>
                  <td>
                    <input value={draft.iin} onChange={(event) => updateDraft(item.id, "iin", event.target.value.replace(/\D/g, "").slice(0, 12))} />
                    <input type="date" value={draft.birth_date} onChange={(event) => updateDraft(item.id, "birth_date", event.target.value)} />
                  </td>
                  <td>
                    <input value={draft.phone} onChange={(event) => updateDraft(item.id, "phone", event.target.value)} />
                    <input value={draft.email} onChange={(event) => updateDraft(item.id, "email", event.target.value)} />
                  </td>
                  <td>
                    <select value={draft.document_type} onChange={(event) => updateDraft(item.id, "document_type", event.target.value)}>
                      <option value="">Не указан</option>
                      {documentTypes.map((type) => <option key={type.id} value={type.name}>{type.name}</option>)}
                    </select>
                  </td>
                  <td>
                    <input value={draft.department} onChange={(event) => updateDraft(item.id, "department", event.target.value)} placeholder="Подразделение" />
                    <input value={draft.position} onChange={(event) => updateDraft(item.id, "position", event.target.value)} placeholder="Должность" />
                  </td>
                  <td>
                    <input value={draft.topic} onChange={(event) => updateDraft(item.id, "topic", event.target.value)} placeholder="Тема" />
                    <input value={draft.registry_number} onChange={(event) => updateDraft(item.id, "registry_number", event.target.value)} placeholder="Номер" />
                  </td>
                  <td>
                    <select value={draft.status} onChange={(event) => updateDraft(item.id, "status", event.target.value)}>
                      {statusOptions.map((statusItem) => <option key={statusItem} value={statusItem}>{statusLabels[statusItem]}</option>)}
                    </select>
                  </td>
                  <td>
                    <button className="icon-row-button" onClick={() => saveRow(item.id)} title="Сохранить строку"><Save size={16} /></button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!cases.length && <EmptyState title="Записей нет" text="Измените фильтр или обновите реестр." />}
      </div>
    </section>
  );
}

export function FileManagerPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [tree, setTree] = useState<FolderNode[]>([]);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [cases, setCases] = useState<Application[]>([]);
  const [selected, setSelected] = useState<number[]>([]);

  const folders = useMemo(() => flattenFolders(tree), [tree]);

  const loadTree = async () => {
    if (!token) return;
    const nodes = await apiFetch<FolderNode[]>("/folders/tree", { token });
    setTree(nodes);
    if (!folderId && nodes[0]) setFolderId(nodes[0].id);
  };

  const loadCases = async () => {
    if (!token || !folderId) return;
    const items = await apiFetch<Application[]>(`/admin/applications?folder_id=${folderId}&limit=500`, { token });
    setCases(items);
    setSelected([]);
  };

  useEffect(() => { void loadTree(); }, [token]);
  useEffect(() => { void loadCases(); }, [token, folderId]);

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

  const moveSelected = async (targetFolderId: number) => {
    if (!token || !selected.length) return;
    await apiFetch("/folders/move-items", {
      method: "POST",
      token,
      body: JSON.stringify({ application_ids: selected, target_folder_id: targetFolderId })
    });
    await loadCases();
    await loadTree();
  };

  const renderNode = (node: FolderNode, depth = 0) => (
    <div key={node.id}>
      <button
        className={node.id === folderId ? "folder-node active" : "folder-node"}
        style={{ paddingLeft: 12 + depth * 14 }}
        onClick={() => setFolderId(node.id)}
        onDoubleClick={() => selected.length && void moveSelected(node.id)}
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
          <h2>Архив</h2>
          <button className="icon-button" onClick={createFolder} title="Создать папку"><FolderPlus size={18} /></button>
        </div>
        <div className="folder-tree">{tree.map((node) => renderNode(node))}</div>
      </aside>
      <main className="file-pane">
        <div className="pane-header">
          <div>
            <p className="eyebrow">Папочная сортировка</p>
            <h2>{folders.find((item) => item.id === folderId)?.name ?? "Папка"}</h2>
          </div>
          <div className="toolbar compact">
            <button onClick={renameFolder}><Pencil size={16} /> Переименовать</button>
            <button onClick={deleteFolder}><Trash2 size={16} /> Удалить</button>
          </div>
        </div>
        <div className="bulk-panel">
          <span>Выбрано: {selected.length}</span>
          <span className="muted">Отметьте карточки и дважды нажмите папку слева, чтобы перенести их.</span>
        </div>
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Карточка</th>
                <th>Сотрудник</th>
                <th>Подразделение</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((item) => (
                <tr key={item.id}>
                  <td><input type="checkbox" checked={selected.includes(item.id)} onChange={() => setSelected((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} /></td>
                  <td><Link to={`/portal/cases/${item.id}`}>{item.admission_details?.specialty ?? `Карточка #${item.id}`}</Link></td>
                  <td>{item.full_name}</td>
                  <td>{item.admission_details?.residence_address ?? "Не указано"}</td>
                  <td><StatusBadge status={item.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!cases.length && <EmptyState title="Папка пуста" text="Переместите сюда карточки из реестра или другой папки." />}
        </div>
      </main>
    </section>
  );
}

export function ApplicationDetailsPage() {
  const { token, user } = useAuth();
  const { applicationId } = useParams();
  const [app, setApp] = useState<Application | null>(null);
  const [draft, setDraft] = useState<CaseDraft | null>(null);
  const [managers, setManagers] = useState<User[]>([]);
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [activeTab, setActiveTab] = useState<DetailsTab>("person");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = async () => {
    if (!token || !applicationId) return;
    const item = await apiFetch<Application>(`/admin/applications/${applicationId}`, { token });
    setApp(item);
    setDraft(caseDraft(item));
  };

  useEffect(() => {
    void load();
  }, [token, applicationId]);

  useEffect(() => {
    if (!token) return;
    void apiFetch<User[]>("/users?role=department_manager", { token }).then(setManagers).catch(() => setManagers([]));
    void apiFetch<PortalInfo>("/public/portal-info").then((info) => setDocumentTypes(info.specialties));
  }, [token]);

  const updateDraft = (field: keyof CaseDraft, value: string) => {
    setDraft((current) => current ? { ...current, [field]: value } : current);
  };

  const saveCase = async () => {
    if (!token || !app || !draft) return;
    setError("");
    setSaved("");
    try {
      await apiFetch<Application>(`/admin/applications/${app.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          iin: draft.iin,
          birth_date: draft.birth_date,
          full_name: draft.full_name,
          email: draft.email,
          phone: draft.phone,
          status: draft.status,
          admission_details: {
            benefit_group: draft.document_type,
            residence_address: draft.department,
            base_class: draft.position,
            qualification: draft.registry_number,
            specialty: draft.topic,
          },
        }),
      });
      setSaved("Карточка сохранена");
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const updateExecution = async (complete: boolean) => {
    if (!token || !app) return;
    setError("");
    setSaved("");
    try {
      await apiFetch(`/document-control/applications/${app.id}/details`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          curator_id: app.education_details?.curator_id ?? null,
          group_number: app.education_details?.group_number ?? "",
          course: app.education_details?.course ?? 2,
          payment_type: app.education_details?.payment_type ?? "standard",
          is_state_grant: Boolean(app.education_details?.is_state_grant),
        }),
      });
      if (complete) {
        await apiFetch<Application>(`/document-control/applications/${app.id}/save`, { method: "POST", token });
      }
      setSaved(complete ? "Документ исполнен" : "Параметры исполнения сохранены");
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const setExecutionField = (field: "curator_id" | "group_number" | "course" | "payment_type" | "is_state_grant", value: string | number | boolean | null) => {
    setApp((current) => current ? {
      ...current,
      education_details: {
        id: current.education_details?.id ?? 0,
        is_state_grant: false,
        ...current.education_details,
        [field]: value,
      }
    } : current);
  };

  const action = async (name: "archive" | "accept" | "reject") => {
    if (!token || !app) return;
    try {
      if (name === "reject") {
        const reason = window.prompt("Причина отклонения");
        if (!reason) return;
        await apiFetch(`/admin/applications/${app.id}/reject`, { method: "POST", token, body: JSON.stringify({ reason }) });
      } else {
        await apiFetch(`/admin/applications/${app.id}/${name}`, { method: "POST", token });
      }
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  if (!app || !draft) {
    return <div className="admin-page"><EmptyState title="Загрузка" text="Открываем карточку документооборота." /></div>;
  }

  const canExecute = user?.role === "document_admin" || user?.role === "tech_admin";
  const tabs: { id: DetailsTab; label: string }[] = [
    { id: "person", label: "Сотрудник" },
    { id: "document", label: "Документ" },
    ...(canExecute ? [{ id: "execution" as DetailsTab, label: "Исполнение" }] : []),
    { id: "summary", label: "Итог" },
  ];

  return (
    <section className="admin-page details-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Карточка #{app.id}</p>
          <h2>{draft.topic || draft.full_name}</h2>
        </div>
        <StatusBadge status={app.status} />
      </div>
      {error && <div className="form-error">{error}</div>}
      {saved && <div className="form-success">{saved}</div>}

      <section className="details-shell">
        <div className="details-tabs">
          {tabs.map((tab) => (
            <button key={tab.id} type="button" className={tab.id === activeTab ? "details-tab active" : "details-tab"} onClick={() => setActiveTab(tab.id)}>
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "person" && (
          <form className="panel-form tab-panel">
            <label><span>ИИН</span><input value={draft.iin} onChange={(e) => updateDraft("iin", e.target.value.replace(/\D/g, "").slice(0, 12))} /></label>
            <label><span>Дата рождения</span><input type="date" value={draft.birth_date} onChange={(e) => updateDraft("birth_date", e.target.value)} /></label>
            <label><span>ФИО</span><input value={draft.full_name} onChange={(e) => updateDraft("full_name", e.target.value)} /></label>
            <label><span>Email</span><input value={draft.email} onChange={(e) => updateDraft("email", e.target.value)} /></label>
            <label><span>Телефон</span><input value={draft.phone} onChange={(e) => updateDraft("phone", e.target.value)} /></label>
            <button type="button" className="primary-button" onClick={saveCase}><Save size={16} /> Сохранить</button>
          </form>
        )}

        {activeTab === "document" && (
          <form className="panel-form tab-panel">
            <label>
              <span>Тип документа</span>
              <select value={draft.document_type} onChange={(e) => updateDraft("document_type", e.target.value)}>
                <option value="">Выберите</option>
                {documentTypes.map((type) => <option key={type.id} value={type.name}>{type.name}</option>)}
              </select>
            </label>
            <label><span>Подразделение</span><input value={draft.department} onChange={(e) => updateDraft("department", e.target.value)} /></label>
            <label><span>Должность</span><input value={draft.position} onChange={(e) => updateDraft("position", e.target.value)} /></label>
            <label><span>Регистрационный номер</span><input value={draft.registry_number} onChange={(e) => updateDraft("registry_number", e.target.value)} /></label>
            <label className="span-2"><span>Тема</span><input value={draft.topic} onChange={(e) => updateDraft("topic", e.target.value)} /></label>
            <label>
              <span>Статус</span>
              <select value={draft.status} onChange={(e) => updateDraft("status", e.target.value)}>
                {statusOptions.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
              </select>
            </label>
            <div className="action-row">
              <button type="button" onClick={saveCase}><Save size={16} /> Сохранить</button>
              <button type="button" onClick={() => action("archive")}><Archive size={16} /> Архив</button>
              <button type="button" onClick={() => action("reject")}><X size={16} /> Отклонить</button>
              <button type="button" className="primary-button" onClick={() => action("accept")}><Check size={16} /> В канцелярию</button>
            </div>
          </form>
        )}

        {activeTab === "execution" && canExecute && (
          <form className="panel-form tab-panel">
            <label>
              <span>Ответственный руководитель</span>
              <select value={app.education_details?.curator_id ?? ""} onChange={(e) => setExecutionField("curator_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="">Выберите</option>
                {managers.map((manager) => <option key={manager.id} value={manager.id}>{manager.full_name}</option>)}
              </select>
            </label>
            <label><span>Код реестра</span><input value={app.education_details?.group_number ?? ""} onChange={(e) => setExecutionField("group_number", e.target.value)} placeholder="UMZ-2026-HR" /></label>
            <label><span>Приоритет</span><input type="number" min={1} max={5} value={app.education_details?.course ?? ""} onChange={(e) => setExecutionField("course", Number(e.target.value))} /></label>
            <label>
              <span>Режим обработки</span>
              <select value={app.education_details?.payment_type ?? ""} onChange={(e) => setExecutionField("payment_type", e.target.value)}>
                <option value="">Выберите</option>
                <option value="standard">Стандартный</option>
                <option value="urgent">Срочный</option>
              </select>
            </label>
            <label className="checkbox-line"><input type="checkbox" checked={Boolean(app.education_details?.is_state_grant)} onChange={(e) => setExecutionField("is_state_grant", e.target.checked)} /> Ограниченный доступ</label>
            <div className="action-row">
              <button type="button" onClick={() => updateExecution(false)}><Save size={16} /> Сохранить</button>
              <button type="button" className="primary-button" onClick={() => updateExecution(true)}><Check size={16} /> Исполнить</button>
            </div>
          </form>
        )}

        {activeTab === "summary" && (
          <div className="student-sheet">
            <dl>
              <div><dt>ФИО</dt><dd>{app.full_name}</dd></div>
              <div><dt>ИИН</dt><dd>{app.iin}</dd></div>
              <div><dt>Дата рождения</dt><dd>{formatDate(app.birth_date)}</dd></div>
              <div><dt>Тип документа</dt><dd>{app.admission_details?.benefit_group ?? "Не указан"}</dd></div>
              <div><dt>Подразделение</dt><dd>{app.admission_details?.residence_address ?? "Не указано"}</dd></div>
              <div><dt>Должность</dt><dd>{app.admission_details?.base_class ?? "Не указана"}</dd></div>
              <div><dt>Тема</dt><dd>{app.admission_details?.specialty ?? "Не указана"}</dd></div>
              <div><dt>Регистрационный номер</dt><dd>{app.admission_details?.qualification ?? "Не указан"}</dd></div>
              <div><dt>Email</dt><dd>{app.email}</dd></div>
              <div><dt>Телефон</dt><dd>{app.phone}</dd></div>
              <div><dt>Создано</dt><dd>{formatDate(app.created_at)}</dd></div>
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
  const base = location.pathname.startsWith("/operator") ? "/operator/messages" : "/portal/messages";
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
        <h2>Чаты карточек</h2>
        {chats.map((chat) => (
          <button key={chat.id} className={chat.id === activeId ? "active" : ""} onClick={() => navigate(`${base}/${chat.id}`)}>
            <MessageCircle size={18} />
            <span>{chat.application?.admission_details?.specialty ?? chat.application?.full_name ?? `Карточка #${chat.application_id}`}</span>
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
            <div key={message.id} className={`message-bubble ${message.sender_type === "employee" ? "mine" : "staff"}`}>
              <span>{message.sender_type === "employee" ? "Сотрудник" : roleLabels[message.sender_type as keyof typeof roleLabels] ?? "Портал"}</span>
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
  const [form, setForm] = useState({ full_name: "", email: "", password: "admin12345", role: "department_manager" });

  const load = async () => {
    if (!token) return;
    setUsers(await apiFetch<User[]>("/users", { token }));
  };

  useEffect(() => { void load(); }, [token]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    await apiFetch("/users", { method: "POST", token, body: JSON.stringify(form) });
    setForm({ full_name: "", email: "", password: "admin12345", role: "department_manager" });
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
          <p className="eyebrow">Администрирование</p>
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
          <p className="eyebrow">Система</p>
          <h2>Параметры портала</h2>
        </div>
      </div>
      <div className="settings-grid">
        <article>
          <h3>Backend</h3>
          <p>FastAPI, PostgreSQL, SQLAlchemy, Alembic, JWT.</p>
        </article>
        <article>
          <h3>Frontend</h3>
          <p>React, Vite, TypeScript, табличный реестр и маршруты рабочих зон.</p>
        </article>
        <article>
          <h3>Workflow</h3>
          <p>Новая карточка, HR-проверка, канцелярия, согласование, исполнение, архив.</p>
        </article>
      </div>
    </section>
  );
}
