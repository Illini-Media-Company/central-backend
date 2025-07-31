import React from 'react'
import { FaChevronDown, FaChevronUp } from 'react-icons/fa'
import './DropdownButton.css'

const DropdownButton = ({children, open, toggle}) => {
  return (
    <div onClick={toggle} className={`dropdown-button ${open ? 'dropdown-button-open' : null}`}>
      {children}
      <span className='dropdown-icon'>
        {open ? <FaChevronUp/> : <FaChevronDown/>}
      </span>
    </div>
  )
}

export default DropdownButton