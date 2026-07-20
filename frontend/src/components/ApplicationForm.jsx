import { COPY, BEVERAGE_TYPES } from "../copy.js";
import "./ApplicationForm.css";

const TEXT_FIELDS = [
  { name: "brandName", label: "Brand name" },
  { name: "classType", label: "Class / type" },
  { name: "alcoholContent", label: "Alcohol content (%)" },
  { name: "netContents", label: "Net contents" },
];

export default function ApplicationForm({ values, onChange, touched, onBlur }) {
  return (
    <div className="application-form">
      {TEXT_FIELDS.map((field) => {
        const isEmpty = touched[field.name] && !values[field.name].trim();
        return (
          <label key={field.name} className="form-field">
            <span className="form-field__label">{field.label}</span>
            <input
              type="text"
              value={values[field.name]}
              onChange={(event) => onChange(field.name, event.target.value)}
              onBlur={() => onBlur(field.name)}
              className={`form-field__input${isEmpty ? " form-field__input--error" : ""}`}
            />
            {isEmpty && <span className="form-field__error">{COPY.requiredField}</span>}
          </label>
        );
      })}

      <label className="form-field">
        <span className="form-field__label">Beverage type</span>
        <select
          value={values.beverageType}
          onChange={(event) => onChange("beverageType", event.target.value)}
          onBlur={() => onBlur("beverageType")}
          className={`form-field__input${touched.beverageType && !values.beverageType ? " form-field__input--error" : ""}`}
        >
          <option value="" disabled>
            Select…
          </option>
          {BEVERAGE_TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {touched.beverageType && !values.beverageType && (
          <span className="form-field__error">{COPY.requiredField}</span>
        )}
      </label>
    </div>
  );
}
