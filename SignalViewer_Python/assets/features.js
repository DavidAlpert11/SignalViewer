/**
 * Signal Viewer Pro - Advanced Features
 * Implements: Drag & Drop, Context Menu, Toast Notifications
 */

(function() {
    'use strict';

    // ========================================
    // TOAST NOTIFICATION SYSTEM
    // ========================================
    window.SignalViewerToast = {
        container: null,
        
        init: function() {
            if (this.container) return;
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            this.container.id = 'toast-container';
            document.body.appendChild(this.container);
        },
        
        show: function(message, type, duration) {
            this.init();
            type = type || 'info';
            duration = duration || 3000;
            
            var toast = document.createElement('div');
            toast.className = 'toast-notification ' + type;
            toast.innerHTML = '<span class="toast-message">' + message + '</span>';
            
            this.container.appendChild(toast);
            
            // Auto-remove after duration
            setTimeout(function() {
                toast.style.animation = 'slideOutRight 0.3s ease-out forwards';
                setTimeout(function() {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            }, duration);
            
            // Click to dismiss
            toast.addEventListener('click', function() {
                toast.style.animation = 'slideOutRight 0.3s ease-out forwards';
                setTimeout(function() {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            });
        },
        
        success: function(message) { this.show(message, 'success'); },
        error: function(message) { this.show(message, 'error'); },
        warning: function(message) { this.show(message, 'warning'); },
        info: function(message) { this.show(message, 'info'); }
    };

    // ========================================
    // CONTEXT MENU SYSTEM
    // ========================================
    window.SignalViewerContextMenu = {
        menu: null,
        currentTarget: null,
        
        init: function() {
            if (this.menu) return;
            
            this.menu = document.createElement('div');
            this.menu.className = 'context-menu';
            this.menu.id = 'signal-context-menu';
            this.menu.style.display = 'none';
            this.menu.innerHTML = `
                <div class="context-menu-item" data-action="properties">
                    <span class="icon">⚙️</span>
                    <span>Properties</span>
                </div>
                <div class="context-menu-item" data-action="duplicate">
                    <span class="icon">📋</span>
                    <span>Duplicate</span>
                </div>
                <div class="context-menu-item" data-action="move-up">
                    <span class="icon">⬆️</span>
                    <span>Move Up</span>
                </div>
                <div class="context-menu-item" data-action="move-down">
                    <span class="icon">⬇️</span>
                    <span>Move Down</span>
                </div>
                <div class="context-menu-divider"></div>
                <div class="context-menu-item" data-action="set-x-axis">
                    <span class="icon">📐</span>
                    <span>Set as X-Axis</span>
                </div>
                <div class="context-menu-item" data-action="derivative">
                    <span class="icon">📈</span>
                    <span>Create Derivative</span>
                </div>
                <div class="context-menu-item" data-action="integral">
                    <span class="icon">∫</span>
                    <span>Create Integral</span>
                </div>
                <div class="context-menu-divider"></div>
                <div class="context-menu-item danger" data-action="remove">
                    <span class="icon">🗑️</span>
                    <span>Remove</span>
                </div>
            `;
            document.body.appendChild(this.menu);
            
            var self = this;
            
            // Handle menu item clicks
            this.menu.addEventListener('click', function(e) {
                var item = e.target.closest('.context-menu-item');
                if (item) {
                    var action = item.dataset.action;
                    self.handleAction(action);
                }
                self.hide();
            });
            
            // Hide on click outside
            document.addEventListener('click', function(e) {
                if (!self.menu.contains(e.target)) {
                    self.hide();
                }
            });
            
            // Hide on scroll
            document.addEventListener('scroll', function() {
                self.hide();
            }, true);
            
            // Hide on escape
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    self.hide();
                }
            });
        },
        
        show: function(x, y, target) {
            this.init();
            this.currentTarget = target;
            
            // Position menu
            this.menu.style.display = 'block';
            this.menu.style.left = x + 'px';
            this.menu.style.top = y + 'px';
            
            // Adjust if off-screen
            var rect = this.menu.getBoundingClientRect();
            if (rect.right > window.innerWidth) {
                this.menu.style.left = (x - rect.width) + 'px';
            }
            if (rect.bottom > window.innerHeight) {
                this.menu.style.top = (y - rect.height) + 'px';
            }
        },
        
        hide: function() {
            if (this.menu) {
                this.menu.style.display = 'none';
            }
            this.currentTarget = null;
        },
        
        handleAction: function(action) {
            if (!this.currentTarget) return;
            
            var signalIdx = this.currentTarget.dataset.signalIdx;
            var signalName = this.currentTarget.dataset.signalName;
            var csvIdx = this.currentTarget.dataset.csvIdx;
            
            console.log('[Context Menu] Action:', action, 'Signal:', signalName, 'Idx:', signalIdx);
            
            // Dispatch custom event that Dash can listen to via clientside callback
            var event = new CustomEvent('signalContextAction', {
                detail: {
                    action: action,
                    signalIdx: parseInt(signalIdx),
                    signalName: signalName,
                    csvIdx: parseInt(csvIdx)
                }
            });
            document.dispatchEvent(event);
            
            // Show toast for feedback
            switch(action) {
                case 'properties':
                    // Click the properties button for this signal
                    var propBtn = document.querySelector('[id*="prop-btn"][id*="' + signalIdx + '"]');
                    if (propBtn) propBtn.click();
                    break;
                case 'duplicate':
                    SignalViewerToast.info('Signal duplicated');
                    break;
                case 'move-up':
                case 'move-down':
                    SignalViewerToast.info('Signal reordered');
                    break;
                case 'remove':
                    // Check the remove checkbox and click remove button
                    var checkbox = document.querySelector('#assigned-list input[type="checkbox"]');
                    if (checkbox) {
                        // Find the checkbox for this specific signal
                        var checkboxes = document.querySelectorAll('#assigned-list input[type="checkbox"]');
                        if (checkboxes[signalIdx]) {
                            checkboxes[signalIdx].checked = true;
                            checkboxes[signalIdx].dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                    var removeBtn = document.getElementById('btn-remove');
                    if (removeBtn) {
                        setTimeout(function() { removeBtn.click(); }, 100);
                    }
                    break;
                case 'derivative':
                case 'integral':
                    SignalViewerToast.info('Operation: ' + action);
                    break;
                case 'set-x-axis':
                    SignalViewerToast.info('Set as X-axis');
                    break;
            }
        }
    };

    // ========================================
    // DRAG & DROP REORDERING
    // ========================================
    window.SignalViewerDragDrop = {
        draggedElement: null,
        draggedIndex: null,
        
        init: function() {
            var self = this;
            
            // Use event delegation on the assigned-list container
            var assignedList = document.getElementById('assigned-list');
            if (!assignedList) {
                setTimeout(function() { self.init(); }, 500);
                return;
            }
            
            if (assignedList.dataset.dragInit === 'true') return;
            assignedList.dataset.dragInit = 'true';
            
            // Drag start
            assignedList.addEventListener('dragstart', function(e) {
                var item = e.target.closest('.draggable-signal');
                if (!item) return;
                
                self.draggedElement = item;
                self.draggedIndex = parseInt(item.dataset.signalIdx);
                item.classList.add('dragging');
                
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', self.draggedIndex);
            });
            
            // Drag end
            assignedList.addEventListener('dragend', function(e) {
                if (self.draggedElement) {
                    self.draggedElement.classList.remove('dragging');
                }
                self.draggedElement = null;
                self.draggedIndex = null;
                
                // Remove all drag-over indicators
                document.querySelectorAll('.drag-over').forEach(function(el) {
                    el.classList.remove('drag-over');
                });
            });
            
            // Drag over
            assignedList.addEventListener('dragover', function(e) {
                e.preventDefault();
                var item = e.target.closest('.draggable-signal');
                if (!item || item === self.draggedElement) return;
                
                e.dataTransfer.dropEffect = 'move';
                
                // Clear all drag-over states
                document.querySelectorAll('.drag-over').forEach(function(el) {
                    el.classList.remove('drag-over');
                });
                
                // Add indicator to current target
                item.classList.add('drag-over');
            });
            
            // Drop
            assignedList.addEventListener('drop', function(e) {
                e.preventDefault();
                
                var dropTarget = e.target.closest('.draggable-signal');
                if (!dropTarget || dropTarget === self.draggedElement) return;
                
                var fromIdx = self.draggedIndex;
                var toIdx = parseInt(dropTarget.dataset.signalIdx);
                
                console.log('[Drag & Drop] Move signal from', fromIdx, 'to', toIdx);
                
                // Dispatch custom event for Dash callback
                var event = new CustomEvent('signalReorder', {
                    detail: { fromIdx: fromIdx, toIdx: toIdx }
                });
                document.dispatchEvent(event);
                
                SignalViewerToast.success('Signal reordered');
            });
            
            console.log('[SignalViewer] Drag & Drop initialized');
        }
    };

    // ========================================
    // CONTEXT MENU TRIGGER FOR SIGNALS
    // ========================================
    function initContextMenuTriggers() {
        var assignedList = document.getElementById('assigned-list');
        if (!assignedList) {
            setTimeout(initContextMenuTriggers, 500);
            return;
        }
        
        if (assignedList.dataset.contextInit === 'true') return;
        assignedList.dataset.contextInit = 'true';
        
        // Right-click handler using event delegation
        assignedList.addEventListener('contextmenu', function(e) {
            var item = e.target.closest('.draggable-signal');
            if (!item) return;
            
            e.preventDefault();
            SignalViewerContextMenu.show(e.pageX, e.pageY, item);
        });
        
        console.log('[SignalViewer] Context menu triggers initialized');
    }

    // ========================================
    // INITIALIZATION
    // ========================================
    function initAllFeatures() {
        SignalViewerToast.init();
        SignalViewerContextMenu.init();
        SignalViewerDragDrop.init();
        initContextMenuTriggers();
        
        console.log('[SignalViewer] All advanced features initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initAllFeatures, 800);
        });
    } else {
        setTimeout(initAllFeatures, 800);
    }

    // Re-initialize on Dash component updates (MutationObserver)
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length > 0) {
                // Check if assigned-list was updated
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        if (node.id === 'assigned-list' || node.querySelector && node.querySelector('#assigned-list')) {
                            setTimeout(function() {
                                SignalViewerDragDrop.init();
                                initContextMenuTriggers();
                            }, 100);
                        }
                    }
                });
            }
        });
    });

    // Start observing after a delay
    setTimeout(function() {
        var appContainer = document.getElementById('app-container');
        if (appContainer) {
            observer.observe(appContainer, { childList: true, subtree: true });
        }
    }, 1500);

})();

