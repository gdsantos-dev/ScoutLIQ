import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { GoogleMapsImportResponse, Lead, LeadInput } from "../types";
import { activeCurrency, cents } from "../types";
import { currencyOptions, tr } from "../i18n";
import { Modal, Field, ErrorText, Submit } from "./UI";
import { SmartSelect } from "./Primitives";

export default function LeadForm({
  lead,
  onClose,
  onSaved,
  addToPipeline = false,
}: {
  lead?: Lead;
  onClose: () => void;
  onSaved: () => Promise<void>;
  addToPipeline?: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [mapsUrl, setMapsUrl] = useState(""),
    [mapsBusy, setMapsBusy] = useState(false),
    [mapsError, setMapsError] = useState(""),
    [mapsNotice, setMapsNotice] = useState(""),
    [imported, setImported] = useState<GoogleMapsImportResponse | null>(null),
    [formVersion, setFormVersion] = useState(0);
  const prefill = imported?.lead;

  async function importGoogleMaps() {
    if (mapsBusy || !mapsUrl.trim()) return;
    setMapsBusy(true);
    setMapsError("");
    setMapsNotice("");
    try {
      const result = await api<GoogleMapsImportResponse>(
        "/radar/import-google-maps",
        "POST",
        { url: mapsUrl.trim() },
        18000,
      );
      setImported(result);
      setFormVersion((current) => current + 1);
      setMapsNotice(
        result.warnings.length
          ? `Preenchimento parcial. ${result.warnings.join(" ")}`
          : "Dados preenchidos. Revise antes de salvar.",
      );
    } catch (e) {
      setMapsError((e as Error).message);
    } finally {
      setMapsBusy(false);
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget),
      str = (key: string) => String(data.get(key) ?? "");
    const payload: LeadInput = {
      name: str("name"),
      category: str("category"),
      city: str("city"),
      country: str("country").toUpperCase(),
      address: str("address"),
      latitude: Number(str("latitude")),
      longitude: Number(str("longitude")),
      rating: str("rating") ? Number(str("rating")) : null,
      reviews: str("reviews") ? Number(str("reviews")) : null,
      website: str("website"),
      website_status: str("website_status") as LeadInput["website_status"],
      instagram: str("instagram"),
      instagram_active: data.has("instagram_active"),
      phone: str("phone"),
      whatsapp: str("whatsapp"),
      contact: str("contact"),
      potential_cents: cents(data.get("potential")),
      potential_currency: str("potential_currency") as LeadInput["potential_currency"],
      notes: str("notes"),
    };
    try {
      if (lead) {
        await api(`/leads/${lead.id}`, "PUT", {
          ...payload,
          version: lead.version,
        });
      } else if (imported) {
        await api<Lead>(
          `/leads/imported${addToPipeline ? "?to_pipeline=true" : ""}`,
          "POST",
          {
            lead: payload,
            source: "google_maps",
            source_id: imported.source_id,
          },
        );
      } else {
        await api<Lead>(
          `/leads${addToPipeline ? "?to_pipeline=true" : ""}`,
          "POST",
          payload,
        );
      }
      await onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={lead ? "Editar estabelecimento" : "Novo estabelecimento"}
      onClose={onClose}
      wide
    >
      {!lead && (
        <section className="lead-map-import" aria-label={tr("Importar estabelecimento do Google Maps")}>
          <div className="lead-map-import-copy">
            <strong>{tr("Importar do Google Maps")}</strong>
            <span>{tr("Cole o link do estabelecimento para preencher o que for possível. Você revisa tudo antes de salvar.")}</span>
          </div>
          <div className="lead-map-import-row">
            <input
              type="url"
              value={mapsUrl}
              onChange={(event) => setMapsUrl(event.target.value)}
              placeholder="https://maps.app.goo.gl/..."
              aria-label={tr("Link do Google Maps")}
              maxLength={2000}
            />
            <button
              className="button"
              type="button"
              onClick={() => void importGoogleMaps()}
              disabled={mapsBusy || !mapsUrl.trim()}
            >
              {mapsBusy ? tr("Analisando…") : tr("Preencher")}
            </button>
          </div>
          {mapsError && <p className="error-text">{mapsError}</p>}
          {mapsNotice && <p className="field-hint">{mapsNotice}</p>}
        </section>
      )}
      <form key={formVersion} onSubmit={submit}>
        <div className="form-grid">
          <Field label={tr("Empresa")} className="span-2">
            <input
              autoFocus
              required
              name="name"
              maxLength={160}
              defaultValue={prefill?.name ?? lead?.name}
              placeholder={tr("Nome do estabelecimento")}
            />
          </Field>
          <Field label={tr("Categoria")}>
            <input
              required
              name="category"
              aria-label={tr("Categoria")}
              maxLength={80}
              defaultValue={prefill?.category ?? lead?.category}
              placeholder="Ex.: Barbearia"
              list="categories"
            />
            <datalist id="categories">
              {[
                "Barbearia",
                "Cafeteria",
                "Dentista",
                "Clínica",
                "Restaurante",
                "Academia",
                "Oficina",
                "Salão",
                "Imobiliária",
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </datalist>
          </Field>
          <Field label={tr("Contato")}>
            <input
              name="contact"
              maxLength={100}
              defaultValue={prefill?.contact ?? lead?.contact}
              placeholder={tr("Nome da pessoa")}
            />
          </Field>
          <Field label={tr("Cidade")}>
            <input
              name="city"
              required
              maxLength={100}
              defaultValue={prefill?.city ?? lead?.city}
            />
          </Field>
          <Field label={tr("País (código ISO)")}>
            <input
              name="country"
              required
              minLength={2}
              maxLength={2}
              defaultValue={prefill?.country ?? lead?.country ?? "BR"}
              placeholder="BR, US, MX…"
            />
          </Field>
          <Field label={tr("Endereço")} className="span-2">
            <input
              name="address"
              maxLength={250}
              defaultValue={prefill?.address ?? lead?.address}
            />
          </Field>
          <Field label={tr("Latitude")}>
            <input
              name="latitude"
              type="number"
              required
              step="any"
              min={-85}
              max={85}
              defaultValue={prefill?.latitude ?? lead?.latitude}
              placeholder="-8.05"
            />
          </Field>
          <Field label={tr("Longitude")}>
            <input
              name="longitude"
              type="number"
              required
              step="any"
              min={-180}
              max={180}
              defaultValue={prefill?.longitude ?? lead?.longitude}
              placeholder="-34.90"
            />
          </Field>
          <p className="field-hint span-2">
            {tr("Copie as coordenadas de um mapa para posicionar o estabelecimento com precisão.")}
          </p>
          <Field label={tr("Situação do site")}>
            <SmartSelect
              name="website_status"
              defaultValue={prefill?.website_status ?? lead?.website_status ?? "unknown"}
              options={[
                { value: "unknown", label: "Ainda não verificado" },
                { value: "none", label: "Sem site confirmado" },
                { value: "poor", label: "Site com problemas confirmados" },
                { value: "good", label: "Site adequado" },
              ]}
            />
          </Field>
          <Field label={tr("Site")}>
            <input
              type="url"
              name="website"
              maxLength={500}
              defaultValue={prefill?.website ?? lead?.website}
              placeholder="https://"
            />
          </Field>
          <Field label={tr("Avaliação (0–5)")}>
            <input
              type="number"
              step="0.1"
              min="0"
              max="5"
              name="rating"
              defaultValue={prefill?.rating ?? lead?.rating ?? ""}
              placeholder={tr("Não informada")}
            />
          </Field>
          <Field label={tr("Número de avaliações")}>
            <input
              type="number"
              step="1"
              min="0"
              max="10000000"
              name="reviews"
              defaultValue={prefill?.reviews ?? lead?.reviews ?? ""}
              placeholder={tr("Não informado")}
            />
          </Field>
          <Field label={tr("Telefone")}>
            <input
              type="tel"
              name="phone"
              maxLength={30}
              defaultValue={prefill?.phone ?? lead?.phone}
            />
          </Field>
          <Field label={tr("WhatsApp (país + número)")}>
            <input
              type="tel"
              name="whatsapp"
              pattern="[0-9]{8,15}"
              maxLength={15}
              defaultValue={prefill?.whatsapp ?? lead?.whatsapp}
              placeholder="5581999999999"
            />
          </Field>
          <Field label="Instagram">
            <input
              type="url"
              name="instagram"
              maxLength={500}
              defaultValue={prefill?.instagram ?? lead?.instagram}
              placeholder="https://instagram.com/empresa"
            />
          </Field>
          <Field label={tr("Moeda")}>
            <SmartSelect
              name="potential_currency"
              defaultValue={prefill?.potential_currency ?? lead?.potential_currency ?? activeCurrency()}
              ariaLabel={tr("Moeda")}
              options={currencyOptions}
            />
          </Field>
          <Field label={tr("Valor potencial")}>
            <input
              type="number"
              min="0"
              max="10000000"
              step="0.01"
              name="potential"
              defaultValue={prefill?.potential_cents != null ? prefill.potential_cents / 100 : lead ? lead.potential_cents / 100 : ""}
            />
          </Field>
          <label className="check-field span-2">
            <input
              type="checkbox"
              name="instagram_active"
              defaultChecked={prefill?.instagram_active ?? lead?.instagram_active}
            />
            {tr("Confirmei que o Instagram está ativo")}
          </label>
          <Field label={tr("Anotações")} className="span-2">
            <textarea
              name="notes"
              rows={3}
              maxLength={5000}
              defaultValue={prefill?.notes ?? lead?.notes}
              placeholder={tr("Contexto útil para a próxima conversa")}
            />
          </Field>
        </div>
        <ErrorText error={error} />
        <div className="form-actions">
          <button className="button" type="button" onClick={onClose}>
            Cancelar
          </button>
          <Submit busy={busy}>
            {lead ? tr("Salvar alterações") : tr("Adicionar estabelecimento")}
          </Submit>
        </div>
      </form>
    </Modal>
  );
}
