% Updated SignalViewerApp.m - Main changes for light mode and streaming - REMOVED REDUNDANT DRAWNOW
classdef SignalViewerApp < matlab.apps.AppBase
    properties
        % Main UI
        UIFigure
        ControlPanel
        MainTabGroup
        SignalOperations
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
        CursorState = false

        % Visual Enhancement Properties
        SubplotHighlightBoxes
        CurrentHighlightColor = [0.2 0.8 0.4]  % Green highlight color


        PDFReportTitle = 'Signal Analysis Report'
        PDFReportAuthor = ''
        PDFReportDate = datetime('now')
        PDFFigureLabel = 'Figure'      % ADD THIS LINE
        SubplotCaptions = {}
        SubplotDescriptions = {}
        SubplotTitles = {}
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
        AutoScaleButton
        PDFReportLanguage = 'English'  % או 'Hebrew'
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
            app.SignalOperations = SignalOperationsManager(app);
            app.UIController  = UIController(app);

            %=== Connect Callbacks ===%
            app.UIController.setupCallbacks();
            %=== Initialize visual enhancements ===%
            app.initializeVisualEnhancements();
        end

        function createEnhancedComponents(app)
            % Enhanced layout with LIGHT MODE styling
            % Only keep controls that are actually used in the current workflow

            fileMenu = uimenu(app.UIFigure, 'Text', 'File');
            uimenu(fileMenu, 'Text', '💾 Save Layout Config', 'MenuSelectedFcn', @(src, event) app.saveConfig());
            uimenu(fileMenu, 'Text', '📁 Load Layout Config', 'MenuSelectedFcn', @(src, event) app.loadConfig());
            uimenu(fileMenu, 'Text', '💾 Save Full Session', 'MenuSelectedFcn', @(src, event) app.saveSession());
            uimenu(fileMenu, 'Text', '📁 Load Full Session', 'MenuSelectedFcn', @(src, event) app.loadSession());

            % Update the actions menu in createEnhancedComponents method:
            actionsMenu = uimenu(app.UIFigure, 'Text', 'Actions');
            uimenu(actionsMenu, 'Text', '▶️ Start (Load CSVs)', 'MenuSelectedFcn', @(src, event) app.menuStart());
            uimenu(actionsMenu, 'Text', '➕ Add More CSVs', 'MenuSelectedFcn', @(src, event) app.menuAddMoreCSVs());
            uimenu(actionsMenu, 'Text', '⏹️ Stop', 'MenuSelectedFcn', @(src, event) app.menuStop());
            uimenu(actionsMenu, 'Text', '🗑️ Clear Plots Only', 'MenuSelectedFcn', @(src, event) app.menuClearPlotsOnly());
            uimenu(actionsMenu, 'Text', '🗑️ Clear Everything', 'MenuSelectedFcn', @(src, event) app.menuClearAll());
            uimenu(actionsMenu, 'Text', '📈 Statistics', 'MenuSelectedFcn', @(src, event) app.menuStatistics());

            % SIGNAL OPERATIONS MENU - Main menu item (not submenu)
            operationsMenu = uimenu(app.UIFigure, 'Text', 'Operations');

            % Single Signal Operations
            singleSubMenu = uimenu(operationsMenu, 'Text', '🔢 Single Signal');
            uimenu(singleSubMenu, 'Text', '∂ Derivative', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showSingleSignalDialog('derivative'));
            uimenu(singleSubMenu, 'Text', '∫ Integral', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showSingleSignalDialog('integral'));

            % Multi Signal Operations
            multiSubMenu = uimenu(operationsMenu, 'Text', '📈 Multi Signal');
            uimenu(multiSubMenu, 'Text', '− Subtract (A - B)', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialog('subtract'));
            uimenu(multiSubMenu, 'Text', '+ Add (A + B)', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialog('add'));
            uimenu(multiSubMenu, 'Text', '× Multiply (A × B)', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialog('multiply'));
            uimenu(multiSubMenu, 'Text', '÷ Divide (A ÷ B)', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialog('divide'));
            uimenu(multiSubMenu, 'Text', '‖‖ Norm of Signals', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showNormDialog());

            % Custom Code
            uimenu(operationsMenu, 'Text', '💻 Custom MATLAB Code', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showCustomCodeDialog(), 'Separator', 'on');

            % Management
            managementSubMenu = uimenu(operationsMenu, 'Text', '⚙️ Management');
            uimenu(managementSubMenu, 'Text', '📋 Operation History', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showOperationHistory());
            uimenu(managementSubMenu, 'Text', '🗑️ Clear All Derived Signals', 'MenuSelectedFcn', @(src, event) app.confirmAndClearDerivedSignals());
            exportMenu = uimenu(app.UIFigure, 'Text', 'Export');
            uimenu(exportMenu, 'Text', '📊 Export CSV', 'MenuSelectedFcn', @(src, event) app.menuExportCSV());
            uimenu(exportMenu, 'Text', '📄 Export PDF', 'MenuSelectedFcn', @(src, event) app.menuExportPDF());


            % ONLY Auto Scale and Refresh CSV buttons at the top
            app.AutoScaleButton = uibutton(app.ControlPanel, 'push', 'Text', 'Auto Scale All', ...
                'Position', [20 740 120 30], ...
                'ButtonPushedFcn', @(src, event) app.autoScaleCurrentSubplot(), ...
                'Tooltip', 'Auto-scale all subplots in current tab to fit data', ...
                'FontSize', 11, 'FontWeight', 'bold');

            app.RefreshCSVsButton = uibutton(app.ControlPanel, 'push', 'Text', 'Refresh CSVs', ...
                'Position', [150 740 120 30], ...
                'ButtonPushedFcn', @(src, event) app.refreshCSVs(), ...
                'FontSize', 11, 'FontWeight', 'bold');

            % Search box for signals - moved up and made wider
            app.SignalSearchField = uieditfield(app.ControlPanel, 'text', ...
                'Position', [20 710 280 25], ...
                'Placeholder', 'Search signals...', ...
                'ValueChangingFcn', @(src, event) app.filterSignals(event.Value), ...
                'FontSize', 11);

            % LARGE Signal selection tree - takes up most of the panel
            app.SignalTree = uitree(app.ControlPanel, ...
                'Position', [20 200 280 500], ... % Much larger: 500px height instead of 200px
                'SelectionChangedFcn', @(src, event) app.onSignalTreeSelectionChanged(), ...
                'FontSize', 11);
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

            % LARGER Table for editing scale and state for selected signals
            app.SignalPropsTable = uitable(app.ControlPanel, ...
                'Position', [20 80 280 110], ... % Increased height from 100 to 110
                'ColumnName', {'Signal', 'Scale', 'State', 'Color', 'LineWidth'}, ...
                'ColumnEditable', [false true true false true], ... % Color not editable by typing
                'CellEditCallback', @(src, event) app.onSignalPropsEdit(event), ...
                'FontSize', 10);

            % Status labels at the very top
            app.StatusLabel = uilabel(app.ControlPanel, ...
                'Position', [20 25 280 15], ... % Smaller and at very top
                'Text', 'Ready', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 10, ...
                'FontWeight', 'bold');

            app.DataRateLabel = uilabel(app.ControlPanel, ...
                'Position', [20 55 140 15], ... % Moved to bottom left
                'Text', 'Data Rate: 0 Hz', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 9);

            % StreamingInfoLabel at bottom right
            app.StreamingInfoLabel = uilabel(app.ControlPanel, ...
                'Position', [160 65 140 15], ... % Bottom right
                'Text', '', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 9);
        end


        function confirmAndClearDerivedSignals(app)
            % Confirm before clearing all derived signals
            if isempty(app.SignalOperations.DerivedSignals)
                uialert(app.UIFigure, 'No derived signals to clear.', 'No Derived Signals');
                return;
            end

            numDerived = length(keys(app.SignalOperations.DerivedSignals));
            answer = uiconfirm(app.UIFigure, ...
                sprintf('Clear all %d derived signals?', numDerived), ...
                'Confirm Clear', 'Options', {'Clear All', 'Cancel'}, ...
                'DefaultOption', 'Cancel', 'Icon', 'warning');

            if strcmp(answer, 'Clear All')
                app.SignalOperations.clearAllDerivedSignals();
                app.StatusLabel.Text = sprintf('🗑️ Cleared %d derived signals', numDerived);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end
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
            % Highlight the currently selected subplot with only an outer border
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
                    ~isempty(app.PlotManager.AxesArrays{tabIdx}) && ...
                    subplotIdx <= numel(app.PlotManager.AxesArrays{tabIdx})

                % FORCE clear ALL highlights in this tab first
                for i = 1:numel(app.PlotManager.AxesArrays{tabIdx})
                    ax = app.PlotManager.AxesArrays{tabIdx}(i);
                    if isvalid(ax)
                        % Reset to normal styling
                        ax.XColor = [0.15 0.15 0.15];
                        ax.YColor = [0.15 0.15 0.15];
                        ax.LineWidth = 1;
                        ax.Box = 'on';

                        % Remove any existing highlight borders
                        if isstruct(ax.UserData) && isfield(ax.UserData, 'HighlightBorders')
                            borders = ax.UserData.HighlightBorders;
                            for j = 1:numel(borders)
                                if isvalid(borders(j))
                                    delete(borders(j));
                                end
                            end
                            ax.UserData = rmfield(ax.UserData, 'HighlightBorders');
                        end

                        % Also remove any plot objects that might be highlight borders
                        % (in case UserData tracking failed)
                        children = get(ax, 'Children');
                        for j = 1:numel(children)
                            child = children(j);
                            if isa(child, 'matlab.graphics.chart.primitive.Line') && ...
                                    child.LineWidth == 6 && ...
                                    isequal(child.Color, app.CurrentHighlightColor)
                                delete(child);
                            end
                        end
                    end
                end

                % NOW add border to ONLY the selected subplot
                ax = app.PlotManager.AxesArrays{tabIdx}(subplotIdx);
                if isvalid(ax)
                    % Add a border using plot lines
                    hold(ax, 'on');

                    % Get current axis limits
                    xlims = ax.XLim;
                    ylims = ax.YLim;

                    % Create border lines around the perimeter
                    topBorder = plot(ax, xlims, [ylims(2) ylims(2)], ...
                        'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
                        'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');

                    bottomBorder = plot(ax, xlims, [ylims(1) ylims(1)], ...
                        'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
                        'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');

                    leftBorder = plot(ax, [xlims(1) xlims(1)], ylims, ...
                        'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
                        'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');

                    rightBorder = plot(ax, [xlims(2) xlims(2)], ylims, ...
                        'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
                        'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');

                    hold(ax, 'off');

                    % Store the borders for later removal
                    if ~isstruct(ax.UserData)
                        ax.UserData = struct();
                    end
                    ax.UserData.HighlightBorders = [topBorder, bottomBorder, leftBorder, rightBorder];
                end
            end

            % Update signal tree to reflect current tab/subplot assignments
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && ...
                    subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assigned = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                % Update visual indicators and selection in signal tree
                app.PlotManager.updateSignalTreeVisualIndicators(assigned);

                % Update signal properties table
                app.updateSignalPropsTable(assigned);
            end
        end

        function clearAllSignalsFromSubplot(app)
            % Clear all signals from a specific folder (CSV or Derived) from ALL subplots

            % Get currently selected node
            selectedNodes = app.SignalTree.SelectedNodes;
            if isempty(selectedNodes)
                uialert(app.UIFigure, 'Please select a CSV folder or Derived Signals folder first.', 'No Selection');
                return;
            end

            selectedNode = selectedNodes(1);

            % Determine what type of clearing to do based on selected node
            if contains(selectedNode.Text, 'CSV') || contains(selectedNode.Text, '.csv')
                % CSV folder selected - clear all signals from this CSV
                app.clearSignalsFromCSVFolder(selectedNode);

            elseif contains(selectedNode.Text, 'Derived Signals')
                % Derived Signals folder selected - clear all derived signals
                app.clearAllDerivedSignalsFromSubplots();

            else
                % Individual signal selected - clear just this signal from all subplots
                if isfield(selectedNode.NodeData, 'Signal')
                    app.clearSpecificSignalFromAllSubplots(selectedNode.NodeData);
                else
                    uialert(app.UIFigure, 'Please select a CSV folder, Derived Signals folder, or specific signal.', 'Invalid Selection');
                end
            end
        end

        function clearSignalsFromCSVFolder(app, csvNode)
            % Clear all signals from a specific CSV from all subplots

            % Extract CSV index from node
            csvIndex = app.getCSVIndexFromNode(csvNode);
            if csvIndex == -1
                uialert(app.UIFigure, 'Could not determine CSV index.', 'Error');
                return;
            end

            % Get all signals from this CSV
            if csvIndex <= numel(app.DataManager.DataTables) && ~isempty(app.DataManager.DataTables{csvIndex})
                T = app.DataManager.DataTables{csvIndex};
                csvSignals = setdiff(T.Properties.VariableNames, {'Time'});
            else
                csvSignals = {};
            end

            if isempty(csvSignals)
                uialert(app.UIFigure, 'No signals found in selected CSV.', 'No Signals');
                return;
            end

            % Confirm action
            answer = uiconfirm(app.UIFigure, ...
                sprintf('Remove all signals from "%s" from ALL subplots in ALL tabs?\n\nSignals to remove: %s', ...
                csvNode.Text, strjoin(csvSignals, ', ')), ...
                'Confirm Clear CSV Signals', ...
                'Options', {'Remove All', 'Cancel'}, ...
                'DefaultOption', 'Cancel', 'Icon', 'warning');

            if strcmp(answer, 'Cancel')
                return;
            end

            % FIXED: Remove signals from ALL subplots in ALL tabs
            removedCount = 0;

            % Make sure AssignedSignals structure exists for all tabs
            numTabs = numel(app.PlotManager.AxesArrays);

            for tabIdx = 1:numTabs
                % Ensure this tab exists in AssignedSignals
                if tabIdx > numel(app.PlotManager.AssignedSignals)
                    continue; % Skip if tab doesn't have assignments yet
                end

                % Get number of subplots in this tab
                if ~isempty(app.PlotManager.AxesArrays{tabIdx})
                    numSubplots = numel(app.PlotManager.AxesArrays{tabIdx});
                else
                    continue; % Skip if no subplots
                end

                % Process each subplot in this tab
                for subplotIdx = 1:numSubplots
                    % Ensure this subplot exists in AssignedSignals
                    if subplotIdx > numel(app.PlotManager.AssignedSignals{tabIdx})
                        continue; % Skip if subplot doesn't have assignments yet
                    end

                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                    if isempty(assignedSignals)
                        continue; % Skip empty subplots
                    end

                    % Filter out signals from this CSV
                    filteredSignals = {};
                    for i = 1:numel(assignedSignals)
                        signal = assignedSignals{i};

                        % Check if this signal is from the CSV we want to remove
                        if isfield(signal, 'CSVIdx') && signal.CSVIdx == csvIndex
                            removedCount = removedCount + 1;
                            % Don't add to filteredSignals (i.e., remove it)
                        else
                            filteredSignals{end+1} = signal; %#ok<AGROW>
                        end
                    end

                    % Update the assignments for this subplot
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = filteredSignals;
                end
            end

            % Refresh ALL plots in ALL tabs
            for tabIdx = 1:numTabs
                app.PlotManager.refreshPlots(tabIdx);
            end

            % Clear tree selection
            app.SignalTree.SelectedNodes = [];

            % Update status
            if removedCount > 0
                app.StatusLabel.Text = sprintf('🗑️ Removed %d signal assignments from "%s" across all tabs', removedCount, csvNode.Text);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = sprintf('ℹ️ No signals from "%s" were assigned to any subplots', csvNode.Text);
                app.StatusLabel.FontColor = [0.5 0.5 0.5];
            end
        end
        function clearAllDerivedSignalsFromSubplots(app)
            % Clear all derived signals from all subplots

            if isempty(app.SignalOperations.DerivedSignals)
                uialert(app.UIFigure, 'No derived signals to clear.', 'No Derived Signals');
                return;
            end

            derivedNames = keys(app.SignalOperations.DerivedSignals);

            % Confirm action
            answer = uiconfirm(app.UIFigure, ...
                sprintf('Remove all derived signals from ALL subplots in ALL tabs?\n\nDerived signals: %s', ...
                strjoin(derivedNames, ', ')), ...
                'Confirm Clear Derived Signals', ...
                'Options', {'Remove All', 'Cancel'}, ...
                'DefaultOption', 'Cancel', 'Icon', 'warning');

            if strcmp(answer, 'Cancel')
                return;
            end

            % FIXED: Remove derived signals from ALL subplots in ALL tabs
            removedCount = 0;
            numTabs = numel(app.PlotManager.AxesArrays);

            for tabIdx = 1:numTabs
                % Ensure this tab exists in AssignedSignals
                if tabIdx > numel(app.PlotManager.AssignedSignals)
                    continue;
                end

                % Get number of subplots in this tab
                if ~isempty(app.PlotManager.AxesArrays{tabIdx})
                    numSubplots = numel(app.PlotManager.AxesArrays{tabIdx});
                else
                    continue;
                end

                % Process each subplot in this tab
                for subplotIdx = 1:numSubplots
                    % Ensure this subplot exists in AssignedSignals
                    if subplotIdx > numel(app.PlotManager.AssignedSignals{tabIdx})
                        continue;
                    end

                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                    if isempty(assignedSignals)
                        continue;
                    end

                    % Filter out derived signals (CSVIdx = -1)
                    filteredSignals = {};
                    for i = 1:numel(assignedSignals)
                        signal = assignedSignals{i};

                        % Check if this is a derived signal
                        if isfield(signal, 'CSVIdx') && signal.CSVIdx == -1
                            removedCount = removedCount + 1;
                            % Don't add to filteredSignals (i.e., remove it)
                        else
                            filteredSignals{end+1} = signal; %#ok<AGROW>
                        end
                    end

                    % Update the assignments for this subplot
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = filteredSignals;
                end
            end

            % Refresh ALL plots in ALL tabs
            for tabIdx = 1:numTabs
                app.PlotManager.refreshPlots(tabIdx);
            end

            % Clear tree selection
            app.SignalTree.SelectedNodes = [];

            % Update status
            if removedCount > 0
                app.StatusLabel.Text = sprintf('🗑️ Removed %d derived signal assignments from all subplots', removedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'ℹ️ No derived signals were assigned to any subplots';
                app.StatusLabel.FontColor = [0.5 0.5 0.5];
            end
        end

        function clearSpecificSignalFromAllSubplots(app, signalData)
            % Clear a specific signal from all subplots

            signalName = signalData.Signal;
            csvIdx = signalData.CSVIdx;

            % Confirm action
            answer = uiconfirm(app.UIFigure, ...
                sprintf('Remove signal "%s" from all subplots?', signalName), ...
                'Confirm Clear Signal', ...
                'Options', {'Remove', 'Cancel'}, ...
                'DefaultOption', 'Cancel', 'Icon', 'question');

            if strcmp(answer, 'Cancel')
                return;
            end

            % Remove signal from all subplots
            removedCount = 0;
            for tabIdx = 1:numel(app.PlotManager.AssignedSignals)
                for subplotIdx = 1:numel(app.PlotManager.AssignedSignals{tabIdx})
                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                    % Filter out this specific signal
                    filteredSignals = {};
                    for i = 1:numel(assignedSignals)
                        signal = assignedSignals{i};
                        if ~(signal.CSVIdx == csvIdx && strcmp(signal.Signal, signalName))
                            filteredSignals{end+1} = signal; %#ok<AGROW>
                        else
                            removedCount = removedCount + 1;
                        end
                    end

                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = filteredSignals;
                end
            end

            % Refresh all plots
            app.PlotManager.refreshPlots();

            % Clear tree selection
            app.SignalTree.SelectedNodes = [];

            % Update status
            app.StatusLabel.Text = sprintf('🗑️ Removed signal "%s" from %d subplots', signalName, removedCount);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function csvIndex = getCSVIndexFromNode(app, csvNode)
            % Extract CSV index from node text or data
            csvIndex = -1;

            % Try to get from NodeData first
            if isfield(csvNode.NodeData, 'CSVIdx')
                csvIndex = csvNode.NodeData.CSVIdx;
                return;
            end

            % Try to extract from text pattern
            nodeText = csvNode.Text;

            % Look for patterns like "CSV1:", "data1.csv", etc.
            if contains(nodeText, 'CSV')
                % Extract number after CSV
                csvMatch = regexp(nodeText, 'CSV(\d+)', 'tokens');
                if ~isempty(csvMatch)
                    csvIndex = str2double(csvMatch{1}{1});
                    return;
                end
            end

            % Try to match with actual CSV file names
            for i = 1:numel(app.DataManager.CSVFilePaths)
                [~, fileName, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                fullFileName = [fileName ext];
                if contains(nodeText, fullFileName)
                    csvIndex = i;
                    return;
                end
            end
        end

        function forceClearAllHighlights(app, tabIdx)
            % NUCLEAR option: remove ALL green elements from all subplots
            if nargin < 2
                % If no tabIdx specified, clear all tabs
                for t = 1:numel(app.PlotManager.AxesArrays)
                    app.forceClearAllHighlights(t);
                end
                return;
            end

            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
                    ~isempty(app.PlotManager.AxesArrays{tabIdx})

                for i = 1:numel(app.PlotManager.AxesArrays{tabIdx})
                    ax = app.PlotManager.AxesArrays{tabIdx}(i);
                    if isvalid(ax)
                        % FORCE reset axes properties
                        ax.XColor = [0.15 0.15 0.15];
                        ax.YColor = [0.15 0.15 0.15];
                        ax.LineWidth = 1;
                        ax.Box = 'on';

                        % Get ALL children
                        children = get(ax, 'Children');
                        toDelete = [];

                        for j = 1:numel(children)
                            child = children(j);

                            % Delete ANY green objects or thick lines
                            shouldDelete = false;

                            if isa(child, 'matlab.graphics.chart.primitive.Line')
                                % Check if it's green (any shade)
                                if length(child.Color) >= 3
                                    if child.Color(2) > 0.5 && child.Color(1) < 0.5 && child.Color(3) < 0.5
                                        shouldDelete = true; % Greenish color
                                    end
                                end

                                % Check if it's a thick line (likely border)
                                if child.LineWidth >= 4
                                    shouldDelete = true;
                                end

                                % Check if it matches our highlight color exactly
                                if isequal(child.Color, app.CurrentHighlightColor)
                                    shouldDelete = true;
                                end

                                % Check if it's a line with empty DisplayName (typical of borders)
                                if isprop(child, 'DisplayName') && isempty(child.DisplayName) && child.LineWidth > 2
                                    shouldDelete = true;
                                end
                            end

                            if shouldDelete
                                toDelete = [toDelete, child];
                            end
                        end

                        % Delete all flagged objects
                        delete(toDelete);

                        % Clear UserData completely
                        ax.UserData = struct();
                    end
                end

                % Refresh the plots to restore proper data
                app.PlotManager.refreshPlots(tabIdx);
            end
        end

        function initializeCaptionArrays(app, tabIdx, numSubplots)
            % Initialize caption arrays for a specific tab

            % Ensure arrays are large enough
            while numel(app.SubplotCaptions) < tabIdx
                app.SubplotCaptions{end+1} = {};
            end
            while numel(app.SubplotDescriptions) < tabIdx
                app.SubplotDescriptions{end+1} = {};
            end
            while numel(app.SubplotTitles) < tabIdx
                app.SubplotTitles{end+1} = {};
            end

            % Initialize subplot arrays for this tab
            app.SubplotCaptions{tabIdx} = cell(1, numSubplots);
            app.SubplotDescriptions{tabIdx} = cell(1, numSubplots);
            app.SubplotTitles{tabIdx} = cell(1, numSubplots);

            % Set default values
            for i = 1:numSubplots
                if isempty(app.SubplotCaptions{tabIdx}{i})
                    app.SubplotCaptions{tabIdx}{i} = sprintf('Caption for subplot %d', i);
                end
                if isempty(app.SubplotDescriptions{tabIdx}{i})
                    app.SubplotDescriptions{tabIdx}{i} = sprintf('Description for Tab %d, Subplot %d', tabIdx, i);
                end
                if isempty(app.SubplotTitles{tabIdx}{i})
                    app.SubplotTitles{tabIdx}{i} = sprintf('Subplot %d', i);
                end
            end
        end
        function editSubplotCaption(app, tabIdx, subplotIdx)
            % Edit caption, description, and title for a specific subplot

            % Ensure arrays are initialized
            if numel(app.SubplotCaptions) < tabIdx || numel(app.SubplotCaptions{tabIdx}) < subplotIdx
                nPlots = app.PlotManager.TabLayouts{tabIdx}(1) * app.PlotManager.TabLayouts{tabIdx}(2);
                app.initializeCaptionArrays(tabIdx, nPlots);
            end

            % Get current values
            currentTitle = '';
            currentCaption = '';
            currentDescription = '';

            if numel(app.SubplotTitles) >= tabIdx && numel(app.SubplotTitles{tabIdx}) >= subplotIdx
                currentTitle = app.SubplotTitles{tabIdx}{subplotIdx};
            end
            if numel(app.SubplotCaptions) >= tabIdx && numel(app.SubplotCaptions{tabIdx}) >= subplotIdx
                currentCaption = app.SubplotCaptions{tabIdx}{subplotIdx};
            end
            if numel(app.SubplotDescriptions) >= tabIdx && numel(app.SubplotDescriptions{tabIdx}) >= subplotIdx
                currentDescription = app.SubplotDescriptions{tabIdx}{subplotIdx};
            end

            % Create dialog
            d = dialog('Name', 'Edit Figure Content', 'Position', [300 300 500 400]);

            % Subplot title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 350 100 20], ...
                'String', 'Subplot Title:', 'HorizontalAlignment', 'left', 'FontWeight', 'bold');
            titleField = uicontrol('Parent', d, 'Style', 'edit', 'Position', [20 325 460 25], ...
                'String', currentTitle, 'HorizontalAlignment', 'left');

            % Caption label and field
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 290 100 20], ...
                'String', 'Caption:', 'HorizontalAlignment', 'left', 'FontWeight', 'bold');
            captionField = uicontrol('Parent', d, 'Style', 'edit', 'Position', [20 265 460 25], ...
                'String', currentCaption, 'HorizontalAlignment', 'left');

            % Description label and field
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 230 100 20], ...
                'String', 'Description:', 'HorizontalAlignment', 'left', 'FontWeight', 'bold');
            descField = uicontrol('Parent', d, 'Style', 'edit', 'Position', [20 150 460 75], ...
                'String', currentDescription, 'Max', 3, 'HorizontalAlignment', 'left');

            % Help text
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 110 460 35], ...
                'String', 'You can write in Hebrew or English. Hebrew text will be automatically right-aligned in the PDF. The subplot title will appear above the plot.', ...
                'FontSize', 9, 'HorizontalAlignment', 'left', 'ForegroundColor', [0.5 0.5 0.5]);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Save', ...
                'Position', [320 20 60 25], 'Callback', @(~,~) saveContent());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [390 20 60 25], 'Callback', @(~,~) close(d));

            function saveContent()
                % Save the new title, caption and description
                app.SubplotTitles{tabIdx}{subplotIdx} = titleField.String;
                app.SubplotCaptions{tabIdx}{subplotIdx} = captionField.String;
                app.SubplotDescriptions{tabIdx}{subplotIdx} = descField.String;

                % Update status
                app.StatusLabel.Text = sprintf('✅ Content updated for Plot %d.%d', tabIdx, subplotIdx);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

                close(d);
                app.restoreFocus();
            end
        end

        function clearSubplotHighlights(app, tabIdx)
            % Clear all subplot highlights for a given tab
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
                    ~isempty(app.PlotManager.AxesArrays{tabIdx})

                for i = 1:numel(app.PlotManager.AxesArrays{tabIdx})
                    ax = app.PlotManager.AxesArrays{tabIdx}(i);
                    if isvalid(ax)
                        % Reset ALL axes to normal styling - NO GREEN COLORS
                        ax.XColor = [0.15 0.15 0.15];     % Dark gray axes
                        ax.YColor = [0.15 0.15 0.15];
                        ax.LineWidth = 1;
                        ax.Box = 'on';

                        % Remove highlight borders using UserData
                        if isstruct(ax.UserData) && isfield(ax.UserData, 'HighlightBorders')
                            borders = ax.UserData.HighlightBorders;
                            for j = 1:numel(borders)
                                if isvalid(borders(j))
                                    delete(borders(j));
                                end
                            end
                            ax.UserData = rmfield(ax.UserData, 'HighlightBorders');
                        end

                        % Initialize UserData if needed
                        if ~isstruct(ax.UserData)
                            ax.UserData = struct();
                        end
                    end
                end
            end
        end
        function onSignalTreeSelectionChanged(app, event)
            selectedNodes = app.SignalTree.SelectedNodes;

            % If no nodes selected, don't change anything
            if isempty(selectedNodes)
                return;
            end

            % Count how many actual signals are selected
            signalCount = 0;
            selectedSignals = {};

            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);

                % Skip folder nodes and operation nodes
                if isstruct(node.NodeData) && isfield(node.NodeData, 'Type')
                    % Skip these types: folder nodes, operations, etc.
                    continue;
                end

                % Count actual signals
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData; %#ok<AGROW>
                    signalCount = signalCount + 1;
                end
            end

            % ONLY update if we have actual signals selected
            % If user clicked on folder, signalCount will be 0 and nothing happens
            if signalCount > 0
                tabIdx = app.PlotManager.CurrentTabIdx;
                subplotIdx = app.PlotManager.SelectedSubplotIdx;
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = selectedSignals;
                app.PlotManager.refreshPlots(tabIdx);
                app.updateSignalPropsTable(selectedSignals);
            end
            % If signalCount == 0, we do nothing - subplot keeps its current signals
        end
        function tf = hasSignalsLoaded(app)
            % Check if we have signals loaded and signal tree populated
            tf = ~isempty(app.DataManager.SignalNames) && ...
                ~isempty(app.SignalTree.Children) && ...
                ~isempty(app.DataManager.DataTables) && ...
                any(~cellfun(@isempty, app.DataManager.DataTables));
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
            % REMOVED: drawnow; - Let MATLAB update the table UI naturally
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
        function [isCompatible, missingSignals, extraSignals] = checkConfigCompatibility(app, config)
            % Check if loaded signals are compatible with config
            isCompatible = true;
            missingSignals = {};
            extraSignals = {};

            if ~isfield(config, 'AssignedSignals') || isempty(config.AssignedSignals)
                return;
            end

            % Get all signals referenced in the config
            configSignals = {};
            for tabIdx = 1:numel(config.AssignedSignals)
                for subplotIdx = 1:numel(config.AssignedSignals{tabIdx})
                    assignments = config.AssignedSignals{tabIdx}{subplotIdx};
                    for i = 1:numel(assignments)
                        if isstruct(assignments{i}) && isfield(assignments{i}, 'Signal')
                            configSignals{end+1} = assignments{i}.Signal;
                        end
                    end
                end
            end
            configSignals = unique(configSignals);

            % Check for missing signals (in config but not loaded)
            currentSignals = app.DataManager.SignalNames;
            missingSignals = setdiff(configSignals, currentSignals);

            % Check for extra signals (loaded but not in config) - just for info
            extraSignals = setdiff(currentSignals, configSignals);

            % Consider incompatible if critical signals are missing
            if ~isempty(missingSignals)
                isCompatible = false;
            end
        end
        function restoreFocus(app)
            % Restore focus to the main application window
            try
                figure(app.UIFigure);
                drawnow;
            catch
                % Ignore errors
            end
        end
        function enableDataTipsByDefault(app)
            % Don't enable data tips by default to avoid context menu conflicts
            % User can enable them via right-click menu
            for i = 1:numel(app.PlotManager.AxesArrays)
                if ~isempty(app.PlotManager.AxesArrays{i})
                    for ax = app.PlotManager.AxesArrays{i}
                        if isgraphics(ax, 'axes')
                            try
                                % Only enable pan and zoom by default
                                ax.Interactions = [panInteraction, zoomInteraction];

                                % Ensure datacursormode is OFF by default
                                dcm = datacursormode(ancestor(ax, 'figure'));
                                dcm.Enable = 'off';

                            catch
                                % Ignore errors
                            end
                        end
                    end
                end
            end
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

            % Enable ONLY data tips by default when data is loaded (NOT crosshair cursor)
            if ~isempty(app.DataManager.DataTables) && any(~cellfun(@isempty, app.DataManager.DataTables))
                app.enableDataTipsByDefault();
                % Do NOT enable crosshair by default
            end
            % Add derived signals section (but NOT operations)
            if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations.DerivedSignals)
                app.SignalOperations.addDerivedSignalsToTree();
            end
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
        function autoScaleCurrentSubplot(app)
            % Auto-scale ALL subplots in the current tab
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            if tabIdx <= numel(app.PlotManager.AxesArrays)
                axesArray = app.PlotManager.AxesArrays{tabIdx};
                scaledCount = 0;

                for i = 1:numel(axesArray)
                    ax = axesArray(i);
                    if isvalid(ax) && isgraphics(ax) && ~isempty(ax.Children)
                        % Force auto-scaling on each subplot that has data
                        ax.XLimMode = 'auto';
                        ax.YLimMode = 'auto';
                        axis(ax, 'auto');
                        scaledCount = scaledCount + 1;
                    end
                end

                % Update status
                if scaledCount > 0
                    app.StatusLabel.Text = sprintf('📐 Auto-scaled %d plots in Tab %d', scaledCount, tabIdx);
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];
                else
                    app.StatusLabel.Text = '⚠️ No plots with data to auto-scale';
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                end

                % IMPORTANT: Restore highlight after auto-scaling
                % The highlight borders need to be redrawn with new axis limits
                if scaledCount > 0
                    % Small delay to let auto-scaling complete
                    pause(0.05);
                    app.highlightSelectedSubplot(tabIdx, subplotIdx);
                end
            end
        end
        function menuClearPlotsOnly(app)
            app.UIController.clearPlotsOnly();
        end

        function menuClearAll(app)
            app.UIController.clearAll();
        end
        function menuAddMoreCSVs(app)
            app.UIController.addMoreCSVs();
            figure(app.UIFigure);
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

        function delete(app)
            % Delete app
            delete(app.UIFigure);
        end

        % Rest of the methods remain the same but with drawnow removed where unnecessary...
        % [Continue with other methods but removing redundant drawnow calls]
        function saveConfig(app)
            % Delegate to ConfigManager
            app.ConfigManager.saveConfig();
            figure(app.UIFigure);
        end

        function loadConfig(app)
            % Delegate to ConfigManager
            app.ConfigManager.loadConfig();
            figure(app.UIFigure);
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

            % Get current tab's layout values from TabControls instead of non-existent spinners
            tabIdx = app.PlotManager.CurrentTabIdx;
            if tabIdx <= numel(app.PlotManager.TabControls) && ~isempty(app.PlotManager.TabControls{tabIdx})
                session.RowsSpinnerValue = app.PlotManager.TabControls{tabIdx}.RowsSpinner.Value;
                session.ColsSpinnerValue = app.PlotManager.TabControls{tabIdx}.ColsSpinner.Value;
            else
                % Fallback to current layout if TabControls not available
                currentLayout = app.PlotManager.TabLayouts{tabIdx};
                session.RowsSpinnerValue = currentLayout(1);
                session.ColsSpinnerValue = currentLayout(2);
            end

            session.AutoScale = true; % Default value since AutoScaleCheckbox doesn't exist

            if isprop(app, 'SubplotMetadata')
                session.SubplotMetadata = app.SubplotMetadata;
            else
                session.SubplotMetadata = {};
            end

            if isprop(app, 'SignalStyles')
                session.SignalStyles = app.SignalStyles;
            else
                session.SignalStyles = struct();
            end

            session.SubplotCaptions = app.SubplotCaptions;
            session.SubplotDescriptions = app.SubplotDescriptions;

            save(fullfile(path, file), 'session');
            app.StatusLabel.Text = '✅ Session saved successfully';
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
            figure(app.UIFigure);
        end
        function loadSession(app)
            % Load a session from a .mat file
            [file, path] = uigetfile('*.mat', 'Load Session');
            if isequal(file, 0), return; end

            loaded = load(fullfile(path, file));
            if ~isfield(loaded, 'session')
                app.StatusLabel.Text = '❌ Invalid session file';
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                app.restoreFocus();
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

            % Set tab layouts using the saved values
            if isfield(session, 'RowsSpinnerValue') && isfield(session, 'ColsSpinnerValue')
                tabIdx = app.PlotManager.CurrentTabIdx;
                if tabIdx <= numel(app.PlotManager.TabControls) && ~isempty(app.PlotManager.TabControls{tabIdx})
                    app.PlotManager.TabControls{tabIdx}.RowsSpinner.Value = session.RowsSpinnerValue;
                    app.PlotManager.TabControls{tabIdx}.ColsSpinner.Value = session.ColsSpinnerValue;
                end
            end

            if isfield(session, 'SubplotMetadata')
                app.SubplotMetadata = session.SubplotMetadata;
            end

            if isfield(session, 'SignalStyles')
                app.SignalStyles = session.SignalStyles;
            end

            if isfield(session, 'SubplotCaptions')
                app.SubplotCaptions = session.SubplotCaptions;
            else
                app.SubplotCaptions = {};
            end

            if isfield(session, 'SubplotDescriptions')
                app.SubplotDescriptions = session.SubplotDescriptions;
            else
                app.SubplotDescriptions = {};
            end

            app.buildSignalTree();
            app.PlotManager.refreshPlots();

            % AUTO-SCALE ALL PLOTS AFTER LOADING SESSION
            app.autoScaleAllTabs();

            app.StatusLabel.Text = '✅ Session loaded successfully';
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
            figure(app.UIFigure);
        end

        function autoScaleAllTabs(app)
            % Auto-scale all subplots in all tabs
            scaledCount = 0;

            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                if ~isempty(app.PlotManager.AxesArrays{tabIdx})
                    axesArray = app.PlotManager.AxesArrays{tabIdx};

                    for i = 1:numel(axesArray)
                        ax = axesArray(i);
                        if isvalid(ax) && isgraphics(ax) && ~isempty(ax.Children)
                            % Force auto-scaling on each subplot that has data
                            ax.XLimMode = 'auto';
                            ax.YLimMode = 'auto';
                            axis(ax, 'auto');
                            scaledCount = scaledCount + 1;
                        end
                    end
                end
            end

            % Update status
            if scaledCount > 0
                app.StatusLabel.Text = sprintf('📐 Auto-scaled %d plots across all tabs', scaledCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

                % Small delay to let auto-scaling complete, then restore highlight
                pause(0.05);
                app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, app.PlotManager.SelectedSubplotIdx);
            end
        end
        % Helper function to assign selected signals in the tree to the current subplot
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

        % Add all other methods but remove unnecessary drawnow calls...
        % (The remaining methods would continue with similar optimization)

        function refreshCSVs(app)
            n = numel(app.DataManager.CSVFilePaths);
            for idx = 1:n
                app.DataManager.readInitialData(idx);
            end
            app.buildSignalTree();
            app.PlotManager.refreshPlots();
            % Do NOT auto-start streaming here to avoid recursion
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

        % Menu callback functions
        function menuStart(app)
            app.UIController.loadMultipleCSVs();
            figure(app.UIFigure);
        end
        function menuStop(app)
            app.DataManager.stopStreamingAll();
            figure(app.UIFigure);
        end

        function menuExportCSV(app)
            app.UIController.exportCSV();
            figure(app.UIFigure);
        end
        function menuExportPDF(app)
            app.PlotManager.exportToPDF();
            figure(app.UIFigure);
        end
        function menuStatistics(app)
            app.UIController.showStatsDialog();
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
            app.CursorState = ~app.CursorState;

            if app.CursorState
                app.PlotManager.enableCursorMode();
                app.CursorMenuItem.Text = '🎯 Disable Crosshair Cursor';
            else
                app.PlotManager.disableCursorMode();
                app.CursorMenuItem.Text = '🎯 Enable Crosshair Cursor';
            end
        end
        % Add other necessary methods...
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
    end
end