import React from 'react'
import './DropdownItem.css'
import { ImCheckboxChecked, ImCheckboxUnchecked } from 'react-icons/im';

const DropdownItem = ({children, type, label, checked, onClick}) => {
  if (type === "checkbox") {
    return (
      <div className='dropdown-item dropdown-item-checkbox' onClick={onClick}>
        <span className='checkbox-icon'>
          {checked ? <ImCheckboxChecked/> : <ImCheckboxUnchecked/>}
        </span>
        {label}
      </div>
    );
  }

  // Fallback when no type is provided
  return (
    <div className='dropdown-item' onClick={onClick}>
      {children}
    </div>
  );
}

export default DropdownItem