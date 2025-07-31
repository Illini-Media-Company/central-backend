import React, { useContext } from "react";
import { FormContext } from "../Form/Form";
import './FormField.css'

function formatPhoneNumber(value) {
  const digits = value.replace(/\D/g, "").slice(0, 10);
  const len = digits.length;

  if (len <= 3) return digits;
  if (len <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

export default function FormFieldPhone({ name, label }) {
  const { formData, updateField } = useContext(FormContext);

  const handleChange = (e) => {
    const formatted = formatPhoneNumber(e.target.value);
    updateField(name, formatted);
  };

  return (
    <div className="form-field">
      <label>{label}</label>
      <input
        type="tel"
        name={name}
        value={formData[name] || ""}
        onChange={handleChange}
        placeholder="(123) 456-7890"
      />
    </div>
  );
}