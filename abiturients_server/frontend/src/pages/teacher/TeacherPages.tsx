import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch, Application } from "../../api/client";
import { EmptyState, StatusBadge } from "../../components/Layout";
import { useAuth } from "../../context/AuthContext";

export function TeacherStudentsPage() {
  const { token } = useAuth();
  const [students, setStudents] = useState<Application[]>([]);

  useEffect(() => {
    if (!token) return;
    void apiFetch<Application[]>("/education/applications", { token }).then(setStudents);
  }, [token]);

  return (
    <section className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Куратор</p>
          <h2>Мои студенты</h2>
        </div>
      </div>
      <div className="student-grid">
        {students.map((student) => (
          <article key={student.id} className="student-card">
            <h3>{student.full_name}</h3>
            <p>{student.education_details?.group_number ?? "Группа не указана"}</p>
            <span>{student.phone}</span>
            <StatusBadge status={student.status} />
            <Link to={`/teacher/students/${student.id}`}>Открыть карточку</Link>
          </article>
        ))}
      </div>
      {!students.length && <EmptyState title="Студентов пока нет" text="Учебная часть назначит вам студентов после оформления." />}
    </section>
  );
}
