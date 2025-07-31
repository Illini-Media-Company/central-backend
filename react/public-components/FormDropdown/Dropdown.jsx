import React, { use } from 'react'
import { useState, useEffect, useRef, Children, cloneElement } from 'react'
import DropdownButton from '../FormDropdownButton/DropdownButton'
import DropdownContent from '../FormDropdownContent/DropdownContent'
import './Dropdown.css'

export default function Dropdown({buttonText, content}) {

  const [isOpen, setIsOpen] = useState(false);

  const dropdownRef = useRef();

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  }

  const closeDropdown = () => {
    setIsOpen(false);
  }

  useEffect(() => {
    const handler = (event) => {
      if (!dropdownRef.current) return;
      if (dropdownRef.current.contains(event.target)) return;
      setIsOpen(false);
    };

    document.addEventListener('click', handler);

    return () => {
      document.removeEventListener('click', handler);
    };
  }, [dropdownRef]);

  // Inject a close handler to close the dropdown when an option is chosen (besides checkboxes)
  const enhancedContent = Children.map(content, child => {
    if (!React.isValidElement(child)) 
      return child;

    if (child.props.type !== "checkbox") {
      return cloneElement(child, {
        onClick: (e) => {
          child.props.onClick && child.props.onClick(e);
          closeDropdown();
        }
      });
    }
    // Don't inject if it's a checkbox
    return child;
  });

  return (
    <div className='dropdown' ref={dropdownRef}>
      <DropdownButton toggle={toggleDropdown} open={isOpen}>
        {buttonText}
      </DropdownButton>
      <DropdownContent open={isOpen}>
        {enhancedContent}
      </DropdownContent>
    </div>
  )
}