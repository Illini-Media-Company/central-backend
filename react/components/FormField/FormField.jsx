import React, { useContext } from "react";
import { FormContext } from "../Form/Form";
import './FormField.css'

export default function FormField({ name, label, type = "text" }) {
    const { formData, updateField } = useContext(FormContext);

    return (
        <div className="form-field">
            <label>
                {label}
            </label>
            <input
                type={type}
                name={name}
                value={formData[name] || ""}
                onChange={(e) => updateField(name, e.target.value)}
            />
        </div>
    );
}
