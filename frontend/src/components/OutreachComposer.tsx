import { useEffect, useMemo, useState } from "react";
import {
  Check,
  Copy,
  ExternalLink,
  FilePenLine,
  Mail,
  MessageCircle,
  Plus,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { Modal } from "./UI";
import { tr } from "../i18n";
import { api } from '../api';
import {
  DEFAULT_OUTREACH_TEMPLATES,
  OUTREACH_VARIABLES,
  buildOutreachContext,
  emailUrl,
  renderOutreachTemplate,
  type OutreachChannel,
  type OutreachTemplate,
  whatsappUrl,
} from "../outreach";
import type { Lead, LeadActivityKind } from "../types";

function newTemplate(channel: OutreachChannel): OutreachTemplate {
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `template-${Date.now()}`;
  return {
    id,
    name: channel === "whatsapp" ? "Novo template · WhatsApp" : "Novo template · E-mail",
    channel,
    subject: channel === "email" ? "{{empresa}}" : "",
    body: "{{saudacao_contato}}! ",
  };
}


export function OutreachTemplateManager({
  templates,
  onChange,
  onClose,
}: {
  templates: OutreachTemplate[];
  onChange: (templates: OutreachTemplate[]) => void;
  onClose: () => void;
}) {
  const [selectedId, setSelectedId] = useState(templates[0]?.id || "");
  const selected = templates.find((template) => template.id === selectedId) || templates[0];

  function update(patch: Partial<OutreachTemplate>) {
    if (!selected) return;
    onChange(
      templates.map((template) =>
        template.id === selected.id ? { ...template, ...patch, builtin: false } : template,
      ),
    );
  }

  function add(channel: OutreachChannel) {
    const created = newTemplate(channel);
    onChange([...templates, created]);
    setSelectedId(created.id);
  }

  function remove() {
    if (!selected || templates.length <= 1) return;
    const next = templates.filter((template) => template.id !== selected.id);
    onChange(next);
    setSelectedId(next[0]?.id || "");
  }

  function resetDefaults() {
    onChange(DEFAULT_OUTREACH_TEMPLATES.map((template) => ({ ...template })));
    setSelectedId(DEFAULT_OUTREACH_TEMPLATES[0].id);
  }

  return (
    <Modal title="Templates de contato" onClose={onClose} wide className="outreach-template-modal">
      <div className="template-library">
        <aside className="template-library-list">
          <div className="template-library-add">
            <button type="button" className="button compact" onClick={() => add("whatsapp")}>
              <Plus size={15} /> WhatsApp
            </button>
            <button type="button" className="button compact" onClick={() => add("email")}>
              <Plus size={15} /> E-mail
            </button>
          </div>
          <div className="template-library-items">
            {templates.map((template) => (
              <button
                type="button"
                key={template.id}
                aria-current={template.id === selected?.id ? "true" : undefined}
                onClick={() => setSelectedId(template.id)}
              >
                {template.channel === "whatsapp" ? <MessageCircle size={15} /> : <Mail size={15} />}
                <span>
                  <strong>{template.name}</strong>
                  <small>{template.channel === "whatsapp" ? "WhatsApp" : "E-mail"}</small>
                </span>
              </button>
            ))}
          </div>
          <button type="button" className="template-reset" onClick={resetDefaults}>
            <RotateCcw size={14} /> {tr("Restaurar templates padrão")}
          </button>
        </aside>

        {selected && (
          <div className="template-editor">
            <label>
              <span>{tr("Nome do template")}</span>
              <input value={selected.name} onChange={(event) => update({ name: event.target.value })} />
            </label>
            <label>
              <span>{tr("Canal")}</span>
              <select
                value={selected.channel}
                onChange={(event) =>
                  update({ channel: event.target.value as OutreachChannel, subject: event.target.value === "email" ? selected.subject : "" })
                }
              >
                <option value="whatsapp">WhatsApp</option>
                <option value="email">E-mail</option>
              </select>
            </label>
            {selected.channel === "email" && (
              <label>
                <span>{tr("Assunto")}</span>
                <input value={selected.subject} onChange={(event) => update({ subject: event.target.value })} />
              </label>
            )}
            <label className="template-body-field">
              <span>{tr("Mensagem")}</span>
              <textarea rows={9} value={selected.body} onChange={(event) => update({ body: event.target.value })} />
            </label>
            <div className="template-variables" aria-label={tr("Variáveis disponíveis")}>
              <span>{tr("Inserir variável")}</span>
              <div>
                {OUTREACH_VARIABLES.map((variable) => (
                  <button
                    type="button"
                    key={variable.key}
                    onClick={() => update({ body: `${selected.body}${selected.body.endsWith(" ") ? "" : " "}{{${variable.key}}}` })}
                  >
                    {variable.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="template-editor-actions">
              <small>{tr("As alterações são salvas neste navegador.")}</small>
              <button type="button" className="button danger compact" disabled={templates.length <= 1} onClick={remove}>
                <Trash2 size={15} /> {tr("Excluir template")}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function OutreachComposer({
  lead,
  phone,
  email,
  templates,
  onManageTemplates,
  onRegister,
  busy,
  onNotice,
}: {
  lead: Lead;
  phone: string;
  email: string;
  templates: OutreachTemplate[];
  onManageTemplates: () => void;
  onRegister: (kind: LeadActivityKind, body: string) => Promise<void> | void;
  busy: boolean;
  onNotice: (message: string) => void;
}) {
  const firstChannel: OutreachChannel = phone ? "whatsapp" : "email";
  const [channel, setChannel] = useState<OutreachChannel>(firstChannel);
  const [recipientAllowed, setRecipientAllowed] = useState(false);
  useEffect(() => {
    let alive = true;
    setRecipientAllowed(false);
    const recipient = channel === 'whatsapp' ? phone : email;
    if (recipient) api<{ policy: { blocked: number } | null }>(`/leads/${lead.id}/recipient-policy?channel=${channel}&recipient=${encodeURIComponent(recipient)}`)
      .then(({ policy }) => { if (alive) setRecipientAllowed(!policy?.blocked); })
      .catch(() => { if (alive) setRecipientAllowed(false); });
    return () => { alive = false; };
  }, [lead.id, channel, phone, email]);
  const available = useMemo(
    () => templates.filter((template) => template.channel === channel),
    [channel, templates],
  );
  const [templateId, setTemplateId] = useState(available[0]?.id || "");
  const template = available.find((item) => item.id === templateId) || available[0];
  const rendered = useMemo(
    () => (template ? renderOutreachTemplate(template, lead) : { subject: "", body: "" }),
    [lead, template],
  );
  const [subject, setSubject] = useState(rendered.subject);
  const [body, setBody] = useState(rendered.body);
  const context = useMemo(() => buildOutreachContext(lead), [lead]);

  useEffect(() => {
    const candidate = available[0];
    if (!available.some((item) => item.id === templateId)) setTemplateId(candidate?.id || "");
  }, [available, templateId]);

  useEffect(() => {
    if (!template) return;
    const next = renderOutreachTemplate(template, lead);
    setSubject(next.subject);
    setBody(next.body);
  }, [template?.id, lead.id]);

  function selectTemplate(id: string) {
    setTemplateId(id);
    const next = templates.find((item) => item.id === id);
    if (!next) return;
    const filled = renderOutreachTemplate(next, lead);
    setSubject(filled.subject);
    setBody(filled.body);
  }

  async function copy() {
    const payload = channel === "email" && subject ? `${subject}\n\n${body}` : body;
    try {
      await navigator.clipboard.writeText(payload);
      onNotice("Mensagem copiada.");
    } catch {
      onNotice("Não foi possível copiar automaticamente.");
    }
  }

  function openExternal() {
    if (!recipientAllowed || lead.contact_blocked) return;
    const url = channel === "whatsapp" ? whatsappUrl(phone, body) : emailUrl(email, subject, body);
    if (!url) {
      onNotice(channel === "whatsapp" ? "WhatsApp não disponível para este contato." : "E-mail não disponível para este contato.");
      return;
    }
    window.open(url, channel === "whatsapp" ? "_blank" : "_self", "noopener,noreferrer");
  }

  async function register() {
    const activityBody = channel === "email" && subject ? `${subject}\n\n${body}` : body;
    await onRegister(channel === "whatsapp" ? "whatsapp" : "email", activityBody);
  }

  const canOpen = recipientAllowed && !lead.contact_blocked && (channel === "whatsapp" ? Boolean(phone) : Boolean(email));

  return (
    <section className="outreach-composer" aria-label={tr("Contato assistido")}>
      <div className="outreach-head">
        <div>
          <span>{tr("Contato assistido")}</span>
          <small>{tr("Revise antes de abrir o canal. Nada é enviado automaticamente.")}</small>
        </div>
        <button type="button" className="button compact" onClick={onManageTemplates}>
          <FilePenLine size={15} /> {tr("Templates")}
        </button>
      </div>

      <div className="outreach-controls">
        <div className="outreach-channel" role="tablist" aria-label={tr("Canal de contato")}>
          <button type="button" role="tab" aria-selected={channel === "whatsapp"} onClick={() => setChannel("whatsapp")}>
            <MessageCircle size={15} /> WhatsApp
          </button>
          <button type="button" role="tab" aria-selected={channel === "email"} onClick={() => setChannel("email")}>
            <Mail size={15} /> E-mail
          </button>
        </div>
        <label>
          <span>{tr("Template")}</span>
          <select value={template?.id || ""} onChange={(event) => selectTemplate(event.target.value)}>
            {available.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
      </div>

      {channel === "email" && (
        <label className="outreach-subject">
          <span>{tr("Assunto")}</span>
          <input value={subject} onChange={(event) => setSubject(event.target.value)} />
        </label>
      )}

      <label className="outreach-body">
        <span>{tr("Prévia editável")}</span>
        <textarea rows={7} value={body} onChange={(event) => setBody(event.target.value)} />
      </label>

      <div className="outreach-context" aria-label={tr("Contexto usado")}> 
        <span>{tr("Preenchido com")}</span>
        <div>
          <small>{context.empresa}</small>
          {context.contato && <small>{context.contato}</small>}
          {context.cidade && <small>{context.cidade}</small>}
          {context.servico && <small>{context.servico}</small>}
        </div>
      </div>

      <div className="outreach-actions">
        <button type="button" className="button" onClick={() => void copy()} disabled={!body.trim()}>
          <Copy size={15} /> {tr("Copiar")}
        </button>
        <button type="button" className="button primary" onClick={openExternal} disabled={!body.trim() || !canOpen}>
          <ExternalLink size={15} /> {tr(channel === "whatsapp" ? "Abrir no WhatsApp" : "Abrir no e-mail")}
        </button>
        <button type="button" className="button" onClick={() => void register()} disabled={busy || !body.trim() || !canOpen}>
          <Check size={15} /> {tr("Registrar envio manual")}
        </button>
      </div>
    </section>
  );
}
