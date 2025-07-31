import React, { useState } from "react";
import './Form.css'

export const FormContext = React.createContext();

export default function Form({ children, onSubmit }) {
    const [formData, setFormData] = useState({});

    const updateField = (name, value) => {
        setFormData((prev) => ({ ...prev, [name]: value }));
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <FormContext.Provider value={{ formData, updateField }}>
            <div className="form-container">
                <form onSubmit={handleSubmit} className="form">
                    {children}
                    <button type="submit" className="submit-button">Submit</button>
                </form>
            </div>
        </FormContext.Provider>
    );
}