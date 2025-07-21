    % Updated SignalViewerApp.m - Main changes for light mode and streaming
classdef SignalViewerApp < matlab.apps.AppBase
    properties
        % Main UI
        UIFigure
        ControlPanel
        MainTabGroup

        % Enhanced color schemes
        Colors = [
            0.2 0.6 0.9;    % Blue
            0.9 0.3 0.3;    % Red
            0.3 0.8 0.4;    % Green
            0.9 0.6 0.2;    % Orange
            0.7 0.3 0.9;    % Purple
            0.2 0.9 0.8;    % Cyan
            0.9 0.8 0.2;    % Yellow
            0.9 0.4 0.7;    % Pink
            0.5 0.5 0.5;    % Gray
            0.1 0.1 0.9;    % Dark Blue
            ];

        % Controls
        RowsSpinner
        ColsSpinner
        SubplotDropdown
        StartButton
        StopButton
        ClearButton
        ExportButton
        ExportPDFButton
        StatsButton
        ResetZoomButton
        CSVPathField
        AutoScaleCheckbox
        StatusLabel
        DataRateLabel

        % Visual Enhancement Properties
        SubplotHighlightBoxes
        CurrentHighlightColor = [0.2 0.8 0.4]  % Green highlight color

        % Subsystems
        PlotManager
        DataManager
        ConfigManager
        UIController
        SignalScaling
        StateSignals
        SaveConfigButton
        LoadConfigButton
        SaveSessionButton % Button for saving session
        LoadSessionButton % Button for loading session
        SyncZoomToggle % Toggle button for synchronized zoom/pan
        CursorToggle % Toggle button for data cursor

        % Multi-CSV support
        DataTables   % Cell array of tables, one per CSV
        CSVFileNames % Cell array of CSV file names
        SignalTree   % uitree for grouped signal selection
        SignalPropsTable % uitable for scale and state editing
        SignalSearchField % uieditfield for signal search
        CSVColors % Cell array of colors for each CSV
        AssignmentUndoStack
        AssignmentRedoStack
        SubplotMetadata % cell array {tabIdx}{subplotIdx} with struct('Notes',...,'Tags',...)
        UndoButton
        RedoButton
        SaveTemplateButton
        LoadTemplateButton
        RefreshCSVsButton
        EditNotesButton
        ManageTemplatesButton
        SignalStyles % containers.Map or struct for color/width per signal
        StreamingInfoLabel % Label for streaming info
    end

    methods
        function app = SignalViewerApp()
            %=== Create UI with LIGHT MODE styling ===%
            app.UIFigure = uifigure('Name', 'Signal Viewer Pro', ...
                'Position', [100 100 1200 800], ...
                'Color', [0.94 0.94 0.94]);  % Light gray background

            % Light Mode Control Panel
            app.ControlPanel = uipanel(app.UIFigure, ...
                'Title', 'Control Panel', ...
                'Position', [1 1 318 799], ...
                'BackgroundColor', [0.96 0.96 0.96], ...  % Very light gray
                'ForegroundColor', [0.1 0.1 0.1], ...     % Dark text
                'BorderType', 'line', ...
                'BorderWidth', 1);

            % Main Tab Group (default light styling)
            app.MainTabGroup = uitabgroup(app.UIFigure, ...
                'Position', [320 1 880 799]);

            %=== Create Enhanced Components ===%
            app.createEnhancedComponents();

            %=== Instantiate Subsystems ===%
            app.PlotManager = PlotManager(app);
            app.PlotManager.initialize();
            app.DataManager   = DataManager(app);
            app.ConfigManager = ConfigManager(app);
            app.UIController  = UIController(app);

            %=== Connect Callbacks ===%
            app.UIController.setupCallbacks();
            %=== Initialize visual enhancements ===%
            app.initializeVisualEnhancements();
        end

        function createEnhancedComponents(app)
            % Enhanced layout with LIGHT MODE styling
            % Only keep controls that are actually used in the current workflow
            % (Tab management and signal table controls are removed)

            % Modern menu bar at the top
            fileMenu = uimenu(app.UIFigure, 'Text', 'File');
            uimenu(fileMenu, 'Text', '💾 Save Config', 'MenuSelectedFcn', @(src, event) app.saveConfig());
            uimenu(fileMenu, 'Text', '📁 Load Config', 'MenuSelectedFcn', @(src, event) app.loadConfig());
            uimenu(fileMenu, 'Text', '💾 Save Session', 'MenuSelectedFcn', @(src, event) app.saveSession());
            uimenu(fileMenu, 'Text', '📁 Load Session', 'MenuSelectedFcn', @(src, event) app.loadSession());

            actionsMenu = uimenu(app.UIFigure, 'Text', 'Actions');
            uimenu(actionsMenu, 'Text', '▶️ Start', 'MenuSelectedFcn', @(src, event) app.menuStart());
            uimenu(actionsMenu, 'Text', '⏹️ Stop', 'MenuSelectedFcn', @(src, event) app.menuStop());
            uimenu(actionsMenu, 'Text', '🗑️ Clear', 'MenuSelectedFcn', @(src, event) app.menuClear());
            uimenu(actionsMenu, 'Text', '📈 Statistics', 'MenuSelectedFcn', @(src, event) app.menuStatistics());
            uimenu(actionsMenu, 'Text', '🔍 Reset Zoom', 'MenuSelectedFcn', @(src, event) app.menuResetZoom());

            exportMenu = uimenu(app.UIFigure, 'Text', 'Export');
            uimenu(exportMenu, 'Text', '📊 Export CSV', 'MenuSelectedFcn', @(src, event) app.menuExportCSV());
            uimenu(exportMenu, 'Text', '📄 Export PDF', 'MenuSelectedFcn', @(src, event) app.menuExportPDF());

            viewMenu = uimenu(app.UIFigure, 'Text', 'View');
            uimenu(viewMenu, 'Text', 'Sync Zoom', 'MenuSelectedFcn', @(src, event) app.menuToggleSyncZoom());
            uimenu(viewMenu, 'Text', 'Cursor', 'MenuSelectedFcn', @(src, event) app.menuToggleCursor());

            % Undo/Redo buttons
            app.UndoButton = uibutton(app.ControlPanel, 'push', 'Text', 'Undo', 'Position', [20 370 60 22], 'ButtonPushedFcn', @(src, event) app.undoAssignment());
            app.RedoButton = uibutton(app.ControlPanel, 'push', 'Text', 'Redo', 'Position', [90 370 60 22], 'ButtonPushedFcn', @(src, event) app.redoAssignment());

            % Template and refresh buttons
            app.SaveTemplateButton = uibutton(app.ControlPanel, 'push', 'Text', 'Save Template', 'Position', [20 400 100 22], 'ButtonPushedFcn', @(src, event) app.saveTemplate());
            app.LoadTemplateButton = uibutton(app.ControlPanel, 'push', 'Text', 'Load Template', 'Position', [130 400 100 22], 'ButtonPushedFcn', @(src, event) app.loadTemplate());
            app.RefreshCSVsButton = uibutton(app.ControlPanel, 'push', 'Text', 'Refresh CSVs', 'Position', [240 400 70 22], 'ButtonPushedFcn', @(src, event) app.refreshCSVs());

            % Edit Notes/Tags button
            app.EditNotesButton = uibutton(app.ControlPanel, 'push', 'Text', 'Edit Notes/Tags', 'Position', [20 430 120 22], 'ButtonPushedFcn', @(src, event) app.editSubplotMetadata());

            % Manage Templates button
            app.ManageTemplatesButton = uibutton(app.ControlPanel, 'push', 'Text', 'Manage Templates', 'Position', [150 430 120 22], 'ButtonPushedFcn', @(src, event) app.manageTemplates());

            % Layout spinners with light styling
            uilabel(app.ControlPanel, 'Text', 'Current Tab Layout:', ...
                'Position', [20 640 120 22], ...
                'FontColor', [0.1 0.1 0.1], ...      % Dark text
                'FontWeight', 'bold');

            uilabel(app.ControlPanel, 'Text', 'Rows:', ...
                'Position', [20 620 40 22], ...
                'FontColor', [0.1 0.1 0.1], ...
                'FontWeight', 'bold');
            app.RowsSpinner = uispinner(app.ControlPanel, ...
                'Position', [60 620 50 22], ...
                'Limits', [1 10], ...
                'Value', 2, ...
                'BackgroundColor', [1 1 1], ...      % White background
                'FontColor', [0.1 0.1 0.1]);        % Dark text

            uilabel(app.ControlPanel, 'Text', 'Cols:', ...
                'Position', [130 620 40 22], ...
                'FontColor', [0.1 0.1 0.1], ...
                'FontWeight', 'bold');
            app.ColsSpinner = uispinner(app.ControlPanel, ...
                'Position', [170 620 50 22], ...
                'Limits', [1 10], ...
                'Value', 1, ...
                'BackgroundColor', [1 1 1], ...      % White background
                'FontColor', [0.1 0.1 0.1]);        % Dark text

            % Subplot dropdown with light styling
            uilabel(app.ControlPanel, 'Text', 'Current Subplot:', ...
                'Position', [20 590 100 22], ...
                'FontColor', [0.1 0.1 0.1], ...
                'FontWeight', 'bold');
            app.SubplotDropdown = uidropdown(app.ControlPanel, ...
                'Position', [130 590 110 22], ...
                'Items', {'Plot 1'}, ...
                'Value', 'Plot 1', ...
                'BackgroundColor', [1 1 1], ...      % White background
                'FontColor', [0.1 0.1 0.1]);        % Dark text

            % Search box for signals
            app.SignalSearchField = uieditfield(app.ControlPanel, 'text', ...
                'Position', [20 340 280 22], ...
                'Placeholder', 'Search signals...', ...
                'ValueChangingFcn', @(src, event) app.filterSignals(event.Value));

            % Signal selection tree
            app.SignalTree = uitree(app.ControlPanel, ...
                'Position', [20 130 280 200], ...
                'SelectionChangedFcn', @(src, event) app.onSignalTreeSelectionChanged());
            try
                app.SignalTree.Multiselect = 'on';
            end
            % Enable drag-and-drop for the signal tree (MATLAB R2021b+)
            try
                app.SignalTree.Draggable = 'on';
            end
            % Add context menu for clearing all signals from subplot
            cm = uicontextmenu(app.UIFigure);
            uimenu(cm, 'Text', 'Clear All Signals from Subplot', 'MenuSelectedFcn', @(src, event) app.clearAllSignalsFromSubplot());
            app.SignalTree.ContextMenu = cm;

            % Table for editing scale and state for selected signals
            app.SignalPropsTable = uitable(app.ControlPanel, ...
                'Position', [20 20 400 120], ...
                'ColumnName', {'Signal', 'Scale', 'State', 'Color', 'LineWidth'}, ...
                'ColumnEditable', [false true true false true], ... % Color not editable by typing
                'CellEditCallback', @(src, event) app.onSignalPropsEdit(event));

            % Add StreamingInfoLabel below StatusLabel
            app.StreamingInfoLabel = uilabel(app.ControlPanel, ...
                'Position', [20 60 280 22], ...
                'Text', '', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 12);
        end

        function editSubplotMetadata(app)
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            if isempty(app.SubplotMetadata) || numel(app.SubplotMetadata) < tabIdx || numel(app.SubplotMetadata{tabIdx}) < subplotIdx || isempty(app.SubplotMetadata{tabIdx}{subplotIdx})
                notes = '';
                tags = '';
            else
                meta = app.SubplotMetadata{tabIdx}{subplotIdx};
                notes = meta.Notes;
                tags = meta.Tags;
            end
            d = dialog('Name', 'Edit Notes/Tags', 'Position', [300 300 350 220]);
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 170 80 20], 'String', 'Notes:');
            notesBox = uicontrol('Parent', d, 'Style', 'edit', 'Position', [20 100 310 80], 'String', notes, 'Max', 2, 'HorizontalAlignment', 'left');
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 70 80 20], 'String', 'Tags:');
            tagsBox = uicontrol('Parent', d, 'Style', 'edit', 'Position', [20 40 310 25], 'String', tags, 'HorizontalAlignment', 'left');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Save', 'Position', [200 10 60 25], 'Callback', @(~,~) saveMeta());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', 'Position', [270 10 60 25], 'Callback', @(~,~) close(d));
            function saveMeta()
                n = notesBox.String;
                t = tagsBox.String;
                if numel(app.SubplotMetadata) < tabIdx
                    app.SubplotMetadata{tabIdx} = cell(1, subplotIdx);
                end
                if numel(app.SubplotMetadata{tabIdx}) < subplotIdx
                    app.SubplotMetadata{tabIdx}{subplotIdx} = struct('Notes', '', 'Tags', '');
                end
                app.SubplotMetadata{tabIdx}{subplotIdx} = struct('Notes', n, 'Tags', t);
                close(d);
            end
        end

        function highlightSelectedSubplot(app, tabIdx, subplotIdx)
            % Highlight the currently selected subplot with a colored border
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
                    ~isempty(app.PlotManager.AxesArrays{tabIdx}) && ...
                    subplotIdx <= numel(app.PlotManager.AxesArrays{tabIdx})

                % Clear previous highlights
                app.clearSubplotHighlights(tabIdx);

                % Add highlight to selected subplot
                ax = app.PlotManager.AxesArrays{tabIdx}(subplotIdx);
                if isvalid(ax)
                    % Only highlight the title, not the axes border
                    originalTitle = ax.Title.String;
                    if ~contains(originalTitle, '★')
                        ax.Title.String = sprintf('★ %s', originalTitle);
                    end
                    ax.Title.Color = app.CurrentHighlightColor;
                    ax.Title.FontWeight = 'bold';
                    % Always keep axes border dark gray
                    ax.XColor = [0.15 0.15 0.15];
                    ax.YColor = [0.15 0.15 0.15];
                    ax.LineWidth = 1;
                end
            end
            % --- NEW: Highlight signals in the tree for this subplot ---
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && ...
               subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                % Find and select nodes in SignalTree matching assigned signals
                allNodes = app.SignalTree.Children;
                selectedNodes = [];
                for i = 1:numel(allNodes)
                    csvNode = allNodes(i);
                    for j = 1:numel(csvNode.Children)
                        sigNode = csvNode.Children(j);
                        isAssigned = false;
                        for k = 1:numel(assigned)
                            if isequal(sigNode.NodeData, assigned{k})
                                isAssigned = true;
                                selectedNodes = [selectedNodes sigNode];
                                break;
                            end
                        end
                        if isAssigned
                            % If isAssigned, prefix sigNode.Text with '✔ ' (if not already present)
                            % Else, remove the prefix if present
                            if ~startsWith(sigNode.Text, '✔ ')
                                sigNode.Text = sprintf('✔ %s', sigNode.Text);
                            end
                        else
                            % If not assigned, remove the prefix if present
                            if startsWith(sigNode.Text, '✔ ')
                                sigNode.Text = strrep(sigNode.Text, '✔ ', '');
                            end
                        end
                    end
                end
                app.SignalTree.SelectedNodes = selectedNodes;
            end
        end

        function clearSubplotHighlights(app, tabIdx)
            % Clear all subplot highlights for a given tab
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
                    ~isempty(app.PlotManager.AxesArrays{tabIdx})

                for i = 1:numel(app.PlotManager.AxesArrays{tabIdx})
                    ax = app.PlotManager.AxesArrays{tabIdx}(i);
                    if isvalid(ax)
                        % Reset to default light mode styling
                        ax.XColor = [0.15 0.15 0.15];     % Dark gray axes
                        ax.YColor = [0.15 0.15 0.15];
                        ax.LineWidth = 1;

                        % Remove star from title
                        originalTitle = ax.Title.String;
                        if contains(originalTitle, '★')
                            ax.Title.String = strrep(originalTitle, '★ ', '');
                            ax.Title.Color = [0.15 0.15 0.15];  % Dark text
                            ax.Title.FontWeight = 'normal';
                        end
                    end
                end
            end
        end

        function addNewTab(app)
            % Add a new tab using the specified layout
            rows = app.RowsSpinner.Value;
            cols = app.ColsSpinner.Value;

            % Add tab through PlotManager
            app.PlotManager.addNewTab(rows, cols);

            % Update UI feedback
            app.StatusLabel.Text = sprintf('🟢 Added new tab with %dx%d layout', rows, cols);
            app.StatusLabel.FontColor = [0.2 0.8 0.4];

            % Update subplot dropdown
            app.updateSubplotDropdown();
        end

        function deleteCurrentTab(app)
            % Delete the current tab
            if numel(app.PlotManager.PlotTabs) <= 1
                app.StatusLabel.Text = '⚠️ Cannot delete the last tab';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Delete tab through PlotManager
            app.PlotManager.deleteCurrentTab();

            % Update UI feedback
            app.StatusLabel.Text = '🗑️ Tab deleted';
            app.StatusLabel.FontColor = [0.9 0.3 0.3];

            % Update subplot dropdown
            app.updateSubplotDropdown();
        end

        function updateCurrentTabLayout(app)
            % Update the layout of the current tab
            rows = app.RowsSpinner.Value;
            cols = app.ColsSpinner.Value;

            % Update layout through PlotManager
            app.PlotManager.changeTabLayout(app.PlotManager.CurrentTabIdx, rows, cols);

            % Update UI feedback
            app.StatusLabel.Text = sprintf('🔄 Updated tab layout to %dx%d', rows, cols);
            app.StatusLabel.FontColor = [0.2 0.9 0.8];

            % Update subplot dropdown
            app.updateSubplotDropdown();
        end

        function onTabSelectionChanged(app)
            % Handle tab selection changes
            selectedTab = app.MainTabGroup.SelectedTab;

            % Find which tab index was selected
            for i = 1:numel(app.PlotManager.PlotTabs)
                if app.PlotManager.PlotTabs{i} == selectedTab
                    app.PlotManager.CurrentTabIdx = i;
                    app.PlotManager.SelectedSubplotIdx = 1;

                    % Update UI to reflect current tab layout
                    if i <= numel(app.PlotManager.TabLayouts)
                        layout = app.PlotManager.TabLayouts{i};
                        app.RowsSpinner.Value = layout(1);
                        app.ColsSpinner.Value = layout(2);
                    end

                    % Update subplot dropdown
                    app.updateSubplotDropdown();

                    % Highlight first subplot
                    app.highlightSelectedSubplot(i, 1);
                    break;
                end
            end
        end

        function updateSubplotDropdown(app)
            % Update the subplot dropdown based on current tab layout
            if app.PlotManager.CurrentTabIdx <= numel(app.PlotManager.TabLayouts)
                layout = app.PlotManager.TabLayouts{app.PlotManager.CurrentTabIdx};
                numPlots = layout(1) * layout(2);

                % Create dropdown items
                items = cell(numPlots, 1);
                for i = 1:numPlots
                    items{i} = sprintf('Plot %d', i);
                end

                app.SubplotDropdown.Items = items;
                app.SubplotDropdown.Value = sprintf('Plot %d', app.PlotManager.SelectedSubplotIdx);
            end
        end

        function initializeVisualEnhancements(app)
            % Initialize subplot highlight system
            app.SubplotHighlightBoxes = {};

            % Set up enhanced visual feedback
            app.setupSubplotHighlighting();
        end

        function setupSubplotHighlighting(app)
            % This will be called when subplots are created to add visual feedback
            % The actual highlighting will be implemented in PlotManager
        end

        % Add a stub for building the signal tree (to be implemented)
        function buildSignalTree(app)
            % Build a tree UI grouped by CSV, with signals as children
            delete(app.SignalTree.Children);
            app.filterSignals(app.SignalSearchField.Value);
            % After building the tree, set up axes drop targets
            app.setupAxesDropTargets();
            % Add per-signal context menu for removal and addition
            allNodes = app.SignalTree.Children;
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            assigned = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end
            for i = 1:numel(allNodes)
                csvNode = allNodes(i);
                for j = 1:numel(csvNode.Children)
                    sigNode = csvNode.Children(j);
                    cm = uicontextmenu(app.UIFigure);
                    % Add 'Remove from Subplot' if assigned
                    isAssigned = false;
                    for k = 1:numel(assigned)
                        if isequal(sigNode.NodeData, assigned{k})
                            isAssigned = true;
                            break;
                        end
                    end
                    if isAssigned
                        uimenu(cm, 'Text', 'Remove from Subplot', 'MenuSelectedFcn', @(src, event) app.removeSignalFromSubplot(sigNode.NodeData));
                    else
                        uimenu(cm, 'Text', 'Add to Subplot', 'MenuSelectedFcn', @(src, event) app.addSignalToSubplot(sigNode.NodeData));
                    end
                    sigNode.ContextMenu = cm;
                end
            end
            % Multi-select context menu for the tree
            multiCm = uicontextmenu(app.UIFigure);
            uimenu(multiCm, 'Text', 'Add all to Subplot', 'MenuSelectedFcn', @(src, event) app.addSelectedSignalsToSubplot());
            uimenu(multiCm, 'Text', 'Remove all from Subplot', 'MenuSelectedFcn', @(src, event) app.removeSelectedSignalsFromSubplot());
            app.SignalTree.ContextMenu = multiCm;
            % Do NOT auto-start streaming here to avoid recursion
        end

        function filterSignals(app, searchText)
            % Filter the signal tree based on search text
            delete(app.SignalTree.Children);
            if isempty(searchText)
                searchText = '';
            end
            for i = 1:numel(app.DataManager.CSVFilePaths)
                [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                csvDisplay = [csvName ext];
                T = app.DataManager.DataTables{i};
                if isempty(T), continue; end
                signals = setdiff(T.Properties.VariableNames, {'Time'});
                % Filter signals by search text
                if ~isempty(searchText)
                    mask = contains(lower(signals), lower(searchText));
                    signals = signals(mask);
                end
                if isempty(signals)
                    continue;
                end
                csvNode = uitreenode(app.SignalTree, 'Text', csvDisplay);
                for j = 1:numel(signals)
                    child = uitreenode(csvNode, 'Text', signals{j});
                    child.NodeData = struct('CSVIdx', i, 'Signal', signals{j});
                end
            end
        end

        function onSignalTreeSelectionChanged(app, event)
            % Callback for when the user selects signals in the tree.
            % Assigns selected signals to the current subplot and updates the properties table.
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                if isfield(selectedNodes(k).NodeData, 'CSVIdx')
                    selectedSignals{end+1} = selectedNodes(k).NodeData; %#ok<AGROW>
                end
            end
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = selectedSignals;
            app.PlotManager.refreshPlots(tabIdx);
            % Update the signal properties table for the selected signals
            app.updateSignalPropsTable(selectedSignals);
        end

        function updateSignalPropsTable(app, selectedSignals)
            % Update the properties table for the selected signals.
            % Each row: {Signal, Scale, State, Color, LineWidth}
            n = numel(selectedSignals);
            data = cell(n, 5);
            for i = 1:n
                sigInfo = selectedSignals{i};
                sigName = sigInfo.Signal;
                % Get scale and state from DataManager
                scale = 1.0;
                if app.DataManager.SignalScaling.isKey(sigName)
                    scale = app.DataManager.SignalScaling(sigName);
                end
                state = false;
                if app.DataManager.StateSignals.isKey(sigName)
                    state = app.DataManager.StateSignals(sigName);
                end
                % Get color and line width from SignalStyles
                color = [0 0.4470 0.7410]; % default MATLAB blue
                width = 2;
                if ~isempty(app.SignalStyles) && isfield(app.SignalStyles, sigName)
                    style = app.SignalStyles.(sigName);
                    if isfield(style, 'Color'), color = style.Color; end
                    if isfield(style, 'LineWidth'), width = style.LineWidth; end
                end
                data{i,1} = sigName;
                data{i,2} = scale;
                data{i,3} = state;
                data{i,4} = mat2str(color); % Store as string
                data{i,5} = width;
            end
            app.SignalPropsTable.Data = data;
            % Set custom cell renderer for color column
            app.SignalPropsTable.CellSelectionCallback = @(src, event) app.onSignalPropsCellSelect(event);
        end

        function onSignalPropsEdit(app, event)
            % Callback for when the user edits scale or state in the properties table.
            % Updates DataManager and re-assigns signals to the current subplot.
            data = app.SignalPropsTable.Data;
            row = event.Indices(1);
            col = event.Indices(2);
            sigName = data{row,1};
            if col == 2 % Scale
                scale = event.NewData;
                if ischar(scale) || isstring(scale)
                    scale = str2double(scale);
                end
                if isnumeric(scale) && isfinite(scale) && scale ~= 0
                    app.DataManager.SignalScaling(sigName) = scale;
                else
                    app.DataManager.SignalScaling(sigName) = 1.0;
                    data{row,2} = 1.0;
                    app.SignalPropsTable.Data = data;
                end
            elseif col == 3 % State
                % Always update state and refresh plot
                app.DataManager.StateSignals(sigName) = logical(event.NewData);
            elseif col == 5 % LineWidth
                width = event.NewData;
                if ischar(width) || isstring(width)
                    width = str2double(width);
                end
                if isnumeric(width) && isfinite(width) && width > 0
                    if isempty(app.SignalStyles), app.SignalStyles = struct(); end
                    if ~isfield(app.SignalStyles, sigName), app.SignalStyles.(sigName) = struct(); end
                    app.SignalStyles.(sigName).LineWidth = width;
                else
                    data{row,5} = 2;
                    app.SignalPropsTable.Data = data;
                end
            end
            drawnow; % Let MATLAB update the table UI
            pause(0.01); % Give a tiny delay for the value to commit
            % Use helper to re-assign signals and refresh plot
            app.assignSelectedSignalsToCurrentSubplot();
            app.PlotManager.refreshPlots();
        end

        function onSignalPropsCellSelect(app, event)
            % Handle color picker for Color column
            if isempty(event.Indices), return; end
            row = event.Indices(1);
            col = event.Indices(2);
            if col == 4 % Color column
                data = app.SignalPropsTable.Data;
                sigName = data{row,1};
                oldColor = str2num(data{row,4}); %#ok<ST2NM>
                if isempty(oldColor), oldColor = [0 0.4470 0.7410]; end
                newColor = uisetcolor(oldColor, sprintf('Pick color for %s', sigName));
                if length(newColor) == 3 % user did not cancel
                    data{row,4} = mat2str(newColor);
                    app.SignalPropsTable.Data = data;
                    if isempty(app.SignalStyles), app.SignalStyles = struct(); end
                    if ~isfield(app.SignalStyles, sigName), app.SignalStyles.(sigName) = struct(); end
                    app.SignalStyles.(sigName).Color = newColor;
                    app.PlotManager.refreshPlots();
                end
            end
        end

        function saveSession(app)
            % Save the current app session to a .mat file
            [file, path] = uiputfile('*.mat', 'Save Session');
            if isequal(file, 0), return; end
            session = struct();
            session.CSVFilePaths = app.DataManager.CSVFilePaths;
            session.SignalScaling = app.DataManager.SignalScaling;
            session.StateSignals = app.DataManager.StateSignals;
            session.AssignedSignals = app.PlotManager.AssignedSignals;
            session.TabLayouts = app.PlotManager.TabLayouts;
            session.CurrentTabIdx = app.PlotManager.CurrentTabIdx;
            session.SelectedSubplotIdx = app.PlotManager.SelectedSubplotIdx;
            session.RowsSpinnerValue = app.RowsSpinner.Value;
            session.ColsSpinnerValue = app.ColsSpinner.Value;
            session.AutoScale = app.AutoScaleCheckbox.Value;
            session.SubplotMetadata = app.SubplotMetadata; % Save metadata
            session.SignalStyles = app.SignalStyles; % Save styles
            save(fullfile(path, file), 'session');
            uialert(app.UIFigure, 'Session saved successfully.', 'Success');
        end

        function loadSession(app)
            % Load a session from a .mat file
            [file, path] = uigetfile('*.mat', 'Load Session');
            if isequal(file, 0), return; end
            loaded = load(fullfile(path, file));
            if ~isfield(loaded, 'session')
                uialert(app.UIFigure, 'Invalid session file.', 'Error');
                return;
            end
            session = loaded.session;
            % Restore CSVs
            app.DataManager.CSVFilePaths = session.CSVFilePaths;
            app.DataManager.DataTables = cell(1, numel(session.CSVFilePaths));
            app.CSVColors = app.assignCSVColors(numel(session.CSVFilePaths));
            for i = 1:numel(session.CSVFilePaths)
                if isfile(session.CSVFilePaths{i})
                    opts = detectImportOptions(session.CSVFilePaths{i});
                    opts = setvartype(opts, 'double');
                    T = readtable(session.CSVFilePaths{i}, opts);
                    if ~ismember('Time', T.Properties.VariableNames)
                        T.Properties.VariableNames{1} = 'Time';
                    end
                    T = sortrows(T, 'Time');
                    app.DataManager.DataTables{i} = T;
                else
                    app.DataManager.DataTables{i} = [];
                end
            end
            app.DataManager.SignalScaling = session.SignalScaling;
            app.DataManager.StateSignals = session.StateSignals;
            app.PlotManager.AssignedSignals = session.AssignedSignals;
            app.PlotManager.TabLayouts = session.TabLayouts;
            app.PlotManager.CurrentTabIdx = session.CurrentTabIdx;
            app.PlotManager.SelectedSubplotIdx = session.SelectedSubplotIdx;
            app.RowsSpinner.Value = session.RowsSpinnerValue;
            app.ColsSpinner.Value = session.ColsSpinnerValue;
            app.AutoScaleCheckbox.Value = session.AutoScale;
            app.SubplotMetadata = session.SubplotMetadata; % Load metadata
            app.SignalStyles = session.SignalStyles; % Load styles
            app.buildSignalTree();
            app.PlotManager.refreshPlots();
            uialert(app.UIFigure, 'Session loaded successfully.', 'Success');
        end

        function delete(app)
            % Delete app
            delete(app.UIFigure);
        end
    end

    % Helper function to assign selected signals in the tree to the current subplot
    methods (Access = private)
        function assignSelectedSignalsToCurrentSubplot(app)
            % Assign all signals currently selected in the tree to the current subplot
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                if isfield(selectedNodes(k).NodeData, 'CSVIdx')
                    selectedSignals{end+1} = selectedNodes(k).NodeData; %#ok<AGROW>
                end
            end
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = selectedSignals;
        end

        function pushAssignmentHistory(app)
            % Push current assignment to undo stack
            if isempty(app.AssignmentUndoStack)
                app.AssignmentUndoStack = {};
            end
            app.AssignmentUndoStack{end+1} = app.deepCopyAssignments(app.PlotManager.AssignedSignals);
            % Clear redo stack
            app.AssignmentRedoStack = {};
        end

        function undoAssignment(app)
            if isempty(app.AssignmentUndoStack) || numel(app.AssignmentUndoStack) < 2
                return;
            end
            % Pop current state to redo stack
            if isempty(app.AssignmentRedoStack)
                app.AssignmentRedoStack = {};
            end
            app.AssignmentRedoStack{end+1} = app.deepCopyAssignments(app.PlotManager.AssignedSignals);
            % Pop previous state from undo stack
            app.AssignmentUndoStack(end) = [];
            prev = app.AssignmentUndoStack{end};
            app.PlotManager.AssignedSignals = app.deepCopyAssignments(prev);
            app.PlotManager.refreshPlots();
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, app.PlotManager.SelectedSubplotIdx);
            app.updateSignalPropsTable(app.PlotManager.AssignedSignals{app.PlotManager.CurrentTabIdx}{app.PlotManager.SelectedSubplotIdx});
        end

        function redoAssignment(app)
            if isempty(app.AssignmentRedoStack)
                return;
            end
            % Push current state to undo stack
            app.AssignmentUndoStack{end+1} = app.deepCopyAssignments(app.PlotManager.AssignedSignals);
            % Pop from redo stack
            next = app.AssignmentRedoStack{end};
            app.AssignmentRedoStack(end) = [];
            app.PlotManager.AssignedSignals = app.deepCopyAssignments(next);
            app.PlotManager.refreshPlots();
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, app.PlotManager.SelectedSubplotIdx);
            app.updateSignalPropsTable(app.PlotManager.AssignedSignals{app.PlotManager.CurrentTabIdx}{app.PlotManager.SelectedSubplotIdx});
        end

        function out = deepCopyAssignments(app, in)
            % Deep copy cell array of assignments
            out = cell(size(in));
            for i = 1:numel(in)
                if iscell(in{i})
                    out{i} = in{i};
                    for j = 1:numel(in{i})
                        if iscell(in{i}{j})
                            out{i}{j} = in{i}{j};
                        else
                            out{i}{j} = in{i}{j};
                        end
                    end
                else
                    out{i} = in{i};
                end
            end
        end

        function menuStart(app)
            app.UIController.loadMultipleCSVs();
        end
        function menuStop(app)
            app.DataManager.stopStreamingAll();
        end
        function menuClear(app)
            app.UIController.clearAll();
        end
        function menuExportCSV(app)
            app.UIController.exportCSV();
        end
        function menuExportPDF(app)
            app.PlotManager.exportToPDF();
        end
        function menuStatistics(app)
            app.UIController.showStatsDialog();
        end
        function menuResetZoom(app)
            app.PlotManager.resetZoom();
        end
        function menuToggleSyncZoom(app)
            % Toggle sync zoom state
            if ~isprop(app, 'SyncZoomState') || isempty(app.SyncZoomState)
                app.SyncZoomState = false;
            end
            app.SyncZoomState = ~app.SyncZoomState;
            if app.SyncZoomState
                app.PlotManager.enableSyncZoom();
            else
                app.PlotManager.disableSyncZoom();
            end
        end
        function menuToggleCursor(app)
            % Toggle cursor mode state
            if ~isprop(app, 'CursorState') || isempty(app.CursorState)
                app.CursorState = false;
            end
            app.CursorState = ~app.CursorState;
            if app.CursorState
                app.PlotManager.enableCursorMode();
            else
                app.PlotManager.disableCursorMode();
            end
        end

        function setupAxesDropTargets(app)
            % Set up each axes as a drop target for drag-and-drop signal assignment
            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                axesArr = app.PlotManager.AxesArrays{tabIdx};
                for subplotIdx = 1:numel(axesArr)
                    ax = axesArr(subplotIdx);
                    try
                        ax.DropEnabled = 'on';
                        ax.DropFcn = @(src, event) app.onAxesDrop(tabIdx, subplotIdx, event);
                    end
                end
            end
        end

        function onAxesDrop(app, tabIdx, subplotIdx, event)
            % Handle drop event: assign the dragged signal to the target subplot
            if isempty(event.Data)
                return;
            end
            node = event.Data;
            if isfield(node.NodeData, 'CSVIdx')
                sigInfo = node.NodeData;
                % Add (not replace) the signal to the subplot assignment
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                % Only add if not already present
                alreadyAssigned = false;
                for k = 1:numel(assigned)
                    if isequal(assigned{k}, sigInfo)
                        alreadyAssigned = true;
                        break;
                    end
                end
                if ~alreadyAssigned
                    assigned{end+1} = sigInfo;
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = assigned;
                end
                app.PlotManager.refreshPlots(tabIdx);
                % Update the properties table for this subplot
                app.updateSignalPropsTable(app.PlotManager.AssignedSignals{tabIdx}{subplotIdx});
                % Update tree highlighting
                app.highlightSelectedSubplot(tabIdx, subplotIdx);
            end
        end

        function colors = assignCSVColors(app, n)
            % Assign a unique color to each CSV from a palette
            palette = [ ...
                0.2 0.6 0.9;    % Blue
                0.9 0.3 0.3;    % Red
                0.3 0.8 0.4;    % Green
                0.9 0.6 0.2;    % Orange
                0.7 0.3 0.9;    % Purple
                0.2 0.9 0.8;    % Cyan
                0.9 0.8 0.2;    % Yellow
                0.9 0.4 0.7;    % Pink
                0.5 0.5 0.5;    % Gray
                0.1 0.1 0.9;    % Dark Blue
            ];
            colors = cell(1, n);
            for i = 1:n
                colors{i} = palette(mod(i-1, size(palette,1)) + 1, :);
            end
        end

        function clearAllSignalsFromSubplot(app)
            app.pushAssignmentHistory();
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = {};
                app.PlotManager.refreshPlots(tabIdx);
                % Update tree highlighting
                app.highlightSelectedSubplot(tabIdx, subplotIdx);
                % Optionally clear the signal properties table
                app.SignalPropsTable.Data = {};
            end
        end

        function removeSignalFromSubplot(app, sigInfo)
            app.pushAssignmentHistory();
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                % Remove the signal matching sigInfo
                keep = true(1, numel(assigned));
                for k = 1:numel(assigned)
                    if isequal(assigned{k}, sigInfo)
                        keep(k) = false;
                    end
                end
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = assigned(keep);
                app.PlotManager.refreshPlots(tabIdx);
                app.highlightSelectedSubplot(tabIdx, subplotIdx);
                % Update the signal properties table
                app.updateSignalPropsTable(app.PlotManager.AssignedSignals{tabIdx}{subplotIdx});
            end
        end

        function addSignalToSubplot(app, sigInfo)
            app.pushAssignmentHistory();
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                % Only add if not already present
                alreadyAssigned = false;
                for k = 1:numel(assigned)
                    if isequal(assigned{k}, sigInfo)
                        alreadyAssigned = true;
                        break;
                    end
                end
                if ~alreadyAssigned
                    assigned{end+1} = sigInfo;
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = assigned;
                    app.PlotManager.refreshPlots(tabIdx);
                    app.highlightSelectedSubplot(tabIdx, subplotIdx);
                    app.updateSignalPropsTable(assigned);
                end
            end
        end

        function addSelectedSignalsToSubplot(app)
            app.pushAssignmentHistory();
            selectedNodes = app.SignalTree.SelectedNodes;
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                for k = 1:numel(selectedNodes)
                    sigInfo = selectedNodes(k).NodeData;
                    alreadyAssigned = false;
                    for m = 1:numel(assigned)
                        if isequal(assigned{m}, sigInfo)
                            alreadyAssigned = true;
                            break;
                        end
                    end
                    if ~alreadyAssigned
                        assigned{end+1} = sigInfo;
                    end
                end
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = assigned;
                app.PlotManager.refreshPlots(tabIdx);
                app.highlightSelectedSubplot(tabIdx, subplotIdx);
                app.updateSignalPropsTable(assigned);
            end
        end

        function removeSelectedSignalsFromSubplot(app)
            app.pushAssignmentHistory();
            selectedNodes = app.SignalTree.SelectedNodes;
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                keep = true(1, numel(assigned));
                for k = 1:numel(assigned)
                    for m = 1:numel(selectedNodes)
                        if isequal(assigned{k}, selectedNodes(m).NodeData)
                            keep(k) = false;
                        end
                    end
                end
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = assigned(keep);
                app.PlotManager.refreshPlots(tabIdx);
                app.highlightSelectedSubplot(tabIdx, subplotIdx);
                app.updateSignalPropsTable(app.PlotManager.AssignedSignals{tabIdx}{subplotIdx});
            end
        end

        function saveTemplate(app)
            [file, path] = uiputfile('*.mat', 'Save Plot/Tab Template');
            if isequal(file, 0), return; end
            template = struct();
            template.TabLayouts = app.PlotManager.TabLayouts;
            template.AssignedSignals = app.PlotManager.AssignedSignals;
            % Save custom plot styles per subplot
            template.PlotStyles = cell(size(app.PlotManager.AxesArrays));
            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                axesArr = app.PlotManager.AxesArrays{tabIdx};
                template.PlotStyles{tabIdx} = cell(size(axesArr));
                for subplotIdx = 1:numel(axesArr)
                    ax = axesArr(subplotIdx);
                    if isvalid(ax)
                        style = struct();
                        style.XLim = ax.XLim;
                        style.YLim = ax.YLim;
                        style.Color = ax.Color;
                        style.Grid = strcmp(ax.XGrid, 'on');
                        template.PlotStyles{tabIdx}{subplotIdx} = style;
                    end
                end
            end
            % Save subplot metadata
            if isempty(app.SubplotMetadata)
                template.SubplotMetadata = {};
            else
                template.SubplotMetadata = app.SubplotMetadata;
            end
            template.SignalStyles = app.SignalStyles; % Save styles
            save(fullfile(path, file), 'template');
            uialert(app.UIFigure, 'Template saved successfully.', 'Success');
        end

        function loadTemplate(app)
            [file, path] = uigetfile('*.mat', 'Load Plot/Tab Template');
            if isequal(file, 0), return; end
            loaded = load(fullfile(path, file));
            if ~isfield(loaded, 'template')
                uialert(app.UIFigure, 'Invalid template file.', 'Error');
                return;
            end
            template = loaded.template;
            % Apply layouts
            app.PlotManager.TabLayouts = template.TabLayouts;
            % Rebuild tabs and subplots
            while numel(app.PlotManager.PlotTabs) > 1
                app.PlotManager.deleteCurrentTab();
            end
            if ~isempty(app.PlotManager.TabLayouts{1})
                app.PlotManager.createSubplotsForTab(1, app.PlotManager.TabLayouts{1}(1), app.PlotManager.TabLayouts{1}(2));
            end
            for i = 2:numel(app.PlotManager.TabLayouts)
                if ~isempty(app.PlotManager.TabLayouts{i})
                    app.PlotManager.addNewTab(app.PlotManager.TabLayouts{i}(1), app.PlotManager.TabLayouts{i}(2));
                end
            end
            % Assign signals by matching names
            assigned = template.AssignedSignals;
            for tabIdx = 1:min(numel(app.PlotManager.AssignedSignals), numel(assigned))
                for subplotIdx = 1:min(numel(app.PlotManager.AssignedSignals{tabIdx}), numel(assigned{tabIdx}))
                    newAssigned = {};
                    for k = 1:numel(assigned{tabIdx}{subplotIdx})
                        sigInfo = assigned{tabIdx}{subplotIdx}{k};
                        % Only assign if signal exists in current CSVs
                        csvIdx = sigInfo.CSVIdx;
                        sigName = sigInfo.Signal;
                        if csvIdx <= numel(app.DataManager.DataTables) && ...
                           ~isempty(app.DataManager.DataTables{csvIdx}) && ...
                           ismember(sigName, app.DataManager.DataTables{csvIdx}.Properties.VariableNames)
                            newAssigned{end+1} = sigInfo;
                        end
                    end
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssigned;
                end
            end
            % Restore custom plot styles if present
            if isfield(template, 'PlotStyles')
                for tabIdx = 1:min(numel(app.PlotManager.AxesArrays), numel(template.PlotStyles))
                    axesArr = app.PlotManager.AxesArrays{tabIdx};
                    for subplotIdx = 1:min(numel(axesArr), numel(template.PlotStyles{tabIdx}))
                        ax = axesArr(subplotIdx);
                        style = template.PlotStyles{tabIdx}{subplotIdx};
                        if isvalid(ax) && ~isempty(style)
                            try
                                ax.XLim = style.XLim;
                                ax.YLim = style.YLim;
                                ax.Color = style.Color;
                                if style.Grid
                                    grid(ax, 'on');
                                else
                                    grid(ax, 'off');
                                end
                            end
                        end
                    end
                end
            end
            % Restore subplot metadata if present
            if isfield(template, 'SubplotMetadata')
                app.SubplotMetadata = template.SubplotMetadata;
            else
                app.SubplotMetadata = {};
            end
            app.SignalStyles = template.SignalStyles; % Load styles
            app.PlotManager.refreshPlots();
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, app.PlotManager.SelectedSubplotIdx);
            uialert(app.UIFigure, 'Template loaded and applied.', 'Success');
        end

        function manageTemplates(app)
            % Directory for templates (can be customized)
            templateDir = pwd;
            files = dir(fullfile(templateDir, '*.mat'));
            % Create dialog
            d = dialog('Name', 'Manage Templates', 'Position', [400 300 500 350]);
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 320 200 20], 'String', 'Templates in folder:', 'HorizontalAlignment', 'left');
            listbox = uicontrol('Parent', d, 'Style', 'listbox', 'Position', [20 60 200 260], 'String', {files.name}, 'Max', 1, 'Min', 0);
            infoBox = uicontrol('Parent', d, 'Style', 'edit', 'Position', [230 60 250 260], 'Max', 2, 'Enable', 'inactive', 'HorizontalAlignment', 'left');
            % Action buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Load', 'Position', [20 20 60 25], 'Callback', @(~,~) loadSelected());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Rename', 'Position', [90 20 60 25], 'Callback', @(~,~) renameSelected());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Delete', 'Position', [160 20 60 25], 'Callback', @(~,~) deleteSelected());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Duplicate', 'Position', [230 20 70 25], 'Callback', @(~,~) duplicateSelected());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', 'Position', [420 20 60 25], 'Callback', @(~,~) close(d));
            % Update info on selection
            listbox.Callback = @(src,~) updateInfo();
            updateInfo();
            function updateInfo()
                idx = listbox.Value;
                if isempty(idx) || idx < 1 || idx > numel(files)
                    infoBox.String = '';
                    return;
                end
                f = files(idx);
                try
                    loaded = load(fullfile(templateDir, f.name));
                    if isfield(loaded, 'template')
                        t = loaded.template;
                        nTabs = numel(t.TabLayouts);
                        nSubplots = sum(cellfun(@(x) prod(x), t.TabLayouts));
                        nSignals = 0;
                        if isfield(t, 'AssignedSignals')
                            for i = 1:numel(t.AssignedSignals)
                                for j = 1:numel(t.AssignedSignals{i})
                                    nSignals = nSignals + numel(t.AssignedSignals{i}{j});
                                end
                            end
                        end
                        notes = '';
                        if isfield(t, 'SubplotMetadata') && ~isempty(t.SubplotMetadata)
                            for i = 1:numel(t.SubplotMetadata)
                                for j = 1:numel(t.SubplotMetadata{i})
                                    meta = t.SubplotMetadata{i}{j};
                                    if isfield(meta, 'Notes') && ~isempty(meta.Notes)
                                        notes = [notes sprintf('Tab %d Plot %d: %s\n', i, j, meta.Notes)];
                                    end
                                end
                            end
                        end
                        infoBox.String = sprintf('Tabs: %d\nSubplots: %d\nSignals assigned: %d\nNotes:\n%s', nTabs, nSubplots, nSignals, notes);
                    else
                        infoBox.String = 'Not a valid template file.';
                    end
                catch ME
                    infoBox.String = ['Error reading file: ' ME.message];
                end
            end
            function loadSelected()
                idx = listbox.Value;
                if isempty(idx) || idx < 1 || idx > numel(files)
                    return;
                end
                close(d);
                app.loadTemplateFromFile(fullfile(templateDir, files(idx).name));
            end
            function renameSelected()
                idx = listbox.Value;
                if isempty(idx) || idx < 1 || idx > numel(files)
                    return;
                end
                oldName = files(idx).name;
                answer = inputdlg('Enter new template name (with .mat):', 'Rename Template', 1, {oldName});
                if isempty(answer), return; end
                newName = answer{1};
                if exist(fullfile(templateDir, newName), 'file')
                    uialert(d, 'File already exists.', 'Error');
                    return;
                end
                movefile(fullfile(templateDir, oldName), fullfile(templateDir, newName));
                files = dir(fullfile(templateDir, '*.mat'));
                listbox.String = {files.name};
                updateInfo();
            end
            function deleteSelected()
                idx = listbox.Value;
                if isempty(idx) || idx < 1 || idx > numel(files)
                    return;
                end
                fname = files(idx).name;
                choice = questdlg(['Delete template ' fname '?'], 'Delete', 'Yes', 'No', 'No');
                if strcmp(choice, 'Yes')
                    delete(fullfile(templateDir, fname));
                    files = dir(fullfile(templateDir, '*.mat'));
                    listbox.String = {files.name};
                    updateInfo();
                end
            end
            function duplicateSelected()
                idx = listbox.Value;
                if isempty(idx) || idx < 1 || idx > numel(files)
                    return;
                end
                oldName = files(idx).name;
                [~, base, ext] = fileparts(oldName);
                newName = [base '_copy' ext];
                i = 1;
                while exist(fullfile(templateDir, newName), 'file')
                    newName = sprintf('%s_copy%d%s', base, i, ext);
                    i = i + 1;
                end
                copyfile(fullfile(templateDir, oldName), fullfile(templateDir, newName));
                files = dir(fullfile(templateDir, '*.mat'));
                listbox.String = {files.name};
                updateInfo();
            end
        end
        function loadTemplateFromFile(app, filePath)
            loaded = load(filePath);
            if ~isfield(loaded, 'template')
                uialert(app.UIFigure, 'Invalid template file.', 'Error');
                return;
            end
            template = loaded.template;
            % Apply layouts
            app.PlotManager.TabLayouts = template.TabLayouts;
            % Rebuild tabs and subplots
            while numel(app.PlotManager.PlotTabs) > 1
                app.PlotManager.deleteCurrentTab();
            end
            if ~isempty(app.PlotManager.TabLayouts{1})
                app.PlotManager.createSubplotsForTab(1, app.PlotManager.TabLayouts{1}(1), app.PlotManager.TabLayouts{1}(2));
            end
            for i = 2:numel(app.PlotManager.TabLayouts)
                if ~isempty(app.PlotManager.TabLayouts{i})
                    app.PlotManager.addNewTab(app.PlotManager.TabLayouts{i}(1), app.PlotManager.TabLayouts{i}(2));
                end
            end
            % Assign signals by matching names
            assigned = template.AssignedSignals;
            for tabIdx = 1:min(numel(app.PlotManager.AssignedSignals), numel(assigned))
                for subplotIdx = 1:min(numel(app.PlotManager.AssignedSignals{tabIdx}), numel(assigned{tabIdx}))
                    newAssigned = {};
                    for k = 1:numel(assigned{tabIdx}{subplotIdx})
                        sigInfo = assigned{tabIdx}{subplotIdx}{k};
                        % Only assign if signal exists in current CSVs
                        csvIdx = sigInfo.CSVIdx;
                        sigName = sigInfo.Signal;
                        if csvIdx <= numel(app.DataManager.DataTables) && ...
                           ~isempty(app.DataManager.DataTables{csvIdx}) && ...
                           ismember(sigName, app.DataManager.DataTables{csvIdx}.Properties.VariableNames)
                            newAssigned{end+1} = sigInfo;
                        end
                    end
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssigned;
                end
            end
            % Restore custom plot styles if present
            if isfield(template, 'PlotStyles')
                for tabIdx = 1:min(numel(app.PlotManager.AxesArrays), numel(template.PlotStyles))
                    axesArr = app.PlotManager.AxesArrays{tabIdx};
                    for subplotIdx = 1:min(numel(axesArr), numel(template.PlotStyles{tabIdx}))
                        ax = axesArr(subplotIdx);
                        style = template.PlotStyles{tabIdx}{subplotIdx};
                        if isvalid(ax) && ~isempty(style)
                            try
                                ax.XLim = style.XLim;
                                ax.YLim = style.YLim;
                                ax.Color = style.Color;
                                if style.Grid
                                    grid(ax, 'on');
                                else
                                    grid(ax, 'off');
                                end
                            end
                        end
                    end
                end
            end
            % Restore subplot metadata if present
            if isfield(template, 'SubplotMetadata')
                app.SubplotMetadata = template.SubplotMetadata;
            else
                app.SubplotMetadata = {};
            end
            app.SignalStyles = template.SignalStyles; % Load styles
            app.PlotManager.refreshPlots();
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, app.PlotManager.SelectedSubplotIdx);
            uialert(app.UIFigure, 'Template loaded and applied.', 'Success');
        end

        function refreshCSVs(app)
            n = numel(app.DataManager.CSVFilePaths);
            for idx = 1:n
                app.DataManager.readInitialData(idx);
            end
            app.buildSignalTree();
            app.PlotManager.refreshPlots();
            % Do NOT auto-start streaming here to avoid recursion
        end
    end
end