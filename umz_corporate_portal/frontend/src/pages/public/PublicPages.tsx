import { ArrowRight, CheckCircle2, ClipboardList, HelpCircle, MessageCircle, Send, Table2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiFetch, apiMessage, ChatMessage, DocumentType, PortalInfo } from "../../api/client";
import { SiteFooter } from "../../components/Layout";

function iinIsValid(iin: string, birthDate: string) {
  if (!/^\d{12}$/.test(iin) || !birthDate) return false;
  const [year, month, day] = birthDate.split("-");
  return iin.slice(0, 6) === `${year.slice(2)}${month}${day}`;
}

export function HomePage() {
  const [info, setInfo] = useState<PortalInfo | null>(null);

  useEffect(() => {
    void apiFetch<PortalInfo>("/public/portal-info").then(setInfo);
  }, []);

  const documentTypes = info?.specialties ?? [];

  return (
    <div className="public-page">
      <header className="public-nav">
        <Link to="/" className="public-logo">
          <img src="/logo_umz.svg" alt="УМЗ" />
          <span>УМЗ Portal</span>
        </Link>
        <div className="public-nav-actions">
          <Link to="/request" className="ghost-link">Создать карточку</Link>
          <Link to="/staff/login" className="ghost-link">Вход сотрудников</Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <img src="/logo_umz.svg" alt="Корпоративный портал УМЗ" className="hero-logo" />
          <p className="eyebrow">Усть-Каменогорск</p>
          <h1>Корпоративный портал УМЗ</h1>
          <p>{info?.slogan ?? "Единый реестр документов, анкет и служебных обращений"}</p>
          <div className="hero-actions">
            <Link to="/request" className="primary-button">
              Создать обращение <ArrowRight size={18} />
            </Link>
            <Link to="/staff/login" className="secondary-button">
              Рабочая зона <Table2 size={18} />
            </Link>
          </div>
        </div>
        <div className="hero-panel registry-preview">
          <div className="preview-toolbar">
            <span>UMZ-DOC</span>
            <strong>Табличный реестр</strong>
          </div>
          {["Анкета сотрудника", "Служебная записка", "Запрос на справку", "Приказ"].map((item, index) => (
            <div className="preview-row" key={item}>
              <span>#{String(index + 41).padStart(4, "0")}</span>
              <strong>{item}</strong>
              <em>{index % 2 ? "Регистрация" : "Кадровая проверка"}</em>
            </div>
          ))}
          <div className="hero-stat">
            <ClipboardList size={22} />
            <strong>Реестр без лишних переходов</strong>
            <span>Редактирование строк, массовые действия, папки и чат в одной системе.</span>
          </div>
        </div>
      </section>

      <main className="public-content">
        <section className="section-grid">
          <div>
            <p className="eyebrow">Назначение</p>
            <h2>Документы, анкеты и обращения сотрудников в одном рабочем контуре</h2>
            <p>{info?.description}</p>
          </div>
          <div className="feature-grid">
            {(info?.characteristics ?? []).map((item) => (
              <article className="feature-card" key={item}>
                <CheckCircle2 size={20} />
                <span>{item}</span>
              </article>
            ))}
          </div>
        </section>

        <section>
          <div className="section-title">
            <p className="eyebrow">Классификатор</p>
            <h2>Типы записей</h2>
          </div>
          <div className="specialty-strip">
            {documentTypes.map((item: DocumentType) => (
              <article key={item.id} className="specialty-card">
                <h3>{item.name}</h3>
                <p>{item.qualification}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section-grid">
          <div>
            <p className="eyebrow">Участники процесса</p>
            <h2>Кадры, канцелярия и подразделения работают с одной карточкой</h2>
          </div>
          <div className="staff-grid">
            {(info?.staff ?? []).map((person) => (
              <article className="staff-card" key={person.name}>
                <div className="avatar-placeholder">{person.name.slice(0, 1)}</div>
                <h3>{person.name}</h3>
                <p>{person.role}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="faq-section">
          <div>
            <p className="eyebrow">FAQ</p>
            <h2>Частые вопросы</h2>
          </div>
          <div className="faq-list">
            {(info?.faq ?? []).map((item) => (
              <details key={item.question}>
                <summary><HelpCircle size={18} /> {item.question}</summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="cta-band">
          <div>
            <h2>Создать карточку обращения</h2>
            <p>После отправки формы система выдаст доступ к чату по карточке.</p>
          </div>
          <Link to="/request" className="primary-button">Открыть форму <ArrowRight size={18} /></Link>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export function ApplyPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ iin: "", birth_date: "", full_name: "", email: "", phone: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<{ id: number; token: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (field: keyof typeof form, value: string) => {
    if (field === "iin") value = value.replace(/\D/g, "").slice(0, 12);
    setForm((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!iinIsValid(form.iin, form.birth_date)) {
      setError("Неверный ИИН");
      return;
    }
    setSubmitting(true);
    try {
      const created = await apiFetch<{ id: number; public_token: string }>("/applications", {
        method: "POST",
        body: JSON.stringify(form)
      });
      localStorage.setItem(`umz_case_${created.id}`, created.public_token);
      setSuccess({ id: created.id, token: created.public_token });
    } catch (err) {
      const message = apiMessage(err);
      setError(message.includes("ИИН") ? "Неверный ИИН" : message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="form-page">
      <Link to="/" className="public-logo">
        <img src="/logo_umz.svg" alt="УМЗ" />
        <span>Корпоративный портал УМЗ</span>
      </Link>
      <form className="application-form" onSubmit={submit}>
        <p className="eyebrow">Новая карточка</p>
        <h1>Данные сотрудника</h1>
        <div className="form-grid">
          <label>
            <span>ИИН</span>
            <input value={form.iin} onChange={(e) => update("iin", e.target.value)} inputMode="numeric" placeholder="12 цифр" required />
          </label>
          <label>
            <span>Дата рождения</span>
            <input type="date" value={form.birth_date} onChange={(e) => update("birth_date", e.target.value)} required />
          </label>
          <label className="span-2">
            <span>ФИО</span>
            <input value={form.full_name} onChange={(e) => update("full_name", e.target.value)} placeholder="Фамилия Имя Отчество" required />
          </label>
          <label>
            <span>Корпоративный email</span>
            <input type="email" value={form.email} onChange={(e) => update("email", e.target.value)} required />
          </label>
          <label>
            <span>Телефон</span>
            <input value={form.phone} onChange={(e) => update("phone", e.target.value)} placeholder="+7 700 000 00 00" required />
          </label>
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="primary-button form-submit" disabled={submitting}>
          {submitting ? "Регистрация..." : "Создать карточку"} <Send size={18} />
        </button>
      </form>

      {success && (
        <div className="modal-backdrop">
          <div className="success-modal">
            <CheckCircle2 size={44} />
            <h2>Карточка создана</h2>
            <p>Отдел кадров получил уведомление. Теперь можно открыть чат и уточнить данные по обращению.</p>
            <div className="hero-actions">
              <button className="primary-button" onClick={() => navigate(`/case/${success.id}`)}>Открыть чат</button>
              <Link className="secondary-button" to="/">На главную</Link>
            </div>
          </div>
        </div>
      )}
      <SiteFooter />
    </div>
  );
}

export function PublicChatPage() {
  const { applicationId } = useParams();
  const storageKey = `umz_case_${applicationId}`;
  const [token, setToken] = useState(() => localStorage.getItem(storageKey) ?? "");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  const canLoad = useMemo(() => Boolean(applicationId && token), [applicationId, token]);

  const load = async () => {
    if (!applicationId || !token) return;
    try {
      const items = await apiFetch<ChatMessage[]>(`/applications/${applicationId}/chat/messages`, { applicationToken: token });
      setMessages(items);
      setError("");
      localStorage.setItem(storageKey, token);
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  useEffect(() => {
    if (!canLoad) return;
    void load();
    const timer = window.setInterval(load, 10000);
    return () => window.clearInterval(timer);
  }, [canLoad, token, applicationId]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!applicationId || !text.trim()) return;
    await apiFetch<ChatMessage>(`/applications/${applicationId}/chat/messages`, {
      method: "POST",
      applicationToken: token,
      body: JSON.stringify({ message: text.trim() })
    });
    setText("");
    await load();
  };

  return (
    <div className="chat-page">
      <Link to="/" className="public-logo">
        <img src="/logo_umz.svg" alt="УМЗ" />
        <span>Чат по карточке #{applicationId}</span>
      </Link>
      <section className="chat-card">
        {!token && (
          <div className="token-panel">
            <h1>Введите код доступа</h1>
            <p>Код был сохранен после создания карточки. При открытии с того же устройства он подставится автоматически.</p>
            <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Код доступа к карточке" />
            <button className="primary-button" onClick={load}>Открыть чат</button>
          </div>
        )}
        {token && (
          <>
            <div className="chat-messages">
              {messages.map((message) => (
                <div key={message.id} className={`message-bubble ${message.sender_type === "employee" ? "mine" : "staff"}`}>
                  <span>{message.sender_type === "employee" ? "Вы" : "Сотрудник портала"}</span>
                  <p>{message.message}</p>
                </div>
              ))}
              {!messages.length && <p className="muted">Сообщений пока нет. Напишите вопрос по карточке.</p>}
            </div>
            {error && <div className="form-error">{error}</div>}
            <form className="chat-input" onSubmit={send}>
              <input value={text} onChange={(event) => setText(event.target.value)} placeholder="Напишите сообщение..." />
              <button className="primary-button">Отправить <MessageCircle size={17} /></button>
            </form>
          </>
        )}
      </section>
      <SiteFooter />
    </div>
  );
}
