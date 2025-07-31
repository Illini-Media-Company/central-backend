import React, { useContext } from "react";
import { FormContext } from "../Form/Form";
import './FormField.css'

function formatDate(value) {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  const len = digits.length;

  if (len <= 2) return digits;
  if (len <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export default function FormFieldDate({ name, label }) {
  const { formData, updateField } = useContext(FormContext);

  const handleChange = (e) => {
    const formatted = formatDate(e.target.value);
    updateField(name, formatted);
  };

  return (
    <div className="form-field">
      <label>{label}</label>
      <input
        type="text"
        name={name}
        value={formData[name] || ""}
        onChange={handleChange}
        placeholder="MM/DD/YYYY"
      />
    </div>
  );
}