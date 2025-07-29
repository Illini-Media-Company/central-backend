import React, { useContext, useState } from "react";
import { FormContext } from "../Form/Form";
import Dropdown from "../FormDropdown/Dropdown";
import DropdownItem from "../FormDropdownItem/DropdownItem";
import './FormFieldSelect.css'

export default function FormFieldSelect({ name, label, options = [] }) {
    const { formData, updateField } = useContext(FormContext);
    const [selected, setSelected] = useState(formData[name] || "");

    const handleSelect = (option) => {
        setSelected(option);
        updateField(name, option);
    };

    return (
        <div className="form-field-select">
            <label>{label}:</label>
            <Dropdown
                buttonText={selected || `Select...`}
                content={
                <div>
                    {options.map((opt) => (
                    <DropdownItem
                        key={opt}
                        onClick={() => handleSelect(opt)}
                    >
                        {opt}
                    </DropdownItem>
                    ))}
                </div>
                }
            />
        </div>
    );
}