import React from 'react'
import './DropdownContent.css'

const DropdownContent = ({children, open}) => {
  return (
    <div className={`dropdown-content ${open ? 'dropdown-content-open' : null}`}>
      {children}
    </div>
  )
}

export default DropdownContent