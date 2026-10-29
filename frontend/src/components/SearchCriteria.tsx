import { useId } from "react";
import { tr } from "../i18n";
import type { CommercialIntent } from "../searchTypes";

export type Criteria = Pick<
  CommercialIntent,
  | "sectors"
  | "profile"
  | "requirements"
  | "preferences"
  | "exclusions"
  | "requirement_mode"
> & {
  accept_unresolved: boolean;
};
export type PreparedSearch = {
  intent: CommercialIntent;
  warnings: string[];
  sectors: string[];
};
export function criteriaFrom(intent: CommercialIntent): Criteria {
  const {
    sectors,
    profile,
    requirements,
    preferences,
    exclusions,
    requirement_mode,
  } = intent;
  return {
    sectors,
    profile,
    requirements,
    preferences,
    exclusions,
    requirement_mode,
    accept_unresolved: false,
  };
}
const requirements: Record<string, string> = {
  no_site: "Sem site confirmado",
  poor_site: "Site com problemas",
  whatsapp: "WhatsApp disponível",
  phone: "Telefone disponível",
  instagram: "Instagram disponível",
  active: "Atividade confirmada",
  independent: "Independência confirmada",
};
export default function SearchCriteria({
  value,
  sectors,
  warnings,
  onChange,
}: {
  value: Criteria;
  sectors: string[];
  warnings: string[];
  onChange: (value: Criteria) => void;
}) {
  const id = useId();
  function toggle(
    field: "sectors" | "requirements" | "preferences" | "exclusions",
    key: string,
  ) {
    onChange({
      ...value,
      [field]: value[field].includes(key)
        ? value[field].filter((item) => item !== key)
        : [...value[field], key],
    });
  }
  return (
    <section className="search-criteria" aria-label={tr("Ajustar critérios")}>
      <fieldset>
        <legend>{tr("Nichos opcionais (até 4)")}</legend>
        <div className="search-criteria-options">
          {sectors.map((sector) => (
            <label key={sector}>
              <input
                type="checkbox"
                checked={value.sectors.includes(sector)}
                disabled={
                  !value.sectors.includes(sector) && value.sectors.length >= 4
                }
                onChange={() => toggle("sectors", sector)}
              />
              {tr(sector)}
            </label>
          ))}
        </div>
      </fieldset>
      {(["requirements", "preferences"] as const).map((field) => (
        <fieldset key={field}>
          <legend>
            {tr(
              field === "requirements"
                ? "Requisitos obrigatórios"
                : "Preferências",
            )}
          </legend>
          <div className="search-criteria-options">
            {Object.entries(requirements).map(([key, label]) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={value[field].includes(key)}
                  onChange={() => toggle(field, key)}
                />
                {tr(label)}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      <div>
        <label htmlFor={`${id}-mode`}>{tr("Combinação dos requisitos")}</label>
        <select
          id={`${id}-mode`}
          value={value.requirement_mode}
          onChange={(e) =>
            onChange({
              ...value,
              requirement_mode: e.target.value as Criteria["requirement_mode"],
            })
          }
        >
          <option value="all">{tr("Todos obrigatórios")}</option>
          <option value="any">{tr("Pelo menos um")}</option>
        </select>
      </div>
      <div className="search-criteria-profile">
        <div>
          <label htmlFor={`${id}-type`}>{tr("Modelo comercial")}</label>
          <select
            id={`${id}-type`}
            value={value.profile.business_type}
            onChange={(e) =>
              onChange({
                ...value,
                profile: { ...value.profile, business_type: e.target.value },
              })
            }
          >
            <option value="local">{tr("Atendimento local")}</option>
            <option value="b2b">B2B</option>
            <option value="any">{tr("Qualquer")}</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-size`}>{tr("Porte")}</label>
          <select
            id={`${id}-size`}
            value={value.profile.size}
            onChange={(e) =>
              onChange({
                ...value,
                profile: { ...value.profile, size: e.target.value },
              })
            }
          >
            <option value="small_medium">{tr("Pequena ou média")}</option>
            <option value="any">{tr("Qualquer")}</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-independence`}>{tr("Autonomia")}</label>
          <select
            id={`${id}-independence`}
            value={value.profile.independence}
            onChange={(e) =>
              onChange({
                ...value,
                profile: { ...value.profile, independence: e.target.value },
              })
            }
          >
            <option value="preferred">{tr("Preferir independentes")}</option>
            <option value="required">{tr("Exigir independência")}</option>
            <option value="any">{tr("Qualquer")}</option>
          </select>
        </div>
      </div>
      <fieldset>
        <legend>{tr("Excluir")}</legend>
        <div className="search-criteria-options">
          {Object.entries({
            centralized_chains: "Redes centralizadas",
            public_entities: "Entidades públicas",
            closed: "Operação encerrada",
            ...Object.fromEntries(sectors.map((sector) => [sector, sector])),
          }).map(([key, label]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={value.exclusions.includes(key)}
                onChange={() => toggle("exclusions", key)}
              />
              {tr(label)}
            </label>
          ))}
        </div>
      </fieldset>
      {warnings.length > 0 && (
        <div className="search-criteria-warning">
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{tr(warning)}</li>
            ))}
          </ul>
          <label>
            <input
              type="checkbox"
              checked={value.accept_unresolved}
              onChange={(e) =>
                onChange({ ...value, accept_unresolved: e.target.checked })
              }
            />
            {tr(
              "Aplicar somente os critérios acima; ignorar os trechos não reconhecidos.",
            )}
          </label>
        </div>
      )}
    </section>
  );
}
