import { ArrowRight, CheckCircle2, HelpCircle, MessageCircle, Send, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiFetch, apiMessage, ChatMessage, CollegeInfo, Specialty } from "../../api/client";
import { SiteFooter } from "../../components/Layout";

function iinIsValid(iin: string, birthDate: string) {
  if (!/^\d{12}$/.test(iin) || !birthDate) return false;
  const [year, month, day] = birthDate.split("-");
  return iin.slice(0, 6) === `${year.slice(2)}${month}${day}`;
}

export function HomePage() {
  const [info, setInfo] = useState<CollegeInfo | null>(null);

  useEffect(() => {
    void apiFetch<CollegeInfo>("/public/college-info").then(setInfo);
  }, []);

  const specialties = info?.specialties ?? [];

  return (
    <div className="public-page">
      <header className="public-nav">
        <Link to="/" className="public-logo">
          <img src="/logo_cet.png" alt="Логотип КЭТ" />
          <span>КЭТ</span>
        </Link>
        <div className="public-nav-actions">
          <Link to="/apply" className="ghost-link">Подать заявку</Link>
          <Link to="/admin/login" className="ghost-link">Вход</Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <img src="/logo_cet.png" alt="Колледж экономики и техники" className="hero-logo" />
          <p className="eyebrow">Официальная система приема</p>
          <h1>Колледж экономики и техники</h1>
          <p>{info?.slogan ?? "Современное образование для практической профессии"}</p>
          <div className="hero-actions">
            <Link to="/apply" className="primary-button">
              Подать заявку <ArrowRight size={18} />
            </Link>
            <a href="#chat-start" className="secondary-button">
              Начать чат <MessageCircle size={18} />
            </a>
          </div>
        </div>
        <div className="hero-panel">
          <div className="hero-photo photo-one" />
          <div className="hero-photo photo-two" />
          <div className="hero-stat">
            <Sparkles size={22} />
            <strong>Digital admissions</strong>
            <span>Заявка, статус и чат в одной системе</span>
          </div>
        </div>
      </section>

      <main className="public-content">
        <section className="section-grid">
          <div>
            <p className="eyebrow">О колледже</p>
            <h2>Практика, наставники и понятный путь поступления</h2>
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
            <p className="eyebrow">Специальности</p>
            <h2>Направления подготовки</h2>
          </div>
          <div className="specialty-strip">
            {specialties.map((specialty: Specialty) => (
              <article key={specialty.id} className="specialty-card">
                <h3>{specialty.name}</h3>
                <p>{specialty.qualification}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section-grid">
          <div>
            <p className="eyebrow">Персонал</p>
            <h2>Команды, которые сопровождают абитуриента</h2>
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

        <section>
          <div className="section-title">
            <p className="eyebrow">Среда обучения</p>
            <h2>Аудитории и материально-техническая база</h2>
          </div>
          <div className="facility-grid">
            {(info?.facilities ?? []).map((item, index) => (
              <article className="facility-card" key={item.title}>
                <div className={`facility-image facility-${index}`} />
                <h3>{item.title}</h3>
                <p>{item.text}</p>
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

        <section id="chat-start" className="cta-band">
          <div>
            <h2>Готовы подать заявку?</h2>
            <p>После отправки формы откроется чат с администрацией по вашей заявке.</p>
          </div>
          <Link to="/apply" className="primary-button">Начать поступление <ArrowRight size={18} /></Link>
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
      setError("Неправильный ИИН");
      return;
    }
    setSubmitting(true);
    try {
      const created = await apiFetch<{ id: number; public_token: string }>("/applications", {
        method: "POST",
        body: JSON.stringify(form)
      });
      localStorage.setItem(`cet_application_${created.id}`, created.public_token);
      setSuccess({ id: created.id, token: created.public_token });
    } catch (err) {
      const message = apiMessage(err);
      setError(message.includes("ИИН") ? "Неправильный ИИН" : message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="form-page">
      <Link to="/" className="public-logo">
        <img src="/logo_cet.png" alt="КЭТ" />
        <span>Колледж экономики и техники</span>
      </Link>
      <form className="application-form" onSubmit={submit}>
        <p className="eyebrow">Подача заявки</p>
        <h1>Расскажите о себе</h1>
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
            <span>Email</span>
            <input type="email" value={form.email} onChange={(e) => update("email", e.target.value)} required />
          </label>
          <label>
            <span>Телефон</span>
            <input value={form.phone} onChange={(e) => update("phone", e.target.value)} placeholder="+7 700 000 00 00" required />
          </label>
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="primary-button form-submit" disabled={submitting}>
          {submitting ? "Отправка..." : "Отправить заявку"} <Send size={18} />
        </button>
      </form>

      {success && (
        <div className="modal-backdrop">
          <div className="success-modal">
            <CheckCircle2 size={44} />
            <h2>Заявка отправлена</h2>
            <p>Приемная комиссия получила уведомление. Теперь вы можете открыть чат по заявке.</p>
            <div className="hero-actions">
              <button className="primary-button" onClick={() => navigate(`/chat/${success.id}`)}>Открыть чат</button>
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
  const storageKey = `cet_application_${applicationId}`;
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
        <img src="/logo_cet.png" alt="КЭТ" />
        <span>Чат по заявке #{applicationId}</span>
      </Link>
      <section className="chat-card">
        {!token && (
          <div className="token-panel">
            <h1>Введите код доступа</h1>
            <p>Код был сохранен после отправки заявки. Если вы открыли чат с того же устройства, он подставится автоматически.</p>
            <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Код доступа к заявке" />
            <button className="primary-button" onClick={load}>Открыть чат</button>
          </div>
        )}
        {token && (
          <>
            <div className="chat-messages">
              {messages.map((message) => (
                <div key={message.id} className={`message-bubble ${message.sender_type === "applicant" ? "mine" : "staff"}`}>
                  <span>{message.sender_type === "applicant" ? "Вы" : "Администрация"}</span>
                  <p>{message.message}</p>
                </div>
              ))}
              {!messages.length && <p className="muted">Сообщений пока нет. Напишите вопрос приемной комиссии.</p>}
            </div>
            {error && <div className="form-error">{error}</div>}
            <form className="chat-input" onSubmit={send}>
              <input value={text} onChange={(event) => setText(event.target.value)} placeholder="Напишите сообщение..." />
              <button className="primary-button">Отправить</button>
            </form>
          </>
        )}
      </section>
      <SiteFooter />
    </div>
  );
}
