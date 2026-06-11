import {
  Archive,
  Check,
  ChevronRight,
  Download,
  Folder as FolderIcon,
  FolderPlus,
  GraduationCap,
  MessageCircle,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
  UserMinus,
  UserPlus,
  X,
} from "lucide-react";
import { DragEvent as ReactDragEvent, FormEvent, MouseEvent as ReactMouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  API_URL,
  apiFetch,
  apiMessage,
  Application,
  Chat,
  ChatMessage,
  ContestEntry,
  FolderNode,
  roleLabels,
  Specialty,
  statusLabels,
  User,
} from "../../api/client";
import { EmptyState, StatusBadge } from "../../components/Layout";
import { ChatAttachments } from "../../components/ChatAttachments";
import { useAuth } from "../../context/AuthContext";

const statusOptions = Object.keys(statusLabels);
const admissionsActionableStatuses = new Set(["new", "in_admissions_review"]);
const educationCompletableStatuses = new Set(["accepted_by_admissions", "education_review"]);

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU").format(new Date(value));
}

function emptyFieldClass(value: unknown) {
  return value === null || value === undefined || value === "" ? "empty-field" : undefined;
}

function flattenFolders(nodes: FolderNode[]): FolderNode[] {
  return nodes.flatMap((node) => [node, ...flattenFolders(node.children ?? [])]);
}

function findFolderPath(nodes: FolderNode[], folderId: number, path: FolderNode[] = []): FolderNode[] {
  for (const node of nodes) {
    const nextPath = [...path, node];
    if (node.id === folderId) return nextPath;
    const childPath = findFolderPath(node.children ?? [], folderId, nextPath);
    if (childPath.length) return childPath;
  }
  return [];
}

function scholarshipAmount(specialty: string | null | undefined, performance: string | null | undefined) {
  let amount = 41_800;
  if (performance === "excellent") amount += 5_000;
  if (specialty?.trim().toUpperCase().startsWith("3W")) amount += 3_000;
  return amount;
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
  const { token, user } = useAuth();
  const [apps, setApps] = useState<Application[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [dateMode, setDateMode] = useState<"exact" | "range">("exact");
  const [exactDate, setExactDate] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");

  const load = async () => {
    if (!token) return;
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (dateMode === "exact" && exactDate) {
      params.set("created_from", exactDate);
      params.set("created_to", exactDate);
    }
    if (dateMode === "range") {
      if (dateFrom) params.set("created_from", dateFrom);
      if (dateTo) params.set("created_to", dateTo);
    }
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

  const selectedApps = apps.filter((app) => selected.includes(app.id));
  const canUseAdmissionsActions = user?.role === "admissions_admin" || user?.role === "tech_admin";
  const canProcessSelection = Boolean(
    selectedApps.length
    && selectedApps.length === selected.length
    && selectedApps.every((app) => admissionsActionableStatuses.has(app.status))
  );

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
        <div className="date-filter">
          <select value={dateMode} onChange={(event) => setDateMode(event.target.value as "exact" | "range")}>
            <option value="exact">Определенная дата</option>
            <option value="range">Период</option>
          </select>
          {dateMode === "exact" ? (
            <input type="date" value={exactDate} onChange={(event) => setExactDate(event.target.value)} aria-label="Дата заявки" />
          ) : (
            <>
              <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} aria-label="Дата от" />
              <span>по</span>
              <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} aria-label="Дата до" />
            </>
          )}
          <button type="button" onClick={load}>Применить</button>
        </div>
      </div>
      <div className="bulk-panel">
        <span>Выбрано: {selected.length}</span>
        {canUseAdmissionsActions && canProcessSelection && (
          <>
            <button onClick={() => bulk("archive")}><Archive size={16} /> Архивировать</button>
            <button onClick={() => bulk("reject")}><X size={16} /> Отклонить</button>
          </>
        )}
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
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [tree, setTree] = useState<FolderNode[]>([]);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [deletingStudents, setDeletingStudents] = useState(false);
  const [draggingIds, setDraggingIds] = useState<number[]>([]);
  const [dropTargetId, setDropTargetId] = useState<number | null>(null);
  const [selectionBox, setSelectionBox] = useState<{ startX: number; startY: number; x: number; y: number } | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);

  const folders = useMemo(() => flattenFolders(tree), [tree]);
  const currentFolder = folders.find((item) => item.id === folderId) ?? null;
  const childFolders = folderId === null ? tree : currentFolder?.children ?? [];
  const folderPath = folderId === null ? [] : findFolderPath(tree, folderId);

  const loadTree = async () => {
    if (!token) return;
    const nodes = await apiFetch<FolderNode[]>("/folders/tree", { token });
    setTree(nodes);
  };

  const loadApps = async () => {
    if (!token) return;
    if (!folderId) {
      setApps([]);
      setSelected([]);
      return;
    }
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

  const deleteAllStudents = async () => {
    if (!token || !folderId || !apps.length) return;
    const confirmed = window.confirm(
      `Удалить всех студентов из папки «${currentFolder?.name ?? ""}» (${apps.length})?\n\nЭто действие нельзя отменить.`
    );
    if (!confirmed) return;

    setError("");
    setSuccess("");
    setDeletingStudents(true);
    try {
      const result = await apiFetch<{ deleted: number }>(`/folders/${folderId}/students`, {
        method: "DELETE",
        token,
      });
      setSuccess(`Удалено студентов: ${result.deleted}`);
      await Promise.all([loadApps(), loadTree()]);
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setDeletingStudents(false);
    }
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

  const dropApplicationsOnFolder = (event: ReactDragEvent<HTMLElement>, targetFolderId: number) => {
    event.preventDefault();
    const payload = event.dataTransfer.getData("application/json");
    const ids = payload ? JSON.parse(payload) as number[] : draggingIds;
    void moveApplications(ids, targetFolderId);
    endDrag();
  };

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
          dropApplicationsOnFolder(event, node.id);
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
        <div className="folder-tree">
          <button className={folderId === null ? "folder-node active" : "folder-node"} onClick={() => setFolderId(null)}>
            <FolderIcon size={15} />
            <span>Корень</span>
          </button>
          {tree.map((node) => renderNode(node))}
        </div>
      </aside>
      <main className="file-pane">
        <div className="pane-header">
          <div>
            <p className="eyebrow">Файловый менеджер</p>
            <h2>{currentFolder?.name ?? "Корень"}</h2>
            <div className="breadcrumb-row">
              <button type="button" onClick={() => setFolderId(null)}>Корень</button>
              {folderPath.map((folder) => (
                <span key={folder.id}>
                  <span>/</span>
                  <button type="button" onClick={() => setFolderId(folder.id)}>{folder.name}</button>
                </span>
              ))}
            </div>
          </div>
          <div className="toolbar compact">
            {folderId !== null && <button onClick={renameFolder}><Pencil size={16} /> Переименовать</button>}
            {folderId !== null && <button onClick={deleteFolder}><Trash2 size={16} /> Удалить</button>}
            {user?.role === "tech_admin" && folderId !== null && (
              <button className="danger-button" onClick={deleteAllStudents} disabled={deletingStudents || !apps.length}>
                <UserMinus size={16} /> {deletingStudents ? "Удаление..." : "Удалить всех студентов"}
              </button>
            )}
          </div>
        </div>
        {error && <div className="form-error">{error}</div>}
        {success && <div className="form-success">{success}</div>}
        <div className="bulk-panel">
          <span>Выбрано: {selected.length}</span>
          <span className="muted">Выделите рамкой или кликом, затем перетащите в папку слева.</span>
        </div>
        <div className="file-grid-shell" ref={gridRef} onMouseDown={startSelection}>
          {selectionBox && <div className="selection-box" style={selectionStyle} />}
          <div className="file-grid">
            {childFolders.map((folder) => (
              <article
                key={`folder-${folder.id}`}
                className={folder.id === dropTargetId ? "file-card folder-card drop-target" : "file-card folder-card"}
                onClick={() => setSelected([])}
                onDoubleClick={() => setFolderId(folder.id)}
                onDragOver={(event) => {
                  if (!draggingIds.length) return;
                  event.preventDefault();
                  setDropTargetId(folder.id);
                }}
                onDragLeave={() => setDropTargetId((current) => current === folder.id ? null : current)}
                onDrop={(event) => dropApplicationsOnFolder(event, folder.id)}
              >
                <FolderIcon size={32} />
                <h3>{folder.name}</h3>
                <small>{folder.item_count} анкет</small>
              </article>
            ))}
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
          {!childFolders.length && !apps.length && (
            <EmptyState title="Папка пуста" text="Создайте подпапку или переместите сюда анкеты." />
          )}
        </div>
      </main>
    </section>
  );
}

