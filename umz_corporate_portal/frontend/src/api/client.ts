export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type Role = "hr_admin" | "document_admin" | "tech_admin" | "department_manager" | "assistant";

export type User = {
  id: number;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
};

export type AdmissionDetails = {
  id: number;
  benefit_group?: string | null;
  residence_address?: string | null;
  base_class?: string | null;
  qualification?: string | null;
  specialty?: string | null;
};

export type EducationDetails = {
  id: number;
  curator_id?: number | null;
  group_number?: string | null;
  course?: number | null;
  payment_type?: "free" | "paid" | null;
  is_state_grant: boolean;
  completed_at?: string | null;
};

export type Application = {
  id: number;
  iin: string;
  birth_date: string;
  full_name: string;
  email: string;
  phone: string;
  status: string;
  created_at: string;
  updated_at: string;
  admission_details?: AdmissionDetails | null;
  education_details?: EducationDetails | null;
  folder_id?: number | null;
  chat_id?: number | null;
};

export type FolderNode = {
  id: number;
  name: string;
  parent_id?: number | null;
  owner_scope: string;
  role_scope?: string | null;
  item_count: number;
  children: FolderNode[];
  created_at: string;
  updated_at: string;
};

export type Chat = {
  id: number;
  application_id: number;
  created_at: string;
  updated_at: string;
  application?: Application | null;
};

export type ChatMessage = {
  id: number;
  chat_id: number;
  sender_type: string;
  sender_user_id?: number | null;
  sender_application_id?: number | null;
  message: string;
  created_at: string;
  is_read: boolean;
};

export type Notification = {
  id: number;
  type: string;
  title: string;
  message: string;
  application_id?: number | null;
  is_read: boolean;
  created_at: string;
};

export type DocumentType = {
  id: number;
  name: string;
  qualification: string;
};

export type PortalInfo = {
  name: string;
  slogan: string;
  description: string;
  characteristics: string[];
  staff: { name: string; role: string }[];
  facilities: { title: string; text: string }[];
  faq: { question: string; answer: string }[];
  specialties: DocumentType[];
};

type ApiOptions = RequestInit & {
  token?: string | null;
  applicationToken?: string | null;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "Ошибка запроса");
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  if (options.applicationToken) {
    headers.set("X-Application-Token", options.applicationToken);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? payload;
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function apiMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (Array.isArray(error.detail)) return "Проверьте заполнение формы";
    if (typeof error.detail === "object" && error.detail) return JSON.stringify(error.detail);
  }
  if (error instanceof Error) return error.message;
  return "Не удалось выполнить действие";
}

export const statusLabels: Record<string, string> = {
  new: "Новая карточка",
  hr_review: "Кадровая проверка",
  archived: "Архив",
  rejected: "Отклонена",
  approved_by_hr: "Передано в канцелярию",
  document_review: "Регистрация",
  manager_review: "Согласование",
  completed: "Исполнено"
};

export const roleLabels: Record<Role, string> = {
  hr_admin: "Отдел кадров",
  document_admin: "Канцелярия",
  tech_admin: "Технический отдел",
  department_manager: "Руководитель подразделения",
  assistant: "Оператор поддержки"
};
