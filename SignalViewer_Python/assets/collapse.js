/**
 * Clientside collapse/expand for CSV nodes in signal tree.
 * This runs entirely in the browser - no server round-trip needed.
 * 
 * Uses event delegation for efficiency - handlers survive Dash tree rebuilds.
 */

(function() {
    'use strict';

    // Use event delegation on the signal tree container
    function initCollapseHandlers() {
        const signalTree = document.getElementById('signal-tree');
        if (!signalTree) {
            // Retry if tree not ready yet
            setTimeout(initCollapseHandlers, 300);
            return;
        }

        // Check if already initialized
        if (signalTree.dataset.collapseInit === 'true') return;
        signalTree.dataset.collapseInit = 'true';

        // Event delegation - handle clicks on csv-folder-header elements
        signalTree.addEventListener('click', function(e) {
            // Find the header element
            const header = e.target.closest('.csv-folder-header');
            if (!header) return;

            // Don't toggle if clicked on a checkbox, button, or other interactive element
            if (e.target.closest('input, button, a, .form-check-input')) return;

            // Toggle collapsed class on header
            header.classList.toggle('collapsed');
            
            // Toggle collapsed class on the signals list (next sibling)
            const signalsList = header.nextElementSibling;
            if (signalsList && signalsList.classList.contains('csv-signals-list')) {
                signalsList.classList.toggle('collapsed');
            }

            // Update the collapse icon text
            const icon = header.querySelector('.collapse-icon');
            if (icon) {
                icon.textContent = header.classList.contains('collapsed') ? '▶' : '▼';
            }

            // Update folder icon
            const folderIcon = header.querySelector('.fa-folder-open, .fa-folder');
            if (folderIcon) {
                if (header.classList.contains('collapsed')) {
                    folderIcon.classList.remove('fa-folder-open');
                    folderIcon.classList.add('fa-folder');
                } else {
                    folderIcon.classList.remove('fa-folder');
                    folderIcon.classList.add('fa-folder-open');
                }
            }

            // Prevent event from bubbling
            e.stopPropagation();
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initCollapseHandlers, 500);
        });
    } else {
        setTimeout(initCollapseHandlers, 500);
    }
})();

