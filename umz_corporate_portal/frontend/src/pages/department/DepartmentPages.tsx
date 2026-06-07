import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch, Application } from "../../api/client";
import { EmptyState, StatusBadge } from "../../components/Layout";
import { useAuth } from "../../context/AuthContext";

export function DepartmentCasesPage() {
  const { token } = useAuth();
  const [cases, setCases] = useState<Application[]>([]);

  useEffect(() => {
    if (!token) return;
    void apiFetch<Application[]>("/document-control/applications", { token }).then(setCases);
  }, [token]);

  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Подразделение</p>
          <h2>Назначенные карточки</h2>
        </div>
      </div>
      <div className="student-grid">
        {cases.map((item) => (
          <article key={item.id} className="student-card">
            <h3>{item.admission_details?.specialty ?? item.full_name}</h3>
            <p>{item.admission_details?.residence_address ?? "Подразделение не указано"}</p>
            <span>{item.full_name}</span>
            <StatusBadge status={item.status} />
            <Link to={`/department/cases/${item.id}`}>Открыть карточку</Link>
          </article>
        ))}
      </div>
      {!cases.length && (
        <EmptyState
          title="Назначенных карточек нет"
          text="Канцелярия назначит документы вашему подразделению после регистрации."
        />
      )}
    </section>
  );
}
