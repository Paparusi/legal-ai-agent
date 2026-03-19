/**
 * Security utilities for Legal AI Agent frontend
 * FIX 16: XSS Prevention
 */

/**
 * Escape HTML to prevent XSS attacks
 * Use this when inserting user data into innerHTML
 * @param {string} str - String to escape
 * @returns {string} - HTML-escaped string
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Safely set text content (preferred over innerHTML)
 * @param {HTMLElement} element - Element to update
 * @param {string} text - Text content to set
 */
function setTextContent(element, text) {
    element.textContent = text;
}

/**
 * Safely create HTML element with escaped content
 * @param {string} tag - HTML tag name
 * @param {string} content - Text content (will be escaped)
 * @param {Object} attributes - Attributes to set
 * @returns {HTMLElement}
 */
function createSafeElement(tag, content, attributes = {}) {
    const elem = document.createElement(tag);
    if (content) {
        elem.textContent = content;  // Safe - no XSS risk
    }
    for (const [key, value] of Object.entries(attributes)) {
        if (key === 'href' || key === 'src') {
            // Validate URL to prevent javascript: URLs
            if (value && !value.startsWith('javascript:') && !value.startsWith('data:')) {
                elem.setAttribute(key, value);
            }
        } else {
            elem.setAttribute(key, value);
        }
    }
    return elem;
}

/**
 * Sanitize URL to prevent javascript: and data: URIs
 * @param {string} url - URL to sanitize
 * @returns {string|null} - Sanitized URL or null if dangerous
 */
function sanitizeUrl(url) {
    if (!url) return null;
    const lower = url.toLowerCase().trim();
    if (lower.startsWith('javascript:') || 
        lower.startsWith('data:text/html') ||
        lower.startsWith('vbscript:')) {
        console.warn('Blocked dangerous URL:', url);
        return null;
    }
    return url;
}

/**
 * Example: Safe rendering of user data in table
 */
function renderUserDataSafe(userData) {
    const row = document.createElement('tr');
    
    // ❌ WRONG (XSS vulnerable):
    // row.innerHTML = `<td>${userData.name}</td><td>${userData.email}</td>`;
    
    // ✅ CORRECT (XSS safe):
    const nameCell = document.createElement('td');
    nameCell.textContent = userData.name;  // Safe
    
    const emailCell = document.createElement('td');
    emailCell.textContent = userData.email;  // Safe
    
    row.appendChild(nameCell);
    row.appendChild(emailCell);
    
    return row;
}

/**
 * If you MUST use innerHTML with user data, escape it:
 */
function renderWithInnerHTMLSafe(userData) {
    const container = document.getElementById('user-container');
    
    // ✅ Escaped before using innerHTML
    container.innerHTML = `
        <div class="user-card">
            <h3>${escapeHtml(userData.name)}</h3>
            <p>${escapeHtml(userData.bio)}</p>
        </div>
    `;
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        escapeHtml,
        setTextContent,
        createSafeElement,
        sanitizeUrl,
        renderUserDataSafe,
        renderWithInnerHTMLSafe
    };
}
