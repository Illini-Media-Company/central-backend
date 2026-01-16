/**
 * 
 * 
 * Created by Jacob Slabosz on Jan. 14, 2026
 * Last modified Jan. 14, 2026
 */


/**
 * 
 * @param {String} dateString 
 * @param {Boolean} includeYear `true` to always include year, `false` to omit if current year
 * @param {Boolean} includeTime `true` to include time, `false` to omit time
 * @returns {String} Formatted date string in AP Style
 */
function stringToAPDate(dateString, includeYear = false, includeTime = true) {
    const date = new Date(dateString);
  
    const months = [
        "Jan.", "Feb.", "March", "April", "May", "June", 
        "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."
    ];
  
    const month = months[date.getUTCMonth()];
    const day = date.getUTCDate();
    const year = date.getUTCFullYear();
    const currentYear = new Date().getFullYear();

    if (!includeTime) {
        if (includeYear) {
            return `${month} ${day}, ${year}`;
        } else {
            return year === currentYear 
                ? `${month} ${day}` 
                : `${month} ${day}, ${year}`;
        }
    }

    // Time Formatting (a.m./p.m.)
    let hours = date.getUTCHours();
    const minutes = date.getUTCMinutes();
    const ampm = hours >= 12 ? "p.m." : "a.m.";
    
    // Convert to 12-hour format
    hours = hours % 12;
    hours = hours ? hours : 12; // the hour '0' should be '12'
    const minutesStr = minutes < 10 ? `0${minutes}` : minutes;
  
    // Handle Noon and Midnight
    let timeStr = `${hours}:${minutesStr} ${ampm}`;
    if (hours === 12 && minutes === 0) {
        timeStr = ampm === "p.m." ? "noon" : "midnight";
    }

    // Assemble Date
    // Omit the year if it's the current year
    if (includeYear) {
        return `${month} ${day}, ${year}, ${timeStr}`;
    } else {
        const datePart = year === currentYear 
            ? `${month} ${day}` 
            : `${month} ${day}, ${year}`;
    }

    return `${datePart}, ${timeStr}`;
}