// Add CSS animation for toast slide out
var style = document.createElement('style');
style.textContent = `
    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
    .context-menu-item.danger {
        color: #ff6b6b;
    }
    .context-menu-item.danger:hover {
        background-color: rgba(255, 107, 107, 0.3) !important;
    }
`;
document.head.appendChild(style);

// ========================================
// SIDEBAR COLLAPSE TOGGLE
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    // Wait for Dash to render
    setTimeout(function() {
        var sidebarToggle = document.getElementById('btn-collapse-sidebar');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', function() {
                // Find the left sidebar column (first child of main content row)
                var sidebar = this.closest('.col-2');
                if (sidebar) {
                    sidebar.classList.toggle('sidebar-collapsed');
                    // Update button text
                    this.textContent = sidebar.classList.contains('sidebar-collapsed') ? '▶' : '◀';
                    // Adjust plot width
                    var plotCol = sidebar.nextElementSibling;
                    if (plotCol && plotCol.classList.contains('col-8')) {
                        if (sidebar.classList.contains('sidebar-collapsed')) {
                            plotCol.classList.remove('col-8');
                            plotCol.classList.add('col-9');
                            sidebar.classList.remove('col-2');
                            sidebar.classList.add('col-1');
                        } else {
                            plotCol.classList.remove('col-9');
                            plotCol.classList.add('col-8');
                            sidebar.classList.remove('col-1');
                            sidebar.classList.add('col-2');
                        }
                    }
                }
            });
        }
    }, 1000);
});

