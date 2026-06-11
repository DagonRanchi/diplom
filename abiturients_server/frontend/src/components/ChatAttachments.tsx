import { Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { ChatAttachment } from "../api/client";

type Props = {
  attachments: ChatAttachment[];
  loadAttachment: (attachment: ChatAttachment) => Promise<Blob>;
};

export function ChatAttachments({ attachments, loadAttachment }: Props) {
  const [urls, setUrls] = useState<Record<number, string>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});

  useEffect(() => {
    let cancelled = false;
    const createdUrls: string[] = [];
    const previewable = attachments.filter((item) => (
      item.content_type.startsWith("image/") || item.content_type === "application/pdf"
    ));
    void Promise.all(previewable.map(async (attachment) => {
      try {
        const blob = await loadAttachment(attachment);
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        createdUrls.push(url);
        setUrls((current) => ({ ...current, [attachment.id]: url }));
      } catch {
        if (!cancelled) {
          setErrors((current) => ({ ...current, [attachment.id]: "Не удалось открыть превью" }));
        }
      }
    }));
    return () => {
      cancelled = true;
      createdUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [attachments.map((item) => item.id).join(",")]);

  const download = async (attachment: ChatAttachment) => {
    const blob = await loadAttachment(attachment);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = attachment.original_name;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="chat-attachments">
      {attachments.map((attachment) => (
        <div className="chat-attachment" key={attachment.id}>
          {attachment.content_type.startsWith("image/") && urls[attachment.id] && (
            <img src={urls[attachment.id]} alt={attachment.original_name} />
          )}
          {attachment.content_type === "application/pdf" && urls[attachment.id] && (
            <iframe src={urls[attachment.id]} title={attachment.original_name} />
          )}
          {!attachment.content_type.startsWith("image/") && attachment.content_type !== "application/pdf" && (
            <FileText size={30} />
          )}
          <div>
            <strong>{attachment.original_name}</strong>
            <small>{Math.max(1, Math.round(attachment.size / 1024))} КБ</small>
            {errors[attachment.id] && <small>{errors[attachment.id]}</small>}
          </div>
          <button type="button" onClick={() => void download(attachment)} title="Скачать">
            <Download size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