export function ContestPage() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [entries, setEntries] = useState<ContestEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState<[string, string, string] | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showBulkEdit, setShowBulkEdit] = useState(false);
  const [bulkForm, setBulkForm] = useState({
    benefit_group: "",
    residence_address: "",
    base_class: "",
    enrollment_type: "",
    locality_type: "",
    instruction_language: "",
    study_form: "",
    needs_dormitory: "",
  });
  const [selectionBox, setSelectionBox] = useState<{ startX: number; startY: number; x: number; y: number } | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);

  const load = async () => {
    if (!token) return;
    try {
      const items = await apiFetch<ContestEntry[]>("/contest/entries", { token });
      setEntries(items);
      setError("");
      const currentPathExists = selectedPath && items.some((item) => (
        item.base_class === selectedPath[0]
        && item.qualification === selectedPath[1]
        && item.specialty === selectedPath[2]
      ));
      if (!currentPathExists && items[0]) {
        setSelectedPath([items[0].base_class, items[0].qualification, items[0].specialty]);
      } else if (!items.length) {
        setSelectedPath(null);
      }
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  useEffect(() => { void load(); }, [token]);
  useEffect(() => { setSelected([]); }, [selectedPath]);

  const tree = useMemo(() => {
    const result: Record<string, Record<string, string[]>> = {};
    entries.forEach((entry) => {
      result[entry.base_class] ??= {};
      result[entry.base_class][entry.qualification] ??= [];
      if (!result[entry.base_class][entry.qualification].includes(entry.specialty)) {
        result[entry.base_class][entry.qualification].push(entry.specialty);
      }
    });
    return result;
  }, [entries]);

  const visibleEntries = selectedPath
    ? entries.filter((entry) => (
        entry.base_class === selectedPath[0]
        && entry.qualification === selectedPath[1]
        && entry.specialty === selectedPath[2]
      ))
    : [];
  const canEdit = user?.role === "tech_admin" || user?.role === "admissions_admin";
  const canDecide = canEdit || user?.role === "education_admin";

  const clickCard = (choiceId: number, event: ReactMouseEvent<HTMLElement>) => {
    if (event.ctrlKey || event.metaKey) {
      setSelected((current) => current.includes(choiceId)
        ? current.filter((id) => id !== choiceId)
        : [...current, choiceId]);
      return;
    }
    setSelected((current) => current.includes(choiceId) && current.length > 1 ? current : [choiceId]);
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

    const onMouseMove = (moveEvent: MouseEvent) => {
      const x = moveEvent.clientX - bounds.left;
      const y = moveEvent.clientY - bounds.top;
      setSelectionBox({ startX, startY, x, y });
      const left = Math.min(startX, x);
      const top = Math.min(startY, y);
      const right = Math.max(startX, x);
      const bottom = Math.max(startY, y);
      const ids = Array.from(grid.querySelectorAll<HTMLElement>("[data-choice-id]"))
        .filter((card) => {
          const rect = card.getBoundingClientRect();
          const cardLeft = rect.left - bounds.left;
          const cardTop = rect.top - bounds.top;
          return cardLeft < right
            && cardLeft + rect.width > left
            && cardTop < bottom
            && cardTop + rect.height > top;
        })
        .map((card) => Number(card.dataset.choiceId))
        .filter(Boolean);
      setSelected(ids);
    };
    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setSelectionBox(null);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  const bulkDecision = async (decision: "accept" | "reject") => {
    if (!token || !selected.length) return;
    const action = decision === "accept" ? "принять" : "отклонить";
    if (!window.confirm(`${action[0].toUpperCase()}${action.slice(1)} выбранные конкурсные заявки (${selected.length})?`)) return;
    setError("");
    setSuccess("");
    try {
      await apiFetch(`/contest/bulk/${decision}`, {
        method: "POST",
        token,
        body: JSON.stringify({ choice_ids: selected }),
      });
      setSuccess(decision === "accept" ? "Выбранные заявки приняты" : "Выбранные направления отклонены");
      setSelected([]);
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const bulkUpdate = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !selected.length) return;
    const update = Object.fromEntries(
      Object.entries(bulkForm)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => [key, key === "needs_dormitory" ? value === "yes" : value])
    );
    if (!Object.keys(update).length) {
      setError("Выберите хотя бы одно поле для изменения");
      return;
    }
    setError("");
    setSuccess("");
    try {
      await apiFetch("/contest/bulk/update", {
        method: "PATCH",
        token,
        body: JSON.stringify({ choice_ids: selected, update }),
      });
      setShowBulkEdit(false);
      setSelected([]);
      setBulkForm({
        benefit_group: "",
        residence_address: "",
        base_class: "",
        enrollment_type: "",
        locality_type: "",
        instruction_language: "",
        study_form: "",
        needs_dormitory: "",
      });
      setSuccess(`Данные обновлены для ${selected.length} заявок`);
      await load();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const selectionStyle = selectionBox
    ? {
        left: Math.min(selectionBox.startX, selectionBox.x),
        top: Math.min(selectionBox.startY, selectionBox.y),
        width: Math.abs(selectionBox.x - selectionBox.startX),
        height: Math.abs(selectionBox.y - selectionBox.startY),
      }
    : undefined;

  return (
    <section className="file-manager contest-manager">
      <aside className="folder-pane">
        <div className="pane-header"><h2>Конкурс</h2></div>
        <div className="folder-tree">
          {Object.entries(tree).map(([baseClass, qualifications]) => (
            <div key={baseClass}>
              <div className="folder-node contest-level"><FolderIcon size={15} /><strong>{baseClass}</strong></div>
              {Object.entries(qualifications).map(([qualification, specialties]) => (
                <div key={`${baseClass}-${qualification}`}>
                  <div className="folder-node contest-level" style={{ paddingLeft: 28 }}>
                    <ChevronRight size={14} /><span>{qualification}</span>
                  </div>
                  {specialties.sort((left, right) => left.localeCompare(right, "ru")).map((specialty) => {
                    const path: [string, string, string] = [baseClass, qualification, specialty];
                    const active = selectedPath?.join("|") === path.join("|");
                    const count = entries.filter((entry) => (
                      entry.base_class === baseClass
                      && entry.qualification === qualification
                      && entry.specialty === specialty
                    )).length;
                    return (
                      <button
                        key={`${baseClass}-${qualification}-${specialty}`}
                        className={active ? "folder-node active" : "folder-node"}
                        style={{ paddingLeft: 48 }}
                        onClick={() => setSelectedPath(path)}
                      >
                        <FolderIcon size={14} />
                        <span>{specialty}</span>
                        <small>{count}</small>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          ))}
          {!entries.length && <span className="muted">На конкурсе пока никого нет.</span>}
        </div>
      </aside>
      <main className="file-pane">
        <div className="pane-header">
          <div>
            <p className="eyebrow">Конкурсный реестр</p>
            <h2>{selectedPath?.[2] ?? "Выберите специальность"}</h2>
            {selectedPath && <span className="muted">{selectedPath[0]} / {selectedPath[1]}</span>}
          </div>
          <button className="secondary-button" onClick={load}><RefreshCw size={16} /> Обновить</button>
        </div>
        {error && <div className="form-error">{error}</div>}
        {success && <div className="form-success">{success}</div>}
        <div className="bulk-panel">
          <span>Выбрано: {selected.length}</span>
          {visibleEntries.length > 0 && (
            <button type="button" onClick={() => setSelected(
              selected.length === visibleEntries.length ? [] : visibleEntries.map((entry) => entry.choice_id)
            )}>
              {selected.length === visibleEntries.length ? "Снять выделение" : "Выбрать все"}
            </button>
          )}
          {canEdit && selected.length > 0 && <button type="button" onClick={() => setShowBulkEdit(true)}><Pencil size={16} /> Изменить данные</button>}
          {canDecide && selected.length > 0 && <button type="button" onClick={() => bulkDecision("accept")}><Check size={16} /> Принять</button>}
          {canDecide && selected.length > 0 && <button type="button" onClick={() => bulkDecision("reject")}><X size={16} /> Отклонить</button>}
          <span className="muted">Выделяйте карточки кликом, Ctrl+кликом или рамкой.</span>
        </div>
        <div className="file-grid-shell" ref={gridRef} onMouseDown={startSelection}>
          {selectionBox && <div className="selection-box" style={selectionStyle} />}
          <div className="file-grid">
            {visibleEntries.map((entry) => (
              <article
                key={entry.choice_id}
                data-choice-id={entry.choice_id}
                className={selected.includes(entry.choice_id) ? "file-card selected" : "file-card"}
                onClick={(event) => clickCard(entry.choice_id, event)}
                onDoubleClick={() => navigate(`/admin/applications/${entry.application_id}?contestChoice=${entry.choice_id}`)}
              >
                <h3>{entry.full_name}</h3>
                <p>{entry.iin}</p>
                <StatusBadge status="in_contest" />
                <button
                  className="secondary-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    navigate(`/admin/applications/${entry.application_id}?contestChoice=${entry.choice_id}`);
                  }}
                >
                  Открыть
                </button>
              </article>
            ))}
          </div>
        </div>
        {selectedPath && !visibleEntries.length && <EmptyState title="Нет анкет" text="В этой конкурсной папке нет заявок." />}
      </main>
      {showBulkEdit && (
        <div className="modal-backdrop" onMouseDown={() => setShowBulkEdit(false)}>
          <form className="success-modal panel-form contest-bulk-form" onSubmit={bulkUpdate} onMouseDown={(event) => event.stopPropagation()}>
            <h3>Изменить данные у {selected.length} заявок</h3>
            <p className="muted">Пустые поля останутся без изменений.</p>
            <label><span>Льготная группа</span><input value={bulkForm.benefit_group} onChange={(event) => setBulkForm({ ...bulkForm, benefit_group: event.target.value })} placeholder="Без изменений" /></label>
            <label><span>Прописка</span><input value={bulkForm.residence_address} onChange={(event) => setBulkForm({ ...bulkForm, residence_address: event.target.value })} placeholder="Без изменений" /></label>
            <label>
              <span>База поступления</span>
              <select value={bulkForm.base_class} onChange={(event) => setBulkForm({ ...bulkForm, base_class: event.target.value })}>
                <option value="">Без изменений</option>
                <option value="9 класс">9 класс</option>
                <option value="11 класс">11 класс</option>
                <option value="ТИПО">ТИПО</option>
              </select>
            </label>
            <label>
              <span>Вид зачисления</span>
              <select value={bulkForm.enrollment_type} onChange={(event) => setBulkForm({ ...bulkForm, enrollment_type: event.target.value })}>
                <option value="">Без изменений</option>
                <option value="general">На общих основаниях</option>
                <option value="reinstated">Как восстановившийся</option>
                <option value="transfer">По переводу</option>
              </select>
            </label>
            <label>
              <span>Тип местности</span>
              <select value={bulkForm.locality_type} onChange={(event) => setBulkForm({ ...bulkForm, locality_type: event.target.value })}>
                <option value="">Без изменений</option>
                <option value="urban">Городская</option>
                <option value="rural">Сельская</option>
              </select>
            </label>
            <label>
              <span>Язык обучения</span>
              <select value={bulkForm.instruction_language} onChange={(event) => setBulkForm({ ...bulkForm, instruction_language: event.target.value })}>
                <option value="">Без изменений</option>
                <option value="russian">Русский</option>
                <option value="kazakh">Казахский</option>
              </select>
            </label>
            <label>
              <span>Форма обучения</span>
              <select value={bulkForm.study_form} onChange={(event) => setBulkForm({ ...bulkForm, study_form: event.target.value })}>
                <option value="">Без изменений</option>
                <option value="full_time">Очная</option>
                <option value="part_time">Заочная</option>
              </select>
            </label>
            <label>
              <span>Общежитие</span>
              <select value={bulkForm.needs_dormitory} onChange={(event) => setBulkForm({ ...bulkForm, needs_dormitory: event.target.value })}>
                <option value="">Без изменений</option>
                <option value="yes">Нужно</option>
                <option value="no">Не нужно</option>
              </select>
            </label>
            <div className="action-row">
              <button type="button" onClick={() => setShowBulkEdit(false)}>Отмена</button>
              <button type="submit" className="primary-button"><Save size={16} /> Применить</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

type DetailsTab = "main" | "contest" | "admissions" | "education" | "student";
type RootEditableField = "iin" | "birth_date" | "full_name" | "email" | "phone";
type AdmissionEditableField =
  | "benefit_group"
  | "residence_address"
  | "base_class"
  | "qualification"
  | "specialty"
  | "enrollment_type"
  | "locality_type"
  | "instruction_language"
  | "study_form"
  | "needs_dormitory";
type ContestEditableField =
  | "benefit_group"
  | "residence_address"
  | "base_class"
  | "enrollment_type"
  | "locality_type"
  | "instruction_language"
  | "study_form"
  | "needs_dormitory";
type EducationEditableField =
  | "curator_id"
  | "group_number"
  | "course"
  | "payment_type"
  | "is_state_grant"
  | "has_scholarship"
  | "scholarship_amount"
  | "academic_leave"
  | "academic_performance";

export function ApplicationDetailsPage() {
  const { token, user } = useAuth();
  const { applicationId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [app, setApp] = useState<Application | null>(null);
  const [teachers, setTeachers] = useState<User[]>([]);
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [activeTab, setActiveTab] = useState<DetailsTab>("main");
  const [dirtyRootFields, setDirtyRootFields] = useState<RootEditableField[]>([]);
  const [dirtyAdmissionFields, setDirtyAdmissionFields] = useState<AdmissionEditableField[]>([]);
  const [contestSpecialtyIds, setContestSpecialtyIds] = useState<number[]>([]);
  const [dirtyEducationFields, setDirtyEducationFields] = useState<EducationEditableField[]>([]);
  const [showExpulsion, setShowExpulsion] = useState(false);
  const [expulsion, setExpulsion] = useState({
    order_number: "",
    order_date: new Date().toISOString().slice(0, 10),
    reason: "",
  });

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
    setContestSpecialtyIds(item.contest_choices.map((choice) => choice.specialty_id));
    const users = await apiFetch<User[]>("/users?role=teacher", { token }).catch(() => []);
    setTeachers(users);
    const info = await apiFetch<{ specialties: Specialty[] }>("/public/college-info").catch(() => ({ specialties: [] }));
    setSpecialties(info.specialties);
  };

  useEffect(() => { void load(); }, [token, applicationId]);
  useEffect(() => {
    setActiveTab(new URLSearchParams(location.search).has("contestChoice") ? "contest" : "main");
    setDirtyRootFields([]);
    setDirtyAdmissionFields([]);
    setDirtyEducationFields([]);
  }, [applicationId, location.search]);

  const updateRoot = (field: RootEditableField, value: string) => {
    setApp((current) => current ? { ...current, [field]: value } : current);
    setDirtyRootFields((current) => current.includes(field) ? current : [...current, field]);
  };

  const updateAdmission = (field: AdmissionEditableField, value: string | boolean | null) => {
    setApp((current) => current ? {
      ...current,
      admission_details: {
        id: current.admission_details?.id ?? 0,
        enrollment_type: "general",
        locality_type: "urban",
        study_form: "full_time",
        needs_dormitory: false,
        ...current.admission_details,
        [field]: value,
      }
    } : current);
    setDirtyAdmissionFields((current) => current.includes(field) ? current : [...current, field]);
  };

  const updateContest = (field: ContestEditableField, value: string | boolean | null) => {
    setApp((current) => current ? {
      ...current,
      contest_profile: {
        id: current.contest_profile?.id ?? 0,
        enrollment_type: "general",
        locality_type: "urban",
        study_form: "full_time",
        needs_dormitory: false,
        ...current.contest_profile,
        [field]: value,
      }
    } : current);
  };

  const addContestSpecialty = () => {
    if (contestSpecialtyIds.length >= 4) return;
    const next = specialties.find((item) => !contestSpecialtyIds.includes(item.id));
    if (next) setContestSpecialtyIds((current) => [...current, next.id]);
  };

  const updateContestSpecialty = (index: number, specialtyId: number) => {
    setContestSpecialtyIds((current) => current.map((item, itemIndex) => itemIndex === index ? specialtyId : item));
  };

  const removeContestSpecialty = (index: number) => {
    setContestSpecialtyIds((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const updateEducation = (field: EducationEditableField, value: string | boolean | number | null) => {
    setApp((current) => {
      if (!current) return current;
      const details = {
        id: current.education_details?.id ?? 0,
        is_state_grant: false,
        has_scholarship: false,
        academic_leave: false,
        ...current.education_details,
        [field]: value,
      };
      if (field === "has_scholarship") {
        details.scholarship_amount = value
          ? scholarshipAmount(current.admission_details?.specialty, details.academic_performance)
          : null;
      } else if (field === "academic_performance" && details.has_scholarship) {
        details.scholarship_amount = scholarshipAmount(current.admission_details?.specialty, String(value || ""));
      }
      return { ...current, education_details: details };
    });
    setDirtyEducationFields((current) => current.includes(field) ? current : [...current, field]);
  };

  const buildBulkApplicationUpdate = () => {
    if (!app) return {};
    const update: Record<string, unknown> = {};
    dirtyRootFields.forEach((field) => {
      update[field] = app[field];
    });
    if (dirtyAdmissionFields.length) {
      const admissionUpdate: Record<string, unknown> = {};
      dirtyAdmissionFields.forEach((field) => {
        admissionUpdate[field] = app.admission_details?.[field] ?? null;
      });
      update.admission_details = admissionUpdate;
    }
    return update;
  };

  const buildBulkEducationUpdate = () => {
    if (!app?.education_details) return {};
    const update: Record<string, unknown> = {};
    dirtyEducationFields.forEach((field) => {
      update[field] = app.education_details?.[field] ?? null;
    });
    return update;
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
        const bulkUpdate = buildBulkApplicationUpdate();
        if (!Object.keys(bulkUpdate).length) {
          setSaved("Нет изменений для массового применения");
          return;
        }
        await apiFetch<Application[]>("/admin/applications/bulk/update", {
          method: "PATCH",
          token,
          body: JSON.stringify({ application_ids: bulkApplicationIds, update: bulkUpdate })
        });
        await load();
        setDirtyRootFields([]);
        setDirtyAdmissionFields([]);
      } else {
        const updated = await apiFetch<Application>(`/admin/applications/${app.id}`, { method: "PATCH", token, body: JSON.stringify(body) });
        setApp(updated);
      }
      setSaved(isBulkMode ? `Сохранено для ${bulkApplicationIds.length} студентов` : "Сохранено");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const saveContest = async (submit = false) => {
    if (!token || !app) return;
    setError("");
    setSaved("");
    try {
      const profile = app.contest_profile;
      const payload = {
        benefit_group: profile?.benefit_group ?? null,
        residence_address: profile?.residence_address ?? null,
        base_class: profile?.base_class ?? null,
        enrollment_type: profile?.enrollment_type ?? "general",
        locality_type: profile?.locality_type ?? "urban",
        instruction_language: profile?.instruction_language ?? null,
        study_form: profile?.study_form ?? "full_time",
        needs_dormitory: profile?.needs_dormitory ?? false,
        specialty_ids: contestSpecialtyIds,
      };
      const updated = await apiFetch<Application>(
        `/contest/applications/${app.id}${submit ? "/submit" : ""}`,
        { method: submit ? "POST" : "PATCH", token, body: JSON.stringify(payload) }
      );
      setApp(updated);
      setContestSpecialtyIds(updated.contest_choices.map((choice) => choice.specialty_id));
      setSaved(submit ? "Заявка отправлена на конкурс" : "Конкурсные данные сохранены");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const decideContestChoice = async (decision: "accept" | "reject") => {
    if (!token || !app) return;
    const queryChoiceId = Number(new URLSearchParams(location.search).get("contestChoice"));
    const choiceId = queryChoiceId || app.contest_choices.find((choice) => choice.status === "active")?.id;
    if (!choiceId) {
      setError("Не выбрана конкурсная специальность");
      return;
    }
    const selectedChoice = app.contest_choices.find((choice) => choice.id === choiceId);
    const prompt = decision === "accept"
      ? `Принять ${app.full_name} по специальности «${selectedChoice?.specialty.name ?? ""}»?`
      : `Отклонить конкурсную заявку по специальности «${selectedChoice?.specialty.name ?? ""}»?`;
    if (!window.confirm(prompt)) return;
    setError("");
    try {
      await apiFetch(`/contest/choices/${choiceId}/${decision}`, { method: "POST", token });
      if (decision === "reject") {
        navigate("/admin/contest");
      } else {
        await load();
        setSaved("Студент принят из конкурса");
      }
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
        is_state_grant: details.is_state_grant,
        has_scholarship: details.has_scholarship,
        scholarship_amount: details.scholarship_amount,
        academic_leave: details.academic_leave,
        academic_performance: details.academic_performance,
      };
      if (isBulkMode) {
        const bulkUpdate = buildBulkEducationUpdate();
        if (!Object.keys(bulkUpdate).length) {
          setSaved("Нет изменений для массового применения");
          return;
        }
        await apiFetch("/education/applications/bulk/details", {
          method: "PATCH",
          token,
          body: JSON.stringify({ application_ids: bulkApplicationIds, update: bulkUpdate })
        });
        if (complete) {
          await apiFetch("/education/applications/bulk/save", {
            method: "POST",
            token,
            body: JSON.stringify({ application_ids: bulkApplicationIds })
          });
        }
        setDirtyEducationFields([]);
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

  const submitExpulsion = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !app) return;
    setError("");
    try {
      const updated = await apiFetch<Application>(`/education/applications/${app.id}/expel`, {
        method: "POST",
        token,
        body: JSON.stringify(expulsion),
      });
      setApp(updated);
      setShowExpulsion(false);
      setSaved("Студент отчислен");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const graduateStudent = async () => {
    if (!token || !app || !window.confirm(`Перевести ${app.full_name} в статус «Выпускник»?`)) return;
    setError("");
    try {
      const updated = await apiFetch<Application>(`/education/applications/${app.id}/graduate`, {
        method: "POST",
        token,
      });
      setApp(updated);
      setSaved("Студент переведен в выпускники");
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const downloadPdf = async () => {
    if (!token || !app) return;
    setError("");
    try {
      const response = await fetch(`${API_URL}/admin/applications/${app.id}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ detail: "Не удалось сформировать PDF" }));
        throw new Error(typeof payload.detail === "string" ? payload.detail : "Не удалось сформировать PDF");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Анкета_${app.id}.pdf`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  if (!app) return <div className="admin-page"><EmptyState title="Загрузка" text="Открываем анкету." /></div>;
  const isTeacher = user?.role === "teacher";
  const canAdmissions = user?.role === "admissions_admin" || user?.role === "tech_admin";
  const canEducation = user?.role === "education_admin" || user?.role === "tech_admin";
  const canContestDecision = canAdmissions || user?.role === "education_admin";
  const canEditRoot = canAdmissions || isTeacher;
  const canUseAdmissionsActions = canAdmissions && admissionsActionableStatuses.has(app.status);
  const canCompleteEducation = canEducation && educationCompletableStatuses.has(app.status);
  const canExpel = canEducation && ["completed", "enrolled"].includes(app.status);
  const canGraduate = canEducation && ["completed", "enrolled"].includes(app.status);
  const hasStudentSheet = ["completed", "enrolled", "expelled", "graduated"].includes(app.status);
  const showContestTab = !isTeacher && (
    app.contest_visible
    || ["new", "in_admissions_review", "in_contest"].includes(app.status)
  );
  const showAdmissionsTab = !isTeacher && Boolean(
    app.admission_details?.specialty
    || ["accepted_by_admissions", "education_review", "enrolled", "completed", "expelled", "graduated"].includes(app.status)
  );
  const selectedContestChoiceId = Number(new URLSearchParams(location.search).get("contestChoice"));
  const selectedContestChoice = app.contest_choices.find((choice) => choice.id === selectedContestChoiceId)
    ?? app.contest_choices.find((choice) => choice.status === "accepted")
    ?? app.contest_choices[0];
  const visibleContestSpecialtyIds = selectedContestChoiceId && selectedContestChoice
    ? [selectedContestChoice.specialty_id]
    : contestSpecialtyIds;
  const groupedSpecialties = Object.entries(
    specialties.reduce<Record<string, Specialty[]>>((groups, specialty) => {
      const qualification = specialty.qualification;
      groups[qualification] = [...(groups[qualification] ?? []), specialty];
      return groups;
    }, {})
  )
    .sort(([left], [right]) => left.localeCompare(right, "ru"))
    .map(([qualification, items]) => [
      qualification,
      items.sort((left, right) => left.name.localeCompare(right.name, "ru")),
    ] as const);
  const curatorName = teachers.find((teacher) => teacher.id === app.education_details?.curator_id)?.full_name ?? "Не выбрано";
  const paymentLabel = app.education_details?.payment_type === "free"
    ? "Бесплатно"
    : app.education_details?.payment_type === "paid"
      ? "Платно"
      : "Не выбрано";
  const enrollmentLabel = {
    general: "На общих основаниях",
    reinstated: "Как восстановившийся",
    transfer: "По переводу",
  }[app.admission_details?.enrollment_type ?? "general"];
  const performanceLabels: Record<string, string> = {
    excellent: "Отлично",
    good: "Хорошо",
    satisfactory: "Удовлетворительно",
  };
  const performanceLabel = performanceLabels[app.education_details?.academic_performance ?? ""] ?? "Не выбрано";
  const tabs: { id: DetailsTab; label: string }[] = [
    { id: "main", label: "Основные данные" },
    ...(showContestTab ? [{ id: "contest" as DetailsTab, label: "Конкурс" }] : []),
    ...(showAdmissionsTab ? [{ id: "admissions" as DetailsTab, label: "Приемная комиссия" }] : []),
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
          <span>Ко всем выбранным карточкам применятся только поля, которые вы изменили здесь.</span>
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
                <label><span>ИИН</span><input disabled={!canAdmissions} value={app.iin} onChange={(e) => updateRoot("iin", e.target.value.replace(/\D/g, "").slice(0, 12))} /></label>
                <label><span>Дата рождения</span><input disabled={!canAdmissions} type="date" value={app.birth_date} onChange={(e) => updateRoot("birth_date", e.target.value)} /></label>
                <label><span>ФИО</span><input disabled={!canAdmissions} value={app.full_name} onChange={(e) => updateRoot("full_name", e.target.value)} /></label>
              </>
            )}
            <label><span>Email</span><input disabled={!canEditRoot} value={app.email} onChange={(e) => updateRoot("email", e.target.value)} /></label>
            <label><span>Телефон</span><input disabled={!canEditRoot} value={app.phone} onChange={(e) => updateRoot("phone", e.target.value)} /></label>
            {canEditRoot && <button type="button" className="primary-button" onClick={saveApplication}><Save size={16} /> Сохранить</button>}
          </form>
        )}

        {activeTab === "contest" && showContestTab && (
          <form className="panel-form tab-panel">
            {selectedContestChoice && (
              <div className="contest-context">
                <strong>Текущая конкурсная специальность</strong>
                <span>{selectedContestChoice.specialty.name}</span>
                <small>{selectedContestChoice.specialty.qualification}</small>
              </div>
            )}
            <label><span>Льготная группа</span><input className={emptyFieldClass(app.contest_profile?.benefit_group)} disabled={!canAdmissions} value={app.contest_profile?.benefit_group ?? ""} onChange={(e) => updateContest("benefit_group", e.target.value)} placeholder="Не выбрано" /></label>
            <label><span>Прописка</span><input className={emptyFieldClass(app.contest_profile?.residence_address)} disabled={!canAdmissions} value={app.contest_profile?.residence_address ?? ""} onChange={(e) => updateContest("residence_address", e.target.value)} placeholder="Не выбрано" /></label>
            <label>
              <span>База поступления</span>
              <select className={emptyFieldClass(app.contest_profile?.base_class)} disabled={!canAdmissions} value={app.contest_profile?.base_class ?? ""} onChange={(e) => updateContest("base_class", e.target.value)}>
                <option value="" disabled>Не выбрано</option>
                <option value="9 класс">9 класс</option>
                <option value="11 класс">11 класс</option>
                <option value="ТИПО">ТИПО</option>
              </select>
            </label>
            <label>
              <span>Вид зачисления</span>
              <select disabled={!canAdmissions} value={app.contest_profile?.enrollment_type ?? "general"} onChange={(e) => updateContest("enrollment_type", e.target.value)}>
                <option value="general">На общих основаниях</option>
                <option value="reinstated">Как восстановившийся</option>
                <option value="transfer">По переводу</option>
              </select>
            </label>
            <label>
              <span>Тип местности проживания</span>
              <select disabled={!canAdmissions} value={app.contest_profile?.locality_type ?? "urban"} onChange={(e) => updateContest("locality_type", e.target.value)}>
                <option value="urban">Городская местность</option>
                <option value="rural">Сельская местность</option>
              </select>
            </label>
            <label>
              <span>Язык обучения</span>
              <select className={emptyFieldClass(app.contest_profile?.instruction_language)} disabled={!canAdmissions} value={app.contest_profile?.instruction_language ?? ""} onChange={(e) => updateContest("instruction_language", e.target.value || null)}>
                <option value="" disabled>Не выбрано</option>
                <option value="russian">Русский</option>
                <option value="kazakh">Казахский</option>
              </select>
            </label>
            <label>
              <span>Форма обучения</span>
              <select disabled={!canAdmissions} value={app.contest_profile?.study_form ?? "full_time"} onChange={(e) => updateContest("study_form", e.target.value)}>
                <option value="full_time">Очная</option>
                <option value="part_time">Заочная</option>
              </select>
            </label>
            <label>
              <span>Общежитие</span>
              <select disabled={!canAdmissions} value={app.contest_profile?.needs_dormitory ? "yes" : "no"} onChange={(e) => updateContest("needs_dormitory", e.target.value === "yes")}>
                <option value="no">Не нужно</option>
                <option value="yes">Нужно</option>
              </select>
            </label>
            <div className="contest-specialties">
              <div className="pane-header">
                <div>
                  <strong>Специальности</strong>
                  <small>От 1 до 4 направлений</small>
                </div>
                {canAdmissions && !selectedContestChoiceId && contestSpecialtyIds.length < 4 && (
                  <button type="button" onClick={addContestSpecialty}><Plus size={16} /> Специальность</button>
                )}
              </div>
              {visibleContestSpecialtyIds.map((specialtyId) => {
                const index = contestSpecialtyIds.indexOf(specialtyId);
                const specialty = specialties.find((item) => item.id === specialtyId);
                return (
                  <div className="contest-specialty-row" key={`${specialtyId}-${index}`}>
                    <select
                      disabled={!canAdmissions}
                      value={specialtyId}
                      onChange={(event) => updateContestSpecialty(index, Number(event.target.value))}
                    >
                      {groupedSpecialties.map(([qualification, items]) => (
                        <optgroup key={qualification} label={qualification}>
                          {items.map((item) => (
                            <option
                              key={item.id}
                              value={item.id}
                              disabled={contestSpecialtyIds.some((selectedId, selectedIndex) => selectedIndex !== index && selectedId === item.id)}
                            >
                              {item.name}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    <span>{specialty?.qualification ?? "Квалификация не найдена"}</span>
                    {canAdmissions && !selectedContestChoiceId && <button type="button" onClick={() => removeContestSpecialty(index)}><X size={15} /></button>}
                  </div>
                );
              })}
              {!contestSpecialtyIds.length && <span className="muted">Добавьте хотя бы одну специальность.</span>}
            </div>
            <div className="action-row">
              {canAdmissions && ["new", "in_admissions_review", "in_contest"].includes(app.status) && (
                <>
                  <button type="button" onClick={() => saveContest(false)}><Save size={16} /> Сохранить</button>
                  {["new", "in_admissions_review"].includes(app.status) && (
                    <button type="button" className="primary-button" onClick={() => saveContest(true)}><Check size={16} /> Отправить на конкурс</button>
                  )}
                </>
              )}
              {canContestDecision && app.status === "in_contest" && selectedContestChoice && (
                <>
                  <button type="button" className="primary-button" onClick={() => decideContestChoice("accept")}><Check size={16} /> Принять из конкурса</button>
                  <button type="button" onClick={() => decideContestChoice("reject")}><X size={16} /> Отклонить направление</button>
                </>
              )}
            </div>
          </form>
        )}

        {activeTab === "admissions" && !isTeacher && (
          <form className="panel-form tab-panel">
            <label><span>Льготная группа</span><input className={emptyFieldClass(app.admission_details?.benefit_group)} disabled={!canAdmissions} value={app.admission_details?.benefit_group ?? ""} onChange={(e) => updateAdmission("benefit_group", e.target.value)} placeholder="Не выбрано" /></label>
            <label><span>Прописка</span><input className={emptyFieldClass(app.admission_details?.residence_address)} disabled={!canAdmissions} value={app.admission_details?.residence_address ?? ""} onChange={(e) => updateAdmission("residence_address", e.target.value)} placeholder="Не выбрано" /></label>
            <label>
              <span>База поступления</span>
              <select className={emptyFieldClass(app.admission_details?.base_class)} disabled={!canAdmissions} value={app.admission_details?.base_class ?? ""} onChange={(e) => updateAdmission("base_class", e.target.value)}>
                <option value="" disabled>Не выбрано</option>
                <option value="9 класс">9 класс</option>
                <option value="11 класс">11 класс</option>
                <option value="ТИПО">ТИПО</option>
              </select>
            </label>
            <label>
              <span>Вид зачисления</span>
              <select disabled={!canAdmissions} value={app.admission_details?.enrollment_type ?? "general"} onChange={(e) => updateAdmission("enrollment_type", e.target.value)}>
                <option value="general">На общих основаниях</option>
                <option value="reinstated">Как восстановившийся</option>
                <option value="transfer">По переводу</option>
              </select>
            </label>
            <label>
              <span>Тип местности проживания</span>
              <select disabled={!canAdmissions} value={app.admission_details?.locality_type ?? "urban"} onChange={(e) => updateAdmission("locality_type", e.target.value)}>
                <option value="urban">Городская местность</option>
                <option value="rural">Сельская местность</option>
              </select>
            </label>
            <label>
              <span>Язык обучения</span>
              <select className={emptyFieldClass(app.admission_details?.instruction_language)} disabled={!canAdmissions} value={app.admission_details?.instruction_language ?? ""} onChange={(e) => updateAdmission("instruction_language", e.target.value || null)}>
                <option value="" disabled>Не выбрано</option>
                <option value="russian">Русский</option>
                <option value="kazakh">Казахский</option>
              </select>
            </label>
            <label>
              <span>Форма обучения</span>
              <select disabled={!canAdmissions} value={app.admission_details?.study_form ?? "full_time"} onChange={(e) => updateAdmission("study_form", e.target.value)}>
                <option value="full_time">Очная</option>
                <option value="part_time">Заочная</option>
              </select>
            </label>
            <label>
              <span>Общежитие</span>
              <select disabled={!canAdmissions} value={app.admission_details?.needs_dormitory ? "yes" : "no"} onChange={(e) => updateAdmission("needs_dormitory", e.target.value === "yes")}>
                <option value="no">Не нужно</option>
                <option value="yes">Нужно</option>
              </select>
            </label>
            <label>
              <span>Специальность</span>
              <select className={emptyFieldClass(app.admission_details?.specialty)} disabled={!canAdmissions} value={app.admission_details?.specialty ?? ""} onChange={(e) => {
                const specialty = specialties.find((item) => item.name === e.target.value);
                updateAdmission("specialty", e.target.value);
                updateAdmission("qualification", specialty?.qualification ?? "");
              }}>
                <option value="" disabled>Не выбрано</option>
                {groupedSpecialties.map(([qualification, items]) => (
                  <optgroup key={qualification} label={qualification}>
                    {items.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
            <label><span>Квалификация</span><input className={emptyFieldClass(app.admission_details?.qualification)} disabled={!canAdmissions} value={app.admission_details?.qualification ?? ""} onChange={(e) => updateAdmission("qualification", e.target.value)} placeholder="Не выбрано" /></label>
            {canAdmissions && (
              <div className="action-row">
                <button type="button" onClick={() => saveApplication()}><Save size={16} /> Сохранить</button>
                {canUseAdmissionsActions && <button type="button" onClick={() => action("archive")}><Archive size={16} /> Архивировать</button>}
                {canUseAdmissionsActions && <button type="button" onClick={() => action("reject")}><X size={16} /> Отклонить</button>}
              </div>
            )}
          </form>
        )}

        {activeTab === "education" && canEducation && (
          <form className="panel-form tab-panel">
            <label>
              <span>Куратор</span>
              <select className={emptyFieldClass(app.education_details?.curator_id)} value={app.education_details?.curator_id ?? ""} onChange={(e) => updateEducation("curator_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="" disabled>Не выбрано</option>
                {teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.full_name}</option>)}
              </select>
            </label>
            <label><span>Номер группы</span><input className={emptyFieldClass(app.education_details?.group_number)} value={app.education_details?.group_number ?? ""} onChange={(e) => updateEducation("group_number", e.target.value)} placeholder="Не выбрано" /></label>
            <label><span>Курс</span><input className={emptyFieldClass(app.education_details?.course)} type="number" min={1} max={4} value={app.education_details?.course ?? ""} onChange={(e) => updateEducation("course", e.target.value ? Number(e.target.value) : null)} placeholder="Не выбрано" /></label>
            <label>
              <span>Оплата</span>
              <select className={emptyFieldClass(app.education_details?.payment_type)} value={app.education_details?.payment_type ?? ""} onChange={(e) => updateEducation("payment_type", e.target.value || null)}>
                <option value="" disabled>Не выбрано</option>
                <option value="free">Бесплатно</option>
                <option value="paid">Платно</option>
              </select>
            </label>
            <label className="checkbox-line"><input type="checkbox" checked={Boolean(app.education_details?.is_state_grant)} onChange={(e) => updateEducation("is_state_grant", e.target.checked)} /> Госзаказ</label>
            <label>
              <span>Успеваемость</span>
              <select className={emptyFieldClass(app.education_details?.academic_performance)} value={app.education_details?.academic_performance ?? ""} onChange={(e) => updateEducation("academic_performance", e.target.value || null)}>
                <option value="" disabled>Не выбрано</option>
                <option value="excellent">Отлично</option>
                <option value="good">Хорошо</option>
                <option value="satisfactory">Удовлетворительно</option>
              </select>
            </label>
            <label className="checkbox-line"><input type="checkbox" checked={Boolean(app.education_details?.has_scholarship)} onChange={(e) => updateEducation("has_scholarship", e.target.checked)} /> Получает стипендию</label>
            <label>
              <span>Размер стипендии</span>
              <input
                type="number"
                min={0}
                disabled={!app.education_details?.has_scholarship}
                value={app.education_details?.scholarship_amount ?? ""}
                onChange={(e) => updateEducation("scholarship_amount", e.target.value ? Number(e.target.value) : null)}
              />
            </label>
            <label className="checkbox-line"><input type="checkbox" checked={Boolean(app.education_details?.academic_leave)} onChange={(e) => updateEducation("academic_leave", e.target.checked)} /> Академический отпуск</label>
            <div className="action-row">
              <button type="button" onClick={() => saveEducation(false)}><Save size={16} /> Сохранить</button>
              {canCompleteEducation && <button type="button" className="primary-button" onClick={() => saveEducation(true)}><Check size={16} /> Оформить</button>}
              {canExpel && <button type="button" onClick={() => setShowExpulsion(true)}><UserMinus size={16} /> Отчислить</button>}
              {canGraduate && <button type="button" onClick={graduateStudent}><GraduationCap size={16} /> Выпускник</button>}
            </div>
          </form>
        )}

        {activeTab === "student" && hasStudentSheet && (
          <div className="student-sheet">
            <div className="action-row">
              <button type="button" className="primary-button" onClick={downloadPdf}><Download size={16} /> Выгрузить анкету в PDF</button>
            </div>
            <dl>
              <div><dt>ИИН</dt><dd>{app.iin}</dd></div>
              <div><dt>ФИО</dt><dd>{app.full_name}</dd></div>
              <div><dt>Дата рождения</dt><dd>{formatDate(app.birth_date)}</dd></div>
              <div><dt>Прописка</dt><dd className={emptyFieldClass(app.admission_details?.residence_address)}>{app.admission_details?.residence_address ?? "Не выбрано"}</dd></div>
              <div><dt>Тип местности</dt><dd>{app.admission_details?.locality_type === "rural" ? "Сельская местность" : "Городская местность"}</dd></div>
              <div><dt>Email</dt><dd>{app.email}</dd></div>
              <div><dt>Телефон</dt><dd>{app.phone}</dd></div>
              <div><dt>База поступления</dt><dd className={emptyFieldClass(app.admission_details?.base_class)}>{app.admission_details?.base_class ?? "Не выбрано"}</dd></div>
              <div><dt>Вид зачисления</dt><dd>{enrollmentLabel}</dd></div>
              <div><dt>Язык обучения</dt><dd className={emptyFieldClass(app.admission_details?.instruction_language)}>{app.admission_details?.instruction_language === "russian" ? "Русский" : app.admission_details?.instruction_language === "kazakh" ? "Казахский" : "Не выбрано"}</dd></div>
              <div><dt>Форма обучения</dt><dd>{app.admission_details?.study_form === "part_time" ? "Заочная" : "Очная"}</dd></div>
              <div><dt>Общежитие</dt><dd>{app.admission_details?.needs_dormitory ? "Нужно" : "Не нужно"}</dd></div>
              <div><dt>Курс</dt><dd className={emptyFieldClass(app.education_details?.course)}>{app.education_details?.course ?? "Не выбрано"}</dd></div>
              <div><dt>Группа</dt><dd className={emptyFieldClass(app.education_details?.group_number)}>{app.education_details?.group_number ?? "Не выбрано"}</dd></div>
              <div><dt>Куратор</dt><dd className={emptyFieldClass(app.education_details?.curator_id)}>{curatorName}</dd></div>
              <div><dt>Квалификация</dt><dd className={emptyFieldClass(app.admission_details?.qualification)}>{app.admission_details?.qualification ?? "Не выбрано"}</dd></div>
              <div><dt>Специальность</dt><dd className={emptyFieldClass(app.admission_details?.specialty)}>{app.admission_details?.specialty ?? "Не выбрано"}</dd></div>
              <div><dt>Оплата</dt><dd className={emptyFieldClass(app.education_details?.payment_type)}>{paymentLabel}</dd></div>
              <div><dt>Успеваемость</dt><dd className={emptyFieldClass(app.education_details?.academic_performance)}>{performanceLabel}</dd></div>
              <div><dt>Стипендия</dt><dd>{app.education_details?.has_scholarship ? `${app.education_details.scholarship_amount ?? 0} ₸` : "Нет"}</dd></div>
              <div><dt>Академический отпуск</dt><dd>{app.education_details?.academic_leave ? "Да" : "Нет"}</dd></div>
            </dl>
            {app.status === "expelled" && (
              <div className="expulsion-summary">
                <h3>Отчисление</h3>
                <p>Приказ № {app.education_details?.expulsion_order_number ?? "не указан"} от {app.education_details?.expulsion_order_date ? formatDate(app.education_details.expulsion_order_date) : "дата не указана"}</p>
                <p>{app.education_details?.expulsion_reason ?? "Причина не указана"}</p>
              </div>
            )}
          </div>
        )}
      </section>
      {showExpulsion && (
        <div className="modal-backdrop" onMouseDown={() => setShowExpulsion(false)}>
          <form className="success-modal panel-form" onSubmit={submitExpulsion} onMouseDown={(event) => event.stopPropagation()}>
            <h3>Отчисление студента</h3>
            <label><span>Номер приказа</span><input required value={expulsion.order_number} onChange={(event) => setExpulsion((current) => ({ ...current, order_number: event.target.value }))} /></label>
            <label><span>Дата приказа</span><input required type="date" value={expulsion.order_date} onChange={(event) => setExpulsion((current) => ({ ...current, order_date: event.target.value }))} /></label>
            <label><span>Причина</span><textarea required rows={4} value={expulsion.reason} onChange={(event) => setExpulsion((current) => ({ ...current, reason: event.target.value }))} /></label>
            <div className="action-row">
              <button type="button" onClick={() => setShowExpulsion(false)}>Отмена</button>
              <button type="submit" className="primary-button"><UserMinus size={16} /> Отчислить</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

export function ChatsPage() {
  const { token, user } = useAuth();
  const { chatId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const base = location.pathname.startsWith("/assistant") ? "/assistant/chats" : "/admin/chats";
  const activeId = chatId ? Number(chatId) : chats[0]?.id;
  const canUseChatFiles = ["tech_admin", "admissions_admin", "assistant"].includes(user?.role ?? "");

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
    if (!token || !activeId || (!text.trim() && !file)) return;
    setError("");
    setUploading(true);
    try {
      if (file) {
        const form = new FormData();
        form.append("file", file);
        form.append("message", text.trim());
        await apiFetch(`/admin/chats/${activeId}/attachments`, { method: "POST", token, body: form });
      } else {
        await apiFetch(`/admin/chats/${activeId}/messages`, { method: "POST", token, body: JSON.stringify({ message: text.trim() }) });
      }
      setText("");
      setFile(null);
      await loadMessages();
      await loadChats();
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const loadAttachment = async (attachment: ChatMessage["attachments"][number]) => {
    const response = await fetch(`${API_URL}/admin/chats/attachments/${attachment.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Не удалось загрузить файл");
    return response.blob();
  };

  const deleteActiveChat = async () => {
    if (!token || !activeId || !window.confirm("Удалить чат и все отправленные документы с сервера?")) return;
    try {
      await apiFetch(`/admin/chats/${activeId}`, { method: "DELETE", token });
      const remaining = chats.filter((chat) => chat.id !== activeId);
      setMessages([]);
      setChats(remaining);
      navigate(remaining[0] ? `${base}/${remaining[0].id}` : base, { replace: true });
      await loadChats();
    } catch (err) {
      setError(apiMessage(err));
    }
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
          {user?.role === "tech_admin" && activeId && (
            <button className="danger-button" onClick={deleteActiveChat}><Trash2 size={16} /> Удалить чат</button>
          )}
        </div>
        {error && <div className="form-error">{error}</div>}
        <div className="chat-messages admin">
          {messages.map((message) => (
            <div key={message.id} className={`message-bubble ${message.sender_type === "applicant" ? "mine" : "staff"}`}>
              <span>{message.sender_type === "applicant" ? "Абитуриент" : roleLabels[message.sender_type as keyof typeof roleLabels] ?? "Сотрудник"}</span>
              <p>{message.message}</p>
              {canUseChatFiles
                ? <ChatAttachments attachments={message.attachments ?? []} loadAttachment={loadAttachment} />
                : Boolean(message.attachments?.length) && <small>Документ доступен приемной комиссии и помощникам.</small>}
            </div>
          ))}
        </div>
        <form className="chat-input" onSubmit={send}>
          <input value={text} onChange={(event) => setText(event.target.value)} placeholder="Ответить..." />
          {canUseChatFiles && (
            <label className="attachment-picker" title="Прикрепить документ">
              <Paperclip size={18} />
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.gif,.webp,.doc,.docx,.xls,.xlsx"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
          )}
          <button className="primary-button" disabled={uploading}>{uploading ? "Отправка..." : "Отправить"}</button>
          {file && <span className="selected-file">{file.name} <button type="button" onClick={() => setFile(null)}><X size={14} /></button></span>}
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
