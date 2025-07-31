/*
 * @file          main.jsx
 * @author        Jacob Slabosz
 * @date          2025-07-25
 * @decsription   
 */

import { useState } from 'react'
import './App.css'

import Form from "public-components/Form/Form";
import FormField from "public-components/FormField/FormField";
import FormFieldSelect from "public-components/FormFieldSelect/FormFieldSelect";
import FormFieldPhone from "public-components/FormField/FormFieldPhone";
import FormFieldDate from "public-components/FormField/FormFieldDate";

function App() {
  const displayData = (data) => {
    alert(`You submitted:
    ${Object.entries(data).map(([k, v]) => `${k} - ${v}`).join("\n")}`);
  };

  return (
    <div>
      <h1>Add Employee</h1>
      <Form onSubmit={displayData}>
        <FormField name="last-name" label="Last Name" />
        <FormField name="first-name" label="First Name" />
        <FormField name="imc-email" label="IMC Email" />
        <FormFieldPhone name="phone" label="Phone Number" />
        <FormField name="personal-email" label="Personal Email" />
        <FormFieldDate name="hire-date" label="Hire Date" />
      </Form>

      <h1>Add Position</h1>
      <Form onSubmit={displayData}>
        <FormField name="title" label="Title" />
        <FormFieldSelect name="brand" label="Brand" options={["Illini Media", "The Daily Illini", "WPGU", "Illio Yearbook", "Chambana Eats", "Illini Content Studio"]} />
        <FormFieldSelect name="pay_status" label="Pay Status" options={["Unpaid", "Hourly", "Salary", "Stipend"]} />
      </Form>
    </div>
  );
}

export default App
