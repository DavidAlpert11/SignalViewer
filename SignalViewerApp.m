% Updated SignalViewerApp.m - Main changes for light mode and streaming - REMOVED REDUNDANT DRAWNOW
classdef SignalViewerApp < matlab.apps.AppBase
    properties
        % Main UI
        UIFigure
        ControlPanel
        MainTabGroup
        SignalOperations
        ExpandedTreeNodes = string.empty
        DerivedSignalsNode
        LinkingManager
        LinkedNodes         % containers.Map - stores node linking relationships
        LinkedSignals       % containers.Map - stores individual signal links
        LinkingGroups       % cell array - groups of linked nodes/signals
        ShowLinkIndicators  % logical - show visual link indicators in tree
        AutoLinkMode        % string - 'off', 'nodes', 'signals', 'patterns'
        LinkingRules        % struct array - custom linking rules
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
        HiddenSignals  % containers.Map to track hidden signals
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

        function createLinkingMenu(app)
            % Create linking menu - called AFTER LinkingManager is initialized
            linkingMenu = uimenu(app.UIFigure, 'Text', 'Linking');
            uimenu(linkingMenu, 'Text', '🔗 Configure Signal Linking', 'MenuSelectedFcn', @(src, event) app.LinkingManager.showLinkingDialog());
            uimenu(linkingMenu, 'Text', '📊 Generate Comparison Analysis', 'MenuSelectedFcn', @(src, event) app.LinkingManager.showComparisonDialog());
            uimenu(linkingMenu, 'Text', '⚡ Quick Link Selected Nodes', 'MenuSelectedFcn', @(src, event) app.LinkingManager.quickLinkSelected());
            uimenu(linkingMenu, 'Text', '🔓 Clear All Links', 'MenuSelectedFcn', @(src, event) app.LinkingManager.clearAllLinks());
        end
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

            % Ensure essential properties exist
            if ~isprop(app.DataManager, 'SignalNames') || isempty(app.DataManager.SignalNames)
                app.DataManager.SignalNames = {};
            end

            if ~isprop(app.DataManager, 'SignalScaling') || isempty(app.DataManager.SignalScaling)
                app.DataManager.SignalScaling = containers.Map('KeyType', 'char', 'ValueType', 'double');
            end

            if ~isprop(app.DataManager, 'StateSignals') || isempty(app.DataManager.StateSignals)
                app.DataManager.StateSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
            end
            app.ConfigManager = ConfigManager(app);
            app.SignalOperations = SignalOperationsManager(app);
            app.UIController  = UIController(app);
            app.LinkingManager = LinkingManager(app);
            app.createLinkingMenu();

            %=== Connect Callbacks ===%
            app.UIController.setupCallbacks();
            %=== Initialize visual enhancements ===%
            app.initializeVisualEnhancements();
            app.debugSessionData()
        end

        function createEnhancedComponents(app)
            % Enhanced layout with LIGHT MODE styling
            % Only keep controls that are actually used in the current workflow

            fileMenu = uimenu(app.UIFigure, 'Text', 'File');
            uimenu(fileMenu, 'Text', '💾 Save Layout Config', 'MenuSelectedFcn', @(src, event) app.ConfigManager.saveConfig());
            uimenu(fileMenu, 'Text', '📁 Load Layout Config', 'MenuSelectedFcn', @(src, event) app.ConfigManager.loadConfig());

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

            % Quick Operations - NEW!
            quickSubMenu = uimenu(operationsMenu, 'Text', '⚡ Quick Operations');
            uimenu(quickSubMenu, 'Text', '📊 Vector Magnitude', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickVectorMagnitude());
            uimenu(quickSubMenu, 'Text', '📈 Moving Average', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickMovingAverage());
            uimenu(quickSubMenu, 'Text', '🌊 FFT Analysis', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickFFT());
            uimenu(quickSubMenu, 'Text', '📏 RMS Calculation', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickRMS());
            uimenu(quickSubMenu, 'Text', '📊 Signal Average', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickAverage());

            % Management
            managementSubMenu = uimenu(operationsMenu, 'Text', '⚙️ Management');
            uimenu(managementSubMenu, 'Text', '📋 Operation History', 'MenuSelectedFcn', @(src, event) app.SignalOperations.showOperationHistory());
            uimenu(managementSubMenu, 'Text', '🗑️ Clear All Derived Signals', 'MenuSelectedFcn', @(src, event) app.confirmAndClearDerivedSignals());

            exportMenu = uimenu(app.UIFigure, 'Text', 'Export');
            uimenu(exportMenu, 'Text', '📊 Export CSV', 'MenuSelectedFcn', @(src, event) app.menuExportCSV());
            uimenu(exportMenu, 'Text', '📄 Export PDF', 'MenuSelectedFcn', @(src, event) app.menuExportPDF());
            uimenu(exportMenu, 'Text', '📂 Open Plot Browser View', 'MenuSelectedFcn', @(src, event) app.menuExportToPlotBrowser());
            uimenu(exportMenu, 'Text', '📡 Export to SDI', ...
                'MenuSelectedFcn', @(src, event) app.PlotManager.exportToSDI());



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


            app.SignalTree.ContextMenu = cm;
            app.setupMultiSelectionContextMenu();
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

            % After creating app.SignalTree, add:
            app.SignalTree.NodeExpandedFcn = @(src, event) app.onTreeNodeExpanded(event.Node.Text);
            app.SignalTree.NodeCollapsedFcn = @(src, event) app.onTreeNodeCollapsed(event.Node.Text);

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


        % Advanced signal filtering dialog
        function showAdvancedSignalFilter(app)
            % Create advanced filter dialog
            d = dialog('Name', 'Advanced Signal Filtering', ...
                'Position', [200 200 600 500], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 460 560 25], ...
                'String', 'Advanced Signal Filtering & Management', ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Filter by properties section
            filterPanel = uipanel('Parent', d, 'Position', [20 320 560 130], ...
                'Title', 'Filter by Properties', 'FontWeight', 'bold');

            % Scale filter
            uicontrol('Parent', filterPanel, 'Style', 'text', 'Position', [20 90 100 20], ...
                'String', 'Scale Factor:', 'FontWeight', 'bold');
            uicontrol('Parent', filterPanel, 'Style', 'text', 'Position', [20 65 40 20], ...
                'String', 'Min:');
            scaleMinField = uicontrol('Parent', filterPanel, 'Style', 'edit', ...
                'Position', [65 65 60 20], 'String', '', 'HorizontalAlignment', 'left');
            uicontrol('Parent', filterPanel, 'Style', 'text', 'Position', [135 65 40 20], ...
                'String', 'Max:');
            scaleMaxField = uicontrol('Parent', filterPanel, 'Style', 'edit', ...
                'Position', [180 65 60 20], 'String', '', 'HorizontalAlignment', 'left');

            % Signal type filter
            uicontrol('Parent', filterPanel, 'Style', 'text', 'Position', [280 90 100 20], ...
                'String', 'Signal Type:', 'FontWeight', 'bold');
            typeDropdown = uicontrol('Parent', filterPanel, 'Style', 'popupmenu', ...
                'Position', [280 65 120 25], ...
                'String', {'All Signals', 'Regular Only', 'State Only', 'Assigned Only', 'Unassigned Only'});

            % CSV filter
            uicontrol('Parent', filterPanel, 'Style', 'text', 'Position', [20 35 100 20], ...
                'String', 'CSV Source:', 'FontWeight', 'bold');
            csvNames = {'All CSVs'};
            for i = 1:numel(app.DataManager.CSVFilePaths)
                [~, name, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                csvNames{end+1} = sprintf('CSV %d: %s%s', i, name, ext);
            end
            csvDropdown = uicontrol('Parent', filterPanel, 'Style', 'popupmenu', ...
                'Position', [20 10 220 25], 'String', csvNames);

            % Apply filters button
            uicontrol('Parent', filterPanel, 'Style', 'pushbutton', 'String', 'Apply Filters', ...
                'Position', [450 35 80 30], 'Callback', @(~,~) applyFilters(), ...
                'FontWeight', 'bold');

            % Results section
            resultsPanel = uipanel('Parent', d, 'Position', [20 150 560 160], ...
                'Title', 'Filter Results', 'FontWeight', 'bold');

            uicontrol('Parent', resultsPanel, 'Style', 'text', 'Position', [20 120 200 20], ...
                'String', 'Filtered Signals:', 'FontWeight', 'bold');

            resultsListbox = uicontrol('Parent', resultsPanel, 'Style', 'listbox', ...
                'Position', [20 20 350 95], 'Max', 100); % Allow multiple selection

            % Actions for filtered signals
            uicontrol('Parent', resultsPanel, 'Style', 'pushbutton', 'String', 'Assign Selected to Current Subplot', ...
                'Position', [380 80 160 25], 'Callback', @(~,~) assignFilteredSignals());
            uicontrol('Parent', resultsPanel, 'Style', 'pushbutton', 'String', 'Bulk Edit Selected', ...
                'Position', [380 50 160 25], 'Callback', @(~,~) bulkEditFiltered());
            uicontrol('Parent', resultsPanel, 'Style', 'pushbutton', 'String', 'Export Selected to CSV', ...
                'Position', [380 20 160 25], 'Callback', @(~,~) exportFilteredSignals());

            % Quick actions section
            quickPanel = uipanel('Parent', d, 'Position', [20 50 560 90], ...
                'Title', 'Quick Actions', 'FontWeight', 'bold');

            uicontrol('Parent', quickPanel, 'Style', 'pushbutton', 'String', 'Show All Hidden Signals', ...
                'Position', [20 40 150 25], 'Callback', @(~,~) showAllHiddenSignals());
            uicontrol('Parent', quickPanel, 'Style', 'pushbutton', 'String', 'Reset All Signal Properties', ...
                'Position', [180 40 150 25], 'Callback', @(~,~) resetAllProperties());
            uicontrol('Parent', quickPanel, 'Style', 'pushbutton', 'String', 'Auto-Color All Signals', ...
                'Position', [340 40 150 25], 'Callback', @(~,~) autoColorSignals());

            % Statistics
            uicontrol('Parent', quickPanel, 'Style', 'text', 'Position', [20 10 520 20], ...
                'String', sprintf('Total Signals: %d | Currently Assigned: %d | State Signals: %d', ...
                getTotalSignalCount(), getAssignedSignalCount(), getStateSignalCount()), ...
                'FontSize', 9, 'HorizontalAlignment', 'left');

            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [500 10 80 30], 'Callback', @(~,~) close(d));

            % Store filtered results
            filteredSignals = {};

            function applyFilters()
                filteredSignals = {};

                % Get filter criteria
                minScale = str2double(scaleMinField.String);
                maxScale = str2double(scaleMaxField.String);
                if isnan(minScale), minScale = -inf; end
                if isnan(maxScale), maxScale = inf; end

                typeFilter = typeDropdown.Value;
                csvFilter = csvDropdown.Value;

                % Get current assignments for filtering
                tabIdx = app.PlotManager.CurrentTabIdx;
                subplotIdx = app.PlotManager.SelectedSubplotIdx;
                assignedSignals = {};
                if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                end

                % Filter each CSV
                for i = 1:numel(app.DataManager.DataTables)
                    T = app.DataManager.DataTables{i};
                    if isempty(T), continue; end

                    % CSV filter
                    if csvFilter > 1 && csvFilter-1 ~= i
                        continue;
                    end

                    signals = setdiff(T.Properties.VariableNames, {'Time'});

                    for j = 1:numel(signals)
                        signalName = signals{j};
                        signalInfo = struct('CSVIdx', i, 'Signal', signalName);

                        % Scale filter
                        scale = 1.0;
                        if app.DataManager.SignalScaling.isKey(signalName)
                            scale = app.DataManager.SignalScaling(signalName);
                        end
                        if scale < minScale || scale > maxScale
                            continue;
                        end

                        % Type filter
                        isState = false;
                        if app.DataManager.StateSignals.isKey(signalName)
                            isState = app.DataManager.StateSignals(signalName);
                        end

                        isAssigned = false;
                        for k = 1:numel(assignedSignals)
                            if isequal(assignedSignals{k}, signalInfo)
                                isAssigned = true;
                                break;
                            end
                        end

                        switch typeFilter
                            case 2 % Regular only
                                if isState, continue; end
                            case 3 % State only
                                if ~isState, continue; end
                            case 4 % Assigned only
                                if ~isAssigned, continue; end
                            case 5 % Unassigned only
                                if isAssigned, continue; end
                        end

                        % Add to filtered results
                        filteredSignals{end+1} = signalInfo;
                    end
                end

                % Update results listbox
                if isempty(filteredSignals)
                    resultsListbox.String = {'No signals match the filter criteria'};
                    resultsListbox.Value = 1;
                else
                    displayNames = cell(numel(filteredSignals), 1);
                    for i = 1:numel(filteredSignals)
                        signal = filteredSignals{i};
                        [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{signal.CSVIdx});
                        displayNames{i} = sprintf('%s (CSV%d: %s%s)', signal.Signal, signal.CSVIdx, csvName, ext);
                    end
                    resultsListbox.String = displayNames;
                    resultsListbox.Value = 1:min(10, length(displayNames)); % Select first 10
                end

                app.StatusLabel.Text = sprintf('🔍 Found %d signals matching filter criteria', numel(filteredSignals));
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end

            function assignFilteredSignals()
                if isempty(filteredSignals)
                    return;
                end

                selectedIndices = resultsListbox.Value;
                if isempty(selectedIndices) || (length(selectedIndices) == 1 && strcmp(resultsListbox.String{1}, 'No signals match the filter criteria'))
                    return;
                end

                signalsToAssign = filteredSignals(selectedIndices);

                tabIdx = app.PlotManager.CurrentTabIdx;
                subplotIdx = app.PlotManager.SelectedSubplotIdx;
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = signalsToAssign;

                app.buildSignalTree();
                app.PlotManager.refreshPlots(tabIdx);
                app.updateSignalPropsTable(signalsToAssign);

                app.StatusLabel.Text = sprintf('📌 Assigned %d filtered signals to subplot', length(selectedIndices));
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end

            function bulkEditFiltered()
                if isempty(filteredSignals)
                    return;
                end

                selectedIndices = resultsListbox.Value;
                if isempty(selectedIndices)
                    return;
                end

                % Create mini bulk edit dialog
                bd = dialog('Name', 'Bulk Edit Filtered Signals', 'Position', [350 350 400 250]);

                uicontrol('Parent', bd, 'Style', 'text', 'Position', [20 210 360 25], ...
                    'String', sprintf('Bulk Edit %d Filtered Signals', length(selectedIndices)), ...
                    'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

                % Scale
                uicontrol('Parent', bd, 'Style', 'text', 'Position', [20 170 100 20], ...
                    'String', 'Set Scale:', 'FontWeight', 'bold');
                bulkScaleField = uicontrol('Parent', bd, 'Style', 'edit', ...
                    'Position', [130 170 80 25], 'String', '1.0');
                uicontrol('Parent', bd, 'Style', 'pushbutton', 'String', 'Apply', ...
                    'Position', [220 170 60 25], 'Callback', @(~,~) applyBulkScaleFiltered());

                % State
                uicontrol('Parent', bd, 'Style', 'pushbutton', 'String', 'Mark as State', ...
                    'Position', [20 130 120 30], 'Callback', @(~,~) applyBulkStateFiltered(true));
                uicontrol('Parent', bd, 'Style', 'pushbutton', 'String', 'Mark as Regular', ...
                    'Position', [150 130 120 30], 'Callback', @(~,~) applyBulkStateFiltered(false));

                uicontrol('Parent', bd, 'Style', 'pushbutton', 'String', 'Close', ...
                    'Position', [300 20 80 30], 'Callback', @(~,~) close(bd));

                function applyBulkScaleFiltered()
                    newScale = str2double(bulkScaleField.String);
                    if isnan(newScale), newScale = 1.0; end

                    for i = selectedIndices
                        if i <= length(filteredSignals)
                            app.DataManager.SignalScaling(filteredSignals{i}.Signal) = newScale;
                        end
                    end
                    app.PlotManager.refreshPlots();
                    close(bd);
                end

                function applyBulkStateFiltered(isState)
                    for i = selectedIndices
                        if i <= length(filteredSignals)
                            app.DataManager.StateSignals(filteredSignals{i}.Signal) = isState;
                        end
                    end
                    app.PlotManager.refreshPlots();
                    close(bd);
                end
            end

            function exportFilteredSignals()
                % Export filtered signals to CSV - implementation similar to existing export
                if isempty(filteredSignals)
                    return;
                end

                selectedIndices = resultsListbox.Value;
                if isempty(selectedIndices)
                    return;
                end

                signalsToExport = filteredSignals(selectedIndices);
                app.UIController.exportSignalsToFolder(signalsToExport, 'FilteredSignals');
            end

            function showAllHiddenSignals()
                if isprop(app, 'HiddenSignals')
                    app.HiddenSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
                end
                app.buildSignalTree();
                app.StatusLabel.Text = '👁️ Showing all previously hidden signals';
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end

            function resetAllProperties()
                % Reset all signal properties to defaults
                answer = uiconfirm(d, 'Reset ALL signal properties to defaults?', 'Confirm Reset', ...
                    'Options', {'Reset All', 'Cancel'}, 'DefaultOption', 'Cancel');

                if strcmp(answer, 'Reset All')
                    app.DataManager.SignalScaling = containers.Map('KeyType', 'char', 'ValueType', 'double');
                    app.DataManager.StateSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
                    app.SignalStyles = struct();

                    % Reinitialize with defaults
                    app.DataManager.initializeSignalMaps();
                    app.PlotManager.refreshPlots();

                    app.StatusLabel.Text = '🔄 Reset all signal properties to defaults';
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];
                end
            end

            function autoColorSignals()
                % Auto-assign colors from color palette
                colorPalette = app.Colors; % Use the app's color palette

                if isempty(app.SignalStyles)
                    app.SignalStyles = struct();
                end

                colorIndex = 1;
                colorCount = 0;

                for i = 1:numel(app.DataManager.DataTables)
                    T = app.DataManager.DataTables{i};
                    if isempty(T), continue; end

                    signals = setdiff(T.Properties.VariableNames, {'Time'});
                    for j = 1:numel(signals)
                        signalName = signals{j};

                        if ~isfield(app.SignalStyles, signalName)
                            app.SignalStyles.(signalName) = struct();
                        end

                        app.SignalStyles.(signalName).Color = colorPalette(colorIndex, :);
                        colorIndex = colorIndex + 1;
                        if colorIndex > size(colorPalette, 1)
                            colorIndex = 1;
                        end
                        colorCount = colorCount + 1;
                    end
                end

                app.PlotManager.refreshPlots();
                app.StatusLabel.Text = sprintf('🎨 Auto-colored %d signals', colorCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end

            function total = getTotalSignalCount()
                total = 0;
                for i = 1:numel(app.DataManager.DataTables)
                    if ~isempty(app.DataManager.DataTables{i})
                        signals = setdiff(app.DataManager.DataTables{i}.Properties.VariableNames, {'Time'});
                        total = total + numel(signals);
                    end
                end
            end

            function assigned = getAssignedSignalCount()
                assigned = 0;
                tabIdx = app.PlotManager.CurrentTabIdx;
                subplotIdx = app.PlotManager.SelectedSubplotIdx;
                if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                    assigned = numel(app.PlotManager.AssignedSignals{tabIdx}{subplotIdx});
                end
            end

            function stateCount = getStateSignalCount()
                stateCount = 0;
                stateKeys = keys(app.DataManager.StateSignals);
                for i = 1:length(stateKeys)
                    if app.DataManager.StateSignals(stateKeys{i})
                        stateCount = stateCount + 1;
                    end
                end
            end
        end

        function highlightSelectedSubplot(app, tabIdx, subplotIdx)
            % % Highlight the currently selected subplot with only an outer border
            % if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
            %         ~isempty(app.PlotManager.AxesArrays{tabIdx}) && ...
            %         subplotIdx <= numel(app.PlotManager.AxesArrays{tabIdx})
            %
            %     % FORCE clear ALL highlights in this tab first
            %     for i = 1:numel(app.PlotManager.AxesArrays{tabIdx})
            %         ax = app.PlotManager.AxesArrays{tabIdx}(i);
            %         if isvalid(ax)
            %             % Reset to normal styling
            %             ax.XColor = [0.15 0.15 0.15];
            %             ax.YColor = [0.15 0.15 0.15];
            %             ax.LineWidth = 1;
            %             ax.Box = 'on';
            %
            %             % Remove any existing highlight borders
            %             if isstruct(ax.UserData) && isfield(ax.UserData, 'HighlightBorders')
            %                 borders = ax.UserData.HighlightBorders;
            %                 for j = 1:numel(borders)
            %                     if isvalid(borders(j))
            %                         delete(borders(j));
            %                     end
            %                 end
            %                 ax.UserData = rmfield(ax.UserData, 'HighlightBorders');
            %             end
            %
            %             % Also remove any plot objects that might be highlight borders
            %             % (in case UserData tracking failed)
            %             children = get(ax, 'Children');
            %             for j = 1:numel(children)
            %                 child = children(j);
            %                 if isa(child, 'matlab.graphics.chart.primitive.Line') && ...
            %                         child.LineWidth == 6 && ...
            %                         isequal(child.Color, app.CurrentHighlightColor)
            %                     delete(child);
            %                 end
            %             end
            %         end
            %     end
            %
            %     % NOW add border to ONLY the selected subplot
            %     ax = app.PlotManager.AxesArrays{tabIdx}(subplotIdx);
            %     if isvalid(ax)
            %         % Add a border using plot lines
            %         hold(ax, 'on');
            %
            %         % Get current axis limits
            %         xlims = ax.XLim;
            %         ylims = ax.YLim;
            %
            %         % Create border lines around the perimeter
            %         topBorder = plot(ax, xlims, [ylims(2) ylims(2)], ...
            %             'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
            %             'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');
            %
            %         bottomBorder = plot(ax, xlims, [ylims(1) ylims(1)], ...
            %             'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
            %             'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');
            %
            %         leftBorder = plot(ax, [xlims(1) xlims(1)], ylims, ...
            %             'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
            %             'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');
            %
            %         rightBorder = plot(ax, [xlims(2) xlims(2)], ylims, ...
            %             'Color', app.CurrentHighlightColor, 'LineWidth', 6, ...
            %             'Clipping', 'off', 'DisplayName', '', 'HandleVisibility', 'off');
            %
            %         hold(ax, 'off');
            %
            %         % Store the borders for later removal
            %         if ~isstruct(ax.UserData)
            %             ax.UserData = struct();
            %         end
            %         ax.UserData.HighlightBorders = [topBorder, bottomBorder, leftBorder, rightBorder];
            %     end
            % end

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


        % Add signal to current subplot
        function addSignalToCurrentSubplot(app, signalInfo)
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Check if already assigned
            for i = 1:numel(currentAssignments)
                if isequal(currentAssignments{i}, signalInfo)
                    app.StatusLabel.Text = sprintf('⚠️ Signal "%s" already assigned', signalInfo.Signal);
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                    return;
                end
            end

            % Add to assignments
            currentAssignments{end+1} = signalInfo;
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = currentAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(currentAssignments);

            app.StatusLabel.Text = sprintf('➕ Added "%s" to subplot', signalInfo.Signal);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        % Remove signal from current subplot
        function removeSignalFromCurrentSubplot(app, signalInfo)
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Find and remove the signal
            newAssignments = {};
            removed = false;
            for i = 1:numel(currentAssignments)
                if isequal(currentAssignments{i}, signalInfo)
                    removed = true;
                    % Skip this signal (don't add to newAssignments)
                else
                    newAssignments{end+1} = currentAssignments{i};
                end
            end

            if removed
                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssignments;

                % Refresh visuals
                app.buildSignalTree();
                app.PlotManager.refreshPlots(tabIdx);
                app.updateSignalPropsTable(newAssignments);

                app.StatusLabel.Text = sprintf('❌ Removed "%s" from subplot', signalInfo.Signal);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = sprintf('⚠️ Signal "%s" not found in subplot', signalInfo.Signal);
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end

        % Edit signal properties without assignment
        function editSignalProperties(app, signalInfo)
            signalName = signalInfo.Signal;

            % Create properties dialog
            d = dialog('Name', sprintf('Properties: %s', signalName), ...
                'Position', [300 300 450 350], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 310 410 25], ...
                'String', sprintf('Signal Properties: %s', signalName), ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Scale
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 270 100 20], ...
                'String', 'Scale Factor:', 'FontWeight', 'bold');

            currentScale = 1.0;
            if app.DataManager.SignalScaling.isKey(signalName)
                currentScale = app.DataManager.SignalScaling(signalName);
            end

            scaleField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [130 270 100 25], 'String', num2str(currentScale), ...
                'HorizontalAlignment', 'left');

            % State signal checkbox
            currentState = false;
            if app.DataManager.StateSignals.isKey(signalName)
                currentState = app.DataManager.StateSignals(signalName);
            end

            stateCheck = uicontrol('Parent', d, 'Style', 'checkbox', ...
                'Position', [20 230 250 20], 'String', 'State Signal (vertical lines)', ...
                'Value', currentState);

            % Color selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 190 100 20], ...
                'String', 'Line Color:', 'FontWeight', 'bold');

            % Get current color
            currentColor = [0 0.4470 0.7410]; % Default MATLAB blue
            if ~isempty(app.SignalStyles) && isfield(app.SignalStyles, signalName)
                if isfield(app.SignalStyles.(signalName), 'Color')
                    currentColor = app.SignalStyles.(signalName).Color;
                end
            end

            colorButton = uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [130 190 100 25], 'String', 'Choose Color', ...
                'BackgroundColor', currentColor, ...
                'Callback', @(src,~) chooseColor(src));

            % Line width
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 100 20], ...
                'String', 'Line Width:', 'FontWeight', 'bold');

            currentWidth = 2;
            if ~isempty(app.SignalStyles) && isfield(app.SignalStyles, signalName)
                if isfield(app.SignalStyles.(signalName), 'LineWidth')
                    currentWidth = app.SignalStyles.(signalName).LineWidth;
                end
            end

            widthField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [130 150 80 25], 'String', num2str(currentWidth), ...
                'HorizontalAlignment', 'left');

            % Signal filtering section
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 110 200 20], ...
                'String', 'Signal Filtering:', 'FontWeight', 'bold');

            filterCheck = uicontrol('Parent', d, 'Style', 'checkbox', ...
                'Position', [20 80 150 20], 'String', 'Hide from tree view', ...
                'Value', false);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Apply', ...
                'Position', [270 20 80 30], 'Callback', @(~,~) applyProperties(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [360 20 80 30], 'Callback', @(~,~) close(d));

            function chooseColor(src)
                newColor = uisetcolor(src.BackgroundColor, sprintf('Choose color for %s', signalName));
                if length(newColor) == 3 % User didn't cancel
                    src.BackgroundColor = newColor;
                end
            end

            function applyProperties()
                try
                    % Apply scale
                    newScale = str2double(scaleField.String);
                    if isnan(newScale) || newScale == 0
                        newScale = 1.0;
                    end
                    app.DataManager.SignalScaling(signalName) = newScale;

                    % Apply state
                    app.DataManager.StateSignals(signalName) = logical(stateCheck.Value);

                    % Apply visual properties
                    if isempty(app.SignalStyles)
                        app.SignalStyles = struct();
                    end
                    if ~isfield(app.SignalStyles, signalName)
                        app.SignalStyles.(signalName) = struct();
                    end

                    app.SignalStyles.(signalName).Color = colorButton.BackgroundColor;

                    newWidth = str2double(widthField.String);
                    if isnan(newWidth) || newWidth <= 0
                        newWidth = 2;
                    end
                    app.SignalStyles.(signalName).LineWidth = newWidth;

                    % Handle filtering
                    if ~isprop(app, 'HiddenSignals')
                        app.HiddenSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
                    end
                    app.HiddenSignals([signalName '_CSV' num2str(signalInfo.CSVIdx)]) = filterCheck.Value;

                    % Refresh plots if signal is currently displayed
                    app.PlotManager.refreshPlots();
                    app.buildSignalTree(); % Refresh tree in case filtering changed

                    app.StatusLabel.Text = sprintf('✅ Updated properties for "%s"', signalName);
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];

                    close(d);

                catch ME
                    uialert(d, sprintf('Error applying properties: %s', ME.message), 'Error');
                end
            end
        end

        % Show signal preview
        function showSignalPreview(app, signalInfo)
            try
                % FIXED: Use SignalOperationsManager.getSignalData for both regular and derived signals
                if signalInfo.CSVIdx == -1
                    % Derived signal - use SignalOperations to get data
                    [timeData, signalData] = app.SignalOperations.getSignalData(signalInfo.Signal);
                    signalSource = 'Derived Signal';
                else
                    % Regular CSV signal - use DataManager
                    T = app.DataManager.DataTables{signalInfo.CSVIdx};
                    if isempty(T) || ~ismember(signalInfo.Signal, T.Properties.VariableNames)
                        app.StatusLabel.Text = sprintf('⚠️ Signal "%s" not found', signalInfo.Signal);
                        return;
                    end

                    timeData = T.Time;
                    signalData = T.(signalInfo.Signal);
                    signalSource = sprintf('CSV %d', signalInfo.CSVIdx);

                    % Apply scaling if exists
                    if app.DataManager.SignalScaling.isKey(signalInfo.Signal)
                        signalData = signalData * app.DataManager.SignalScaling(signalInfo.Signal);
                    end

                    % Remove NaN values
                    validIdx = ~isnan(signalData);
                    timeData = timeData(validIdx);
                    signalData = signalData(validIdx);
                end

                if isempty(timeData)
                    app.StatusLabel.Text = sprintf('⚠️ No valid data for "%s"', signalInfo.Signal);
                    return;
                end

                % Create preview figure
                fig = figure('Name', sprintf('Preview: %s', signalInfo.Signal), ...
                    'Position', [200 200 800 400]);

                % Get color if custom color is set
                plotColor = [0 0.4470 0.7410]; % default
                if ~isempty(app.SignalStyles) && isfield(app.SignalStyles, signalInfo.Signal)
                    if isfield(app.SignalStyles.(signalInfo.Signal), 'Color')
                        plotColor = app.SignalStyles.(signalInfo.Signal).Color;
                    end
                end

                plot(timeData, signalData, 'LineWidth', 2, 'Color', plotColor);
                title(sprintf('Signal Preview: %s (%s)', signalInfo.Signal, signalSource), 'FontSize', 14);
                xlabel('Time');
                ylabel('Value');
                grid on;

                % Add basic statistics as text
                stats = sprintf('Mean: %.3f | Std: %.3f | Min: %.3f | Max: %.3f | Samples: %d', ...
                    mean(signalData), std(signalData), min(signalData), max(signalData), length(signalData));

                annotation(fig, 'textbox', [0.1 0.02 0.8 0.05], 'String', stats, ...
                    'HorizontalAlignment', 'center', 'FontSize', 10, ...
                    'BackgroundColor', [0.9 0.9 0.9], 'EdgeColor', 'none');

            catch ME
                app.StatusLabel.Text = sprintf('❌ Preview failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end
        % Assign all signals from CSV
        function assignAllSignalsFromCSV(app, csvIdx)
            T = app.DataManager.DataTables{csvIdx};
            if isempty(T), return; end

            signals = setdiff(T.Properties.VariableNames, {'Time'});

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Create signal info structures
            newAssignments = {};
            for i = 1:numel(signals)
                newAssignments{end+1} = struct('CSVIdx', csvIdx, 'Signal', signals{i});
            end

            % Replace current assignments
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(newAssignments);

            app.StatusLabel.Text = sprintf('📌 Assigned %d signals from CSV %d', numel(signals), csvIdx);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        % Remove all signals from CSV
        function removeAllSignalsFromCSV(app, csvIdx)
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Filter out signals from this CSV
            newAssignments = {};
            removedCount = 0;
            for i = 1:numel(currentAssignments)
                if currentAssignments{i}.CSVIdx == csvIdx
                    removedCount = removedCount + 1;
                else
                    newAssignments{end+1} = currentAssignments{i};
                end
            end

            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(newAssignments);

            app.StatusLabel.Text = sprintf('❌ Removed %d signals from CSV %d', removedCount, csvIdx);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        % Bulk edit signal properties
        function bulkEditSignalProperties(app, csvIdx)
            T = app.DataManager.DataTables{csvIdx};
            if isempty(T), return; end

            signals = setdiff(T.Properties.VariableNames, {'Time'});
            [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{csvIdx});

            % Create bulk edit dialog
            d = dialog('Name', sprintf('Bulk Edit: %s%s', csvName, ext), ...
                'Position', [250 250 500 400], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 360 460 25], ...
                'String', sprintf('Bulk Edit Properties for %s (%d signals)', [csvName ext], numel(signals)), ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 330 150 20], ...
                'String', 'Select Signals to Edit:', 'FontWeight', 'bold');

            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 250 460 75], 'String', signals, 'Max', length(signals), ...
                'Value', 1:length(signals)); % Select all by default

            % Bulk operations
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 200 20], ...
                'String', 'Bulk Operations:', 'FontWeight', 'bold');

            % Scale factor
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 190 120 20], ...
                'String', 'Set Scale Factor:', 'FontWeight', 'bold');
            scaleField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 190 80 25], 'String', '1.0', 'HorizontalAlignment', 'left');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Apply to Selected', ...
                'Position', [240 190 120 25], 'Callback', @(~,~) applyBulkScale());

            % State signals
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Mark Selected as State Signals', ...
                'Position', [20 150 200 30], 'Callback', @(~,~) applyBulkState(true));
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Mark Selected as Regular Signals', ...
                'Position', [230 150 200 30], 'Callback', @(~,~) applyBulkState(false));

            % Color assignment
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 110 120 20], ...
                'String', 'Set Color:', 'FontWeight', 'bold');
            colorButton = uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [150 110 80 25], 'String', 'Choose', ...
                'BackgroundColor', [0 0.4470 0.7410], ...
                'Callback', @(src,~) chooseColor(src));
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Apply to Selected', ...
                'Position', [240 110 120 25], 'Callback', @(~,~) applyBulkColor());

            % Line width
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 70 120 20], ...
                'String', 'Set Line Width:', 'FontWeight', 'bold');
            widthField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 70 80 25], 'String', '2', 'HorizontalAlignment', 'left');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Apply to Selected', ...
                'Position', [240 70 120 25], 'Callback', @(~,~) applyBulkWidth());

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [400 20 80 30], 'Callback', @(~,~) close(d));

            function chooseColor(src)
                newColor = uisetcolor(src.BackgroundColor, 'Choose bulk color');
                if length(newColor) == 3
                    src.BackgroundColor = newColor;
                end
            end

            function applyBulkScale()
                selectedIndices = signalListbox.Value;
                newScale = str2double(scaleField.String);
                if isnan(newScale) || newScale == 0
                    newScale = 1.0;
                end

                for i = selectedIndices
                    app.DataManager.SignalScaling(signals{i}) = newScale;
                end

                app.PlotManager.refreshPlots();
                app.StatusLabel.Text = sprintf('✅ Applied scale %.2f to %d signals', newScale, length(selectedIndices));
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end

            function applyBulkState(isState)
                selectedIndices = signalListbox.Value;

                for i = selectedIndices
                    app.DataManager.StateSignals(signals{i}) = isState;
                end

                app.PlotManager.refreshPlots();
                stateStr = char("state" * isState + "regular" * (~isState));
                app.StatusLabel.Text = sprintf('✅ Marked %d signals as %s', length(selectedIndices), stateStr);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end

            function applyBulkColor()
                selectedIndices = signalListbox.Value;
                newColor = colorButton.BackgroundColor;

                if isempty(selectedIndices)
                    uialert(d, 'Please select signals to apply color to.', 'No Selection');
                    return;
                end

                if isempty(app.SignalStyles)
                    app.SignalStyles = struct();
                end

                try
                    % Apply color to selected signals
                    for i = selectedIndices
                        signalName = signals{i};
                        if ~isfield(app.SignalStyles, signalName)
                            app.SignalStyles.(signalName) = struct();
                        end
                        app.SignalStyles.(signalName).Color = newColor;
                    end

                    % Refresh plots to show new colors
                    app.PlotManager.refreshPlots();

                    % Update status
                    colorStr = sprintf('RGB(%.2f,%.2f,%.2f)', newColor(1), newColor(2), newColor(3));
                    app.StatusLabel.Text = sprintf('✅ Applied color %s to %d signals', colorStr, length(selectedIndices));
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];

                catch ME
                    uialert(d, sprintf('Error applying color: %s', ME.message), 'Error');
                end
            end

            function applyBulkWidth()
                selectedIndices = signalListbox.Value;
                newWidth = str2double(widthField.String);
                if isnan(newWidth) || newWidth <= 0
                    newWidth = 2;
                end

                if isempty(selectedIndices)
                    uialert(d, 'Please select signals to apply line width to.', 'No Selection');
                    return;
                end

                if isempty(app.SignalStyles)
                    app.SignalStyles = struct();
                end

                try
                    % Apply line width to selected signals
                    for i = selectedIndices
                        signalName = signals{i};
                        if ~isfield(app.SignalStyles, signalName)
                            app.SignalStyles.(signalName) = struct();
                        end
                        app.SignalStyles.(signalName).LineWidth = newWidth;
                    end

                    % Refresh plots to show new line widths
                    app.PlotManager.refreshPlots();

                    % Update status
                    app.StatusLabel.Text = sprintf('✅ Applied line width %.1f to %d signals', newWidth, length(selectedIndices));
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];

                catch ME
                    uialert(d, sprintf('Error applying line width: %s', ME.message), 'Error');
                end
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

            % Get signal info from selected nodes
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);

                % Skip folder nodes and operation nodes
                if isstruct(node.NodeData) && isfield(node.NodeData, 'Type')
                    nodeType = node.NodeData.Type;
                    if strcmp(nodeType, 'derived_signals_folder') || strcmp(nodeType, 'operations')
                        continue;
                    end
                end

                % Count actual signals (both original and derived)
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData; %#ok<AGROW>
                end
            end

            % ALWAYS update the properties table with selected signals
            app.updateSignalPropsTable(selectedSignals);

            % Update status based on selection
            signalCount = numel(selectedSignals);
            if signalCount == 1
                app.StatusLabel.Text = sprintf('Selected: %s (right-click for options)', selectedSignals{1}.Signal);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            elseif signalCount > 1
                app.StatusLabel.Text = sprintf('Selected: %d signals (right-click for options)', signalCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'No signals selected';
                app.StatusLabel.FontColor = [0.5 0.5 0.5];
            end
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

            if n == 0
                % No signals selected - show empty table
                app.SignalPropsTable.Data = {};
                return;
            end

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

                % FIXED: Just show signal name without checkmark
                data{i,1} = sigName;  % No checkmark here
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
            % Updates DataManager and refreshes plots if signal is currently displayed.

            data = app.SignalPropsTable.Data;
            if isempty(data)
                return;
            end

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
                % Always update state
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

            % Small delay for value to commit
            pause(0.01);

            % Refresh plots (will only affect plots where this signal is assigned)
            app.PlotManager.refreshPlots();

            % Update status
            app.StatusLabel.Text = sprintf('✅ Updated %s properties', sigName);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
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
            % No need to read expanded state from UI - use stored state instead

            % Build a tree UI grouped by CSV, with signals as children
            delete(app.SignalTree.Children);

            % Get current subplot assignments for visual indicators
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            assignedSignals = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Store created CSV nodes for later expansion restoration
            createdNodes = {};

            % Process each CSV file
            for i = 1:numel(app.DataManager.CSVFilePaths)
                [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                csvDisplay = [csvName ext];
                T = app.DataManager.DataTables{i};
                if isempty(T), continue; end

                signals = setdiff(T.Properties.VariableNames, {'Time'});

                % Apply search filter if active
                if ~isempty(app.SignalSearchField.Value)
                    mask = contains(lower(signals), lower(app.SignalSearchField.Value));
                    signals = signals(mask);
                end

                % Create CSV node only if it has signals
                if ~isempty(signals)
                    csvNode = uitreenode(app.SignalTree, 'Text', csvDisplay);

                    % Store the node for later expansion restoration
                    createdNodes{end+1} = struct('Node', csvNode, 'Text', csvDisplay);

                    % Add CSV-level context menu for bulk operations
                    csvContextMenu = uicontextmenu(app.UIFigure);
                    uimenu(csvContextMenu, 'Text', '📌 Assign All to Current Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.assignAllSignalsFromCSV(i));
                    uimenu(csvContextMenu, 'Text', '❌ Remove All from Current Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.removeAllSignalsFromCSV(i));
                    uimenu(csvContextMenu, 'Text', '⚙️ Bulk Edit Properties', ...
                        'MenuSelectedFcn', @(src, event) app.bulkEditSignalProperties(i), 'Separator', 'on');
                    csvNode.ContextMenu = csvContextMenu;

                    % Add signals to this CSV node
                    for j = 1:numel(signals)
                        signalName = signals{j};

                        % Check if this signal is assigned to current subplot
                        isAssigned = false;
                        signalInfo = struct('CSVIdx', i, 'Signal', signalName);
                        for k = 1:numel(assignedSignals)
                            if isequal(assignedSignals{k}, signalInfo)
                                isAssigned = true;
                                break;
                            end
                        end

                        displayText = signalName;
                        child = uitreenode(csvNode, 'Text', displayText);
                        child.NodeData = signalInfo;
                    end
                end
            end

            % Add derived signals section if they exist
            if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations.DerivedSignals)
                app.SignalOperations.addDerivedSignalsToTree();

                % SIMPLIFIED: Find the derived signals node after creation instead of storing reference
                for i = 1:numel(app.SignalTree.Children)
                    node = app.SignalTree.Children(i);
                    if strcmp(node.Text, '⚙️ Derived Signals')
                        createdNodes{end+1} = struct('Node', node, 'Text', '⚙️ Derived Signals');
                        break;
                    end
                end
            end

            % Restore expanded state for previously expanded nodes
            % Initialize ExpandedTreeNodes property if it doesn't exist
            if ~isprop(app, 'ExpandedTreeNodes')
                app.ExpandedTreeNodes = string.empty;
            end

            for i = 1:length(createdNodes)
                nodeInfo = createdNodes{i};
                node = nodeInfo.Node;
                nodeText = nodeInfo.Text;

                % Check if this node should be expanded
                if any(strcmp(nodeText, app.ExpandedTreeNodes))
                    try
                        node.expand();
                        fprintf('Restored expansion for: %s\n', nodeText);
                    catch
                        % If expand() method doesn't work, try alternative
                        try
                            node.Expanded = true;
                            fprintf('Set Expanded=true for: %s\n', nodeText);
                        catch
                            fprintf('Failed to expand: %s\n', nodeText);
                        end
                    end
                end
            end

            % FIXED: Set up tree callbacks to track expansion/collapse
            % These callbacks work for ALL nodes in the tree, including derived signals
            app.SignalTree.NodeExpandedFcn = @(src, event) app.onTreeNodeExpanded(event.Node.Text);
            app.SignalTree.NodeCollapsedFcn = @(src, event) app.onTreeNodeCollapsed(event.Node.Text);

            % Setup axes drop targets and enable data tips
            app.setupAxesDropTargets();
            if ~isempty(app.DataManager.DataTables) && any(~cellfun(@isempty, app.DataManager.DataTables))
                app.enableDataTipsByDefault();
            end
        end
        % Also add these helper methods to your SignalViewerApp class:

        function onTreeNodeExpanded(app, csvNodeText)
            % Call this when a node is manually expanded
            if ~isprop(app, 'ExpandedTreeNodes')
                app.ExpandedTreeNodes = string.empty;
            end

            if ~any(strcmp(csvNodeText, app.ExpandedTreeNodes))
                app.ExpandedTreeNodes(end+1) = csvNodeText;
            end

            % DEBUG: Track expansion
            fprintf('Node expanded: %s\n', csvNodeText);
        end

        function onTreeNodeCollapsed(app, csvNodeText)
            % Call this when a node is manually collapsed
            if ~isprop(app, 'ExpandedTreeNodes')
                app.ExpandedTreeNodes = string.empty;
            end

            app.ExpandedTreeNodes = app.ExpandedTreeNodes(~strcmp(app.ExpandedTreeNodes, csvNodeText));

            % DEBUG: Track collapse
            fprintf('Node collapsed: %s\n', csvNodeText);
        end
        function filterSignals(app, searchText)
            % Enhanced filter with auto-expand functionality

            % Clear existing tree
            delete(app.SignalTree.Children);

            if isempty(searchText)
                searchText = '';
            end

            hasFilteredResults = false;
            nodesToExpand = {};  % Keep track of nodes to expand

            % Process each CSV file
            for i = 1:numel(app.DataManager.CSVFilePaths)
                [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                csvDisplay = [csvName ext];
                T = app.DataManager.DataTables{i};
                if isempty(T), continue; end

                signals = setdiff(T.Properties.VariableNames, {'Time'});

                % Filter signals by search text
                filteredSignals = signals;
                if ~isempty(searchText)
                    mask = contains(lower(signals), lower(searchText));
                    filteredSignals = signals(mask);
                end

                % Only create CSV node if it has filtered signals OR no search is active
                if ~isempty(filteredSignals) || isempty(searchText)
                    csvNode = uitreenode(app.SignalTree, 'Text', csvDisplay);

                    % Add signals to this CSV node
                    for j = 1:numel(filteredSignals)
                        child = uitreenode(csvNode, 'Text', filteredSignals{j});
                        child.NodeData = struct('CSVIdx', i, 'Signal', filteredSignals{j});
                    end

                    % Mark for expansion if we have search results
                    if ~isempty(searchText) && ~isempty(filteredSignals)
                        nodesToExpand{end+1} = csvNode;
                        hasFilteredResults = true;
                    end
                end
            end

            % Add derived signals section if they exist
            if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations.DerivedSignals)
                derivedNames = keys(app.SignalOperations.DerivedSignals);

                % Filter derived signals
                filteredDerived = derivedNames;
                if ~isempty(searchText)
                    mask = contains(lower(derivedNames), lower(searchText));
                    filteredDerived = derivedNames(mask);
                end

                % Only create derived signals node if it has filtered signals OR no search is active
                if ~isempty(filteredDerived) || isempty(searchText)
                    derivedNode = uitreenode(app.SignalTree, 'Text', '⚙️ Derived Signals', ...
                        'NodeData', struct('Type', 'derived_signals_folder'));

                    for i = 1:length(filteredDerived)
                        signalName = filteredDerived{i};
                        derivedData = app.SignalOperations.DerivedSignals(signalName);

                        % Create icon based on operation type
                        switch derivedData.Operation.Type
                            case 'single'
                                if strcmp(derivedData.Operation.Operation, 'derivative')
                                    icon = '∂';
                                else
                                    icon = '∫';
                                end
                            case 'dual'
                                opIcons = containers.Map({'subtract', 'add', 'multiply', 'divide'}, {'−', '+', '×', '÷'});
                                if isKey(opIcons, derivedData.Operation.Operation)
                                    icon = opIcons(derivedData.Operation.Operation);
                                else
                                    icon = '⚙️';
                                end
                            case 'norm'
                                icon = '‖‖';
                            case {'quick_vector_magnitude', 'quick_moving_average', 'quick_fft', 'quick_rms', 'quick_average'}
                                icon = '⚡';
                            otherwise
                                icon = '🔄';
                        end

                        child = uitreenode(derivedNode, 'Text', sprintf('%s %s', icon, signalName));
                        child.NodeData = struct('CSVIdx', -1, 'Signal', signalName, 'IsDerived', true);

                        % Add context menu for derived signals
                        cm = uicontextmenu(app.UIFigure);
                        uimenu(cm, 'Text', '🗑️ Delete Signal', ...
                            'MenuSelectedFcn', @(src, event) app.SignalOperations.confirmDeleteDerivedSignal(signalName));
                        uimenu(cm, 'Text', '📋 Show Details', ...
                            'MenuSelectedFcn', @(src, event) app.SignalOperations.showOperationDetails(derivedData.Operation));
                        uimenu(cm, 'Text', '💾 Export Signal', ...
                            'MenuSelectedFcn', @(src, event) app.SignalOperations.exportDerivedSignal(signalName));
                        child.ContextMenu = cm;
                    end

                    % Mark for expansion if we have search results in derived signals
                    if ~isempty(searchText) && ~isempty(filteredDerived)
                        nodesToExpand{end+1} = derivedNode;
                        hasFilteredResults = true;
                    end
                end
            end

            % AUTO-EXPAND: Expand all nodes that have filtered results
            if hasFilteredResults && ~isempty(nodesToExpand)
                % Small delay to ensure tree is fully built
                pause(0.05);

                % Expand all marked nodes
                for i = 1:length(nodesToExpand)
                    try
                        nodesToExpand{i}.expand();
                    catch
                        % Ignore expansion errors - might not be supported in all MATLAB versions
                    end
                end

                % Force UI update
                drawnow;
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
        % =========================================================================
        % IMPROVED SESSION VALIDATION WITH DEBUGGING - Add to SignalViewerApp.m
        % =========================================================================

        function [isValid, errorDetails] = validateSessionData(obj)
            % Enhanced validation with detailed error reporting
            isValid = true;
            errorDetails = {};

            try
                % === CHECK 1: Essential Objects Exist ===
                if ~isprop(obj, 'DataManager') || isempty(obj.DataManager)
                    isValid = false;
                    errorDetails{end+1} = 'DataManager is missing or empty';
                elseif ~isvalid(obj.DataManager)
                    isValid = false;
                    errorDetails{end+1} = 'DataManager is not valid';
                end

                if ~isprop(obj, 'PlotManager') || isempty(obj.PlotManager)
                    isValid = false;
                    errorDetails{end+1} = 'PlotManager is missing or empty';
                elseif ~isvalid(obj.PlotManager)
                    isValid = false;
                    errorDetails{end+1} = 'PlotManager is not valid';
                end

                % === CHECK 2: DataManager Properties ===
                if isValid && isprop(obj, 'DataManager') && ~isempty(obj.DataManager)
                    % Check SignalNames
                    if ~isprop(obj.DataManager, 'SignalNames')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.SignalNames property missing';
                    elseif ~iscell(obj.DataManager.SignalNames)
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.SignalNames is not a cell array';
                    end

                    % Check DataTables
                    if ~isprop(obj.DataManager, 'DataTables')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.DataTables property missing';
                    elseif ~iscell(obj.DataManager.DataTables)
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.DataTables is not a cell array';
                    end

                    % Check CSVFilePaths
                    if ~isprop(obj.DataManager, 'CSVFilePaths')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.CSVFilePaths property missing';
                    elseif ~iscell(obj.DataManager.CSVFilePaths)
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.CSVFilePaths is not a cell array';
                    end

                    % Check SignalScaling
                    if ~isprop(obj.DataManager, 'SignalScaling')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.SignalScaling property missing';
                    elseif ~isa(obj.DataManager.SignalScaling, 'containers.Map')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.SignalScaling is not a containers.Map';
                    end

                    % Check StateSignals
                    if ~isprop(obj.DataManager, 'StateSignals')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.StateSignals property missing';
                    elseif ~isa(obj.DataManager.StateSignals, 'containers.Map')
                        isValid = false;
                        errorDetails{end+1} = 'DataManager.StateSignals is not a containers.Map';
                    end
                end

                % === CHECK 3: PlotManager Properties ===
                if isValid && isprop(obj, 'PlotManager') && ~isempty(obj.PlotManager)
                    % Check AssignedSignals
                    if ~isprop(obj.PlotManager, 'AssignedSignals')
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.AssignedSignals property missing';
                    elseif ~iscell(obj.PlotManager.AssignedSignals)
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.AssignedSignals is not a cell array';
                    end

                    % Check TabLayouts
                    if ~isprop(obj.PlotManager, 'TabLayouts')
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.TabLayouts property missing';
                    elseif ~iscell(obj.PlotManager.TabLayouts)
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.TabLayouts is not a cell array';
                    end

                    % Check CurrentTabIdx
                    if ~isprop(obj.PlotManager, 'CurrentTabIdx')
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.CurrentTabIdx property missing';
                    elseif ~isnumeric(obj.PlotManager.CurrentTabIdx)
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.CurrentTabIdx is not numeric';
                    end

                    % Check SelectedSubplotIdx
                    if ~isprop(obj.PlotManager, 'SelectedSubplotIdx')
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.SelectedSubplotIdx property missing';
                    elseif ~isnumeric(obj.PlotManager.SelectedSubplotIdx)
                        isValid = false;
                        errorDetails{end+1} = 'PlotManager.SelectedSubplotIdx is not numeric';
                    end
                end

                % === CHECK 4: Optional Components (don't fail if missing) ===
                % These are warnings, not failures
                if isprop(obj, 'SignalOperations') && ~isempty(obj.SignalOperations)
                    if ~isprop(obj.SignalOperations, 'DerivedSignals')
                        errorDetails{end+1} = 'Warning: SignalOperations.DerivedSignals missing';
                    elseif ~isa(obj.SignalOperations.DerivedSignals, 'containers.Map')
                        errorDetails{end+1} = 'Warning: SignalOperations.DerivedSignals is not a containers.Map';
                    end
                end

            catch ME
                isValid = false;
                errorDetails{end+1} = sprintf('Validation error: %s', ME.message);
            end
        end

        function debugSessionData(app)
            % Debug function to check what's wrong with session data
            fprintf('\n=== SESSION DATA DEBUG REPORT ===\n');

            % Check app object
            fprintf('App object: %s\n', class(app));

            % Check DataManager
            if isprop(app, 'DataManager')
                fprintf('DataManager exists: %s\n', mat2str(~isempty(app.DataManager)));
                if ~isempty(app.DataManager)
                    fprintf('DataManager valid: %s\n', mat2str(isvalid(app.DataManager)));
                    fprintf('DataManager class: %s\n', class(app.DataManager));

                    % Check DataManager properties
                    props = {'SignalNames', 'DataTables', 'CSVFilePaths', 'SignalScaling', 'StateSignals'};
                    for i = 1:length(props)
                        prop = props{i};
                        if isprop(app.DataManager, prop)
                            val = app.DataManager.(prop);
                            fprintf('  %s: %s (%s)\n', prop, mat2str(~isempty(val)), class(val));
                        else
                            fprintf('  %s: MISSING\n', prop);
                        end
                    end
                end
            else
                fprintf('DataManager: MISSING\n');
            end

            % Check PlotManager
            if isprop(app, 'PlotManager')
                fprintf('PlotManager exists: %s\n', mat2str(~isempty(app.PlotManager)));
                if ~isempty(app.PlotManager)
                    fprintf('PlotManager valid: %s\n', mat2str(isvalid(app.PlotManager)));
                    fprintf('PlotManager class: %s\n', class(app.PlotManager));

                    % Check PlotManager properties
                    props = {'AssignedSignals', 'TabLayouts', 'CurrentTabIdx', 'SelectedSubplotIdx'};
                    for i = 1:length(props)
                        prop = props{i};
                        if isprop(app.PlotManager, prop)
                            val = app.PlotManager.(prop);
                            fprintf('  %s: %s (%s)\n', prop, mat2str(~isempty(val)), class(val));
                        else
                            fprintf('  %s: MISSING\n', prop);
                        end
                    end
                end
            else
                fprintf('PlotManager: MISSING\n');
            end

            % Run validation and show results
            [isValid, errorDetails] = app.validateSessionData();
            fprintf('\nValidation Result: %s\n', mat2str(isValid));
            if ~isValid
                fprintf('Errors:\n');
                for i = 1:length(errorDetails)
                    fprintf('  %d. %s\n', i, errorDetails{i});
                end
            end

            fprintf('\n=== END DEBUG REPORT ===\n');
        end
        function saveSession(app)
            [file, path] = uiputfile('*.mat', 'Save Session');
            if isequal(file, 0), return; end

            try
                % === SKIP VALIDATION - JUST SAVE ===
                % Comment out or remove this validation block:
                % if ~app.DataManager.validateSessionData()
                %     answer = uiconfirm(app.UIFigure, ...
                %         'Session data validation failed. Continue saving anyway?', ...
                %         'Validation Failed', ...
                %         'Options', {'Save Anyway', 'Cancel'}, ...
                %         'DefaultOption', 'Cancel', 'Icon', 'warning');
                %
                %     if strcmp(answer, 'Cancel')
                %         app.restoreFocus();
                %         return;
                %     end
                % end

                session = struct();

                % === SAFE DATA EXTRACTION ===
                % Core data with error handling
                try
                    session.CSVFilePaths = app.DataManager.CSVFilePaths;
                catch
                    session.CSVFilePaths = {};
                end

                try
                    session.SignalScaling = app.DataManager.SignalScaling;
                catch
                    session.SignalScaling = containers.Map();
                end

                try
                    session.StateSignals = app.DataManager.StateSignals;
                catch
                    session.StateSignals = containers.Map();
                end

                try
                    session.SignalNames = app.DataManager.SignalNames;
                catch
                    session.SignalNames = {};
                end

                % === PLOT MANAGER DATA ===
                try
                    session.AssignedSignals = app.PlotManager.AssignedSignals;
                catch
                    session.AssignedSignals = {};
                end

                try
                    session.TabLayouts = app.PlotManager.TabLayouts;
                catch
                    session.TabLayouts = {[2, 1]};
                end

                try
                    session.CurrentTabIdx = app.PlotManager.CurrentTabIdx;
                catch
                    session.CurrentTabIdx = 1;
                end

                try
                    session.SelectedSubplotIdx = app.PlotManager.SelectedSubplotIdx;
                catch
                    session.SelectedSubplotIdx = 1;
                end

                % === TAB COUNT ===
                try
                    session.NumTabs = numel(app.PlotManager.TabLayouts);
                catch
                    session.NumTabs = 1;
                end

                % === TAB CONTROLS ===
                session.TabControlsData = {};
                try
                    if isprop(app.PlotManager, 'TabControls') && ~isempty(app.PlotManager.TabControls)
                        session.TabControlsData = cell(1, numel(app.PlotManager.TabControls));
                        for i = 1:numel(app.PlotManager.TabControls)
                            if ~isempty(app.PlotManager.TabControls{i})
                                session.TabControlsData{i} = struct(...
                                    'RowsValue', app.PlotManager.TabControls{i}.RowsSpinner.Value, ...
                                    'ColsValue', app.PlotManager.TabControls{i}.ColsSpinner.Value);
                            end
                        end
                    end
                catch
                    session.TabControlsData = {};
                end

                % === UI STATE (ALL OPTIONAL) ===
                session.SubplotMetadata = app.safeGetProperty('SubplotMetadata', {});
                session.SignalStyles = app.safeGetProperty('SignalStyles', struct());
                session.SubplotCaptions = app.safeGetProperty('SubplotCaptions', {});
                session.SubplotDescriptions = app.safeGetProperty('SubplotDescriptions', {});
                session.SubplotTitles = app.safeGetProperty('SubplotTitles', {});
                session.ExpandedTreeNodes = app.safeGetProperty('ExpandedTreeNodes', string.empty);

                % === DERIVED SIGNALS ===
                try
                    if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations)
                        session.DerivedSignals = app.SignalOperations.DerivedSignals;
                        session.OperationHistory = app.safeGetSubProperty(app.SignalOperations, 'OperationHistory', {});
                        session.OperationCounter = app.safeGetSubProperty(app.SignalOperations, 'OperationCounter', 0);
                    else
                        session.DerivedSignals = containers.Map();
                        session.OperationHistory = {};
                        session.OperationCounter = 0;
                    end
                catch
                    session.DerivedSignals = containers.Map();
                    session.OperationHistory = {};
                    session.OperationCounter = 0;
                end

                % === LINKING SYSTEM ===
                try
                    if isprop(app, 'LinkingManager') && ~isempty(app.LinkingManager)
                        session.LinkedGroups = app.safeGetSubProperty(app.LinkingManager, 'LinkedGroups', {});
                        session.AutoLinkEnabled = app.safeGetSubProperty(app.LinkingManager, 'AutoLinkEnabled', false);
                        session.LinkingMode = app.safeGetSubProperty(app.LinkingManager, 'LinkingMode', 'nodes');
                    else
                        session.LinkedGroups = {};
                        session.AutoLinkEnabled = false;
                        session.LinkingMode = 'nodes';
                    end
                catch
                    session.LinkedGroups = {};
                    session.AutoLinkEnabled = false;
                    session.LinkingMode = 'nodes';
                end

                % === APP PREFERENCES ===
                session.PDFReportTitle = app.safeGetProperty('PDFReportTitle', 'Signal Analysis Report');
                session.PDFReportAuthor = app.safeGetProperty('PDFReportAuthor', '');
                session.PDFFigureLabel = app.safeGetProperty('PDFFigureLabel', 'Figure');

                % === METADATA ===
                session.SessionVersion = '2.1';
                session.MatlabVersion = version();
                session.SaveTimestamp = datetime('now');

                % === SAVE ===
                save(fullfile(path, file), 'session', '-v7.3');

                app.StatusLabel.Text = sprintf('✅ Session saved: %s', file);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                app.StatusLabel.Text = sprintf('❌ Save failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                fprintf('Session save error: %s\n', ME.message);
            end

            app.restoreFocus();
        end

        function value = safeGetProperty(obj, varargin)
            % Safely get property value with default fallback
            % Usage: obj.safeGetProperty(propName, defaultValue)
            % OR:    obj.safeGetProperty(subObj, propName, defaultValue)

            try
                if nargin == 3  % obj.safeGetProperty(propName, defaultValue)
                    propName = varargin{1};
                    defaultValue = varargin{2};

                    if isprop(obj, propName) && ~isempty(obj.(propName))
                        value = obj.(propName);
                    else
                        value = defaultValue;
                    end

                elseif nargin == 4  % obj.safeGetProperty(subObj, propName, defaultValue)
                    subObj = varargin{1};
                    propName = varargin{2};
                    defaultValue = varargin{3};

                    if isprop(subObj, propName) && ~isempty(subObj.(propName))
                        value = subObj.(propName);
                    else
                        value = defaultValue;
                    end
                else
                    error('Invalid number of arguments');
                end
            catch
                if nargin >= 3
                    value = varargin{end};  % Use last argument as default
                else
                    value = [];
                end
            end
        end

        function loadSession(app)
            [file, path] = uigetfile('*.mat', 'Load Session');
            if isequal(file, 0), return; end

            try
                loaded = load(fullfile(path, file));
                if ~isfield(loaded, 'session')
                    app.StatusLabel.Text = '❌ Invalid session file format';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                session = loaded.session;

                % === RESTORE CSV DATA ===
                app.DataManager.CSVFilePaths = session.CSVFilePaths;
                app.DataManager.DataTables = cell(1, numel(session.CSVFilePaths));
                app.CSVColors = app.assignCSVColors(numel(session.CSVFilePaths));

                for i = 1:numel(session.CSVFilePaths)
                    if isfile(session.CSVFilePaths{i})
                        app.DataManager.readInitialData(i);
                    else
                        app.DataManager.DataTables{i} = [];
                    end
                end

                app.DataManager.SignalScaling = session.SignalScaling;
                app.DataManager.StateSignals = session.StateSignals;
                if isfield(session, 'SignalNames')
                    app.DataManager.SignalNames = session.SignalNames;
                end

                % === RESTORE DERIVED SIGNALS ===
                if isfield(session, 'DerivedSignals') && isprop(app, 'SignalOperations')
                    app.SignalOperations.DerivedSignals = session.DerivedSignals;

                    derivedNames = keys(session.DerivedSignals);
                    for i = 1:length(derivedNames)
                        if ~ismember(derivedNames{i}, app.DataManager.SignalNames)
                            app.DataManager.SignalNames{end+1} = derivedNames{i};
                        end
                    end

                    if isfield(session, 'OperationHistory')
                        app.SignalOperations.OperationHistory = session.OperationHistory;
                    end
                    if isfield(session, 'OperationCounter')
                        app.SignalOperations.OperationCounter = session.OperationCounter;
                    end
                end

                % === RESTORE LINKING SYSTEM ===
                if isfield(session, 'LinkedGroups') && isprop(app, 'LinkingManager')
                    app.LinkingManager.LinkedGroups = session.LinkedGroups;
                    if isfield(session, 'AutoLinkEnabled')
                        app.LinkingManager.AutoLinkEnabled = session.AutoLinkEnabled;
                    end
                    if isfield(session, 'LinkingMode')
                        app.LinkingManager.LinkingMode = session.LinkingMode;
                    end
                end

                % === CRITICAL: CREATE REQUIRED TABS FIRST ===
                requiredTabs = numel(session.TabLayouts);
                currentTabs = numel(app.PlotManager.PlotTabs);

                % Remove + tab temporarily if it exists
                plusTabIdx = [];
                for i = 1:numel(app.PlotManager.PlotTabs)
                    if strcmp(app.PlotManager.PlotTabs{i}.Title, '+')
                        plusTabIdx = i;
                        break;
                    end
                end

                if ~isempty(plusTabIdx)
                    delete(app.PlotManager.PlotTabs{plusTabIdx});
                    app.PlotManager.PlotTabs(plusTabIdx) = [];
                    currentTabs = currentTabs - 1;
                end

                % Create additional tabs if needed
                while numel(app.PlotManager.PlotTabs) < requiredTabs
                    app.PlotManager.addNewTab();
                end

                % === RESTORE PLOT MANAGER DATA ===
                app.PlotManager.TabLayouts = session.TabLayouts;
                app.PlotManager.AssignedSignals = session.AssignedSignals;
                app.PlotManager.CurrentTabIdx = min(session.CurrentTabIdx, requiredTabs);
                app.PlotManager.SelectedSubplotIdx = session.SelectedSubplotIdx;

                % === RECREATE EACH TAB WITH CORRECT LAYOUT ===
                for tabIdx = 1:requiredTabs
                    if tabIdx <= numel(session.TabLayouts)
                        layout = session.TabLayouts{tabIdx};
                        rows = layout(1);
                        cols = layout(2);

                        % Recreate subplots for this tab
                        app.PlotManager.createSubplotsForTab(tabIdx, rows, cols);

                        % Restore tab controls if available
                        if isfield(session, 'TabControlsData') && ...
                                tabIdx <= numel(session.TabControlsData) && ...
                                ~isempty(session.TabControlsData{tabIdx})

                            if tabIdx <= numel(app.PlotManager.TabControls) && ...
                                    ~isempty(app.PlotManager.TabControls{tabIdx})
                                app.PlotManager.TabControls{tabIdx}.RowsSpinner.Value = rows;
                                app.PlotManager.TabControls{tabIdx}.ColsSpinner.Value = cols;
                            end
                        end
                    end
                end

                % === RESTORE UI STATE ===
                if isfield(session, 'SubplotMetadata')
                    app.SubplotMetadata = session.SubplotMetadata;
                end
                if isfield(session, 'SignalStyles')
                    app.SignalStyles = session.SignalStyles;
                end
                if isfield(session, 'SubplotCaptions')
                    app.SubplotCaptions = session.SubplotCaptions;
                end
                if isfield(session, 'SubplotDescriptions')
                    app.SubplotDescriptions = session.SubplotDescriptions;
                end
                if isfield(session, 'SubplotTitles')
                    app.SubplotTitles = session.SubplotTitles;
                end
                if isfield(session, 'ExpandedTreeNodes')
                    app.ExpandedTreeNodes = session.ExpandedTreeNodes;
                end
                if isfield(session, 'PDFReportTitle')
                    app.PDFReportTitle = session.PDFReportTitle;
                end
                if isfield(session, 'PDFReportAuthor')
                    app.PDFReportAuthor = session.PDFReportAuthor;
                end
                if isfield(session, 'PDFFigureLabel')
                    app.PDFFigureLabel = session.PDFFigureLabel;
                end

                % === REBUILD UI AND REFRESH ===
                app.buildSignalTree();

                % Refresh plots for all tabs
                for tabIdx = 1:requiredTabs
                    app.PlotManager.refreshPlots(tabIdx);
                end

                % Auto-scale and restore current tab
                app.autoScaleAllTabs();
                app.PlotManager.ensurePlusTabAtEnd();
                app.PlotManager.updateTabTitles();

                % Set current tab
                if app.PlotManager.CurrentTabIdx <= numel(app.PlotManager.PlotTabs)
                    app.MainTabGroup.SelectedTab = app.PlotManager.PlotTabs{app.PlotManager.CurrentTabIdx};
                end

                app.StatusLabel.Text = sprintf('✅ Session loaded: %s', file);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                app.StatusLabel.Text = sprintf('❌ Load failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                fprintf('Session load error: %s\n', ME.message);
                for i = 1:length(ME.stack)
                    fprintf('  %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
                end
            end

            app.restoreFocus();
        end

        function showSessionLoadSummary(obj, session, missingCSVs)
            % Show summary of what was loaded in the session
            summary = sprintf('Session Load Summary:\n\n');
            summary = [summary sprintf('• CSV Files: %d loaded', numel(session.CSVFilePaths))];
            if ~isempty(missingCSVs)
                summary = [summary sprintf(' (%d missing)', numel(missingCSVs))];
            end
            summary = [summary sprintf('\n• Tabs: %d', numel(session.TabLayouts))];
            summary = [summary sprintf('\n• Signal Assignments: %d tabs configured', numel(session.AssignedSignals))];
            if isfield(session, 'DerivedSignals')
                derivedCount = length(keys(session.DerivedSignals));
                summary = [summary sprintf('\n• Derived Signals: %d restored', derivedCount)];
            end
            if isfield(session, 'LinkedGroups')
                summary = [summary sprintf('\n• Link Groups: %d restored', numel(session.LinkedGroups))];
            end

            uialert(obj.UIFigure, summary, 'Session Loaded Successfully', 'Icon', 'success');
        end


        function newPaths = browseForMissingCSVs(obj, originalPaths)
            % Interactive dialog to browse for missing CSV files
            newPaths = originalPaths;
            for i = 1:numel(originalPaths)
                if ~isfile(originalPaths{i})
                    [~, fileName, ext] = fileparts(originalPaths{i});
                    [file, path] = uigetfile('*.csv', sprintf('Locate missing file: %s%s', fileName, ext));
                    if ~isequal(file, 0)
                        newPaths{i} = fullfile(path, file);
                    end
                end
            end
        end

        function checksum = calculateSessionChecksum(obj, session)
            % Generate a simple checksum for session integrity
            try
                % Create a string representation of key fields
                keyFields = {'CSVFilePaths', 'AssignedSignals', 'TabLayouts'};
                checksumData = '';
                for i = 1:length(keyFields)
                    if isfield(session, keyFields{i})
                        checksumData = [checksumData, mat2str(session.(keyFields{i}))];
                    end
                end
                checksum = num2str(java.lang.String(checksumData).hashCode());
            catch
                checksum = 'unknown';
            end
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

        function setupMultiSelectionContextMenu(app)
            % Create a persistent context menu for the tree
            app.SignalTree.ContextMenu = uicontextmenu(app.UIFigure);

            % Set up the context menu opening function
            app.SignalTree.ContextMenu.ContextMenuOpeningFcn = @(src, event) app.onTreeContextMenuOpening();
        end

        function onTreeContextMenuOpening(app)
            % Get selected nodes
            selectedNodes = app.SignalTree.SelectedNodes;

            % Clear existing menu items
            delete(app.SignalTree.ContextMenu.Children);

            if isempty(selectedNodes)
                % No selection - show general options
                uimenu(app.SignalTree.ContextMenu, 'Text', 'No signals selected', 'Enable', 'off');
                return;
            end

            % Get actual signal nodes (not folders)
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData; %#ok<AGROW>
                end
            end

            if isempty(selectedSignals)
                uimenu(app.SignalTree.ContextMenu, 'Text', 'No signals selected', 'Enable', 'off');
                return;
            end

            % Get current assignments to determine what actions are available
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            currentAssignments = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            % FIXED: Separate the signals more carefully
            assignedSignals = {};
            unassignedSignals = {};

            for i = 1:numel(selectedSignals)
                isAssigned = false;
                signalInfo = selectedSignals{i};

                % More robust comparison
                for j = 1:numel(currentAssignments)
                    currentSignal = currentAssignments{j};
                    if isstruct(currentSignal) && isstruct(signalInfo) && ...
                            isfield(currentSignal, 'CSVIdx') && isfield(signalInfo, 'CSVIdx') && ...
                            isfield(currentSignal, 'Signal') && isfield(signalInfo, 'Signal') && ...
                            currentSignal.CSVIdx == signalInfo.CSVIdx && ...
                            strcmp(currentSignal.Signal, signalInfo.Signal)
                        isAssigned = true;
                        break;
                    end
                end

                if isAssigned
                    assignedSignals{end+1} = selectedSignals{i};
                else
                    unassignedSignals{end+1} = selectedSignals{i};
                end
            end

            % Create appropriate menu items
            if ~isempty(unassignedSignals)
                if numel(unassignedSignals) == 1
                    uimenu(app.SignalTree.ContextMenu, 'Text', '➕ Add to Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.addSelectedSignalsToSubplot(unassignedSignals));
                else
                    uimenu(app.SignalTree.ContextMenu, 'Text', sprintf('➕ Add %d Signals to Subplot', numel(unassignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.addSelectedSignalsToSubplot(unassignedSignals));
                end
            end

            if ~isempty(assignedSignals)
                if numel(assignedSignals) == 1
                    uimenu(app.SignalTree.ContextMenu, 'Text', '❌ Remove from Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.removeSelectedSignalsFromSubplot(assignedSignals));
                else
                    uimenu(app.SignalTree.ContextMenu, 'Text', sprintf('❌ Remove %d Signals from Subplot', numel(assignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.removeSelectedSignalsFromSubplot(assignedSignals));
                end
            end

            % Preview option
            if numel(selectedSignals) == 1
                uimenu(app.SignalTree.ContextMenu, 'Text', '📊 Quick Preview', ...
                    'MenuSelectedFcn', @(src, event) app.showSignalPreview(selectedSignals{1}), ...
                    'Separator', 'on');
            else
                uimenu(app.SignalTree.ContextMenu, 'Text', sprintf('📊 Preview %d Signals', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.previewSelectedSignals(selectedSignals), ...
                    'Separator', 'on');
            end
        end
        function removeSelectedSignalsFromSubplot(app, signalsToRemove)
            if isempty(signalsToRemove)
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Remove all specified signals
            newAssignments = {};
            removedCount = 0;

            for i = 1:numel(currentAssignments)
                shouldKeep = true;
                for j = 1:numel(signalsToRemove)
                    if isequal(currentAssignments{i}, signalsToRemove{j})
                        shouldKeep = false;
                        removedCount = removedCount + 1;
                        break;
                    end
                end

                if shouldKeep
                    newAssignments{end+1} = currentAssignments{i};
                end
            end

            % Update assignments
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);

            % Keep showing properties of selected signals (not just assigned ones)
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData;
                end
            end
            app.updateSignalPropsTable(selectedSignals);

            if removedCount > 0
                app.StatusLabel.Text = sprintf('❌ Removed %d signal(s) from subplot', removedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'No selected signals were assigned';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end

        % Add selected signals to current subplot
        function addSelectedSignals(app)
            selectedNodes = app.SignalTree.SelectedNodes;

            % Get signal info from selected nodes
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData; %#ok<AGROW>
                end
            end

            if isempty(selectedSignals)
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Add only signals that aren't already assigned
            addedCount = 0;
            for i = 1:numel(selectedSignals)
                signalInfo = selectedSignals{i};

                % Check if already assigned
                alreadyAssigned = false;
                for j = 1:numel(currentAssignments)
                    if isequal(currentAssignments{j}, signalInfo)
                        alreadyAssigned = true;
                        break;
                    end
                end

                if ~alreadyAssigned
                    currentAssignments{end+1} = signalInfo;
                    addedCount = addedCount + 1;
                end
            end

            % Update assignments
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = currentAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(currentAssignments);

            if addedCount > 0
                app.StatusLabel.Text = sprintf('➕ Added %d signal(s) to subplot', addedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'All selected signals already assigned';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end


        function addSelectedSignalsToSubplot(app, signalsToAdd)
            if isempty(signalsToAdd)
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Add all signals that aren't already assigned
            addedCount = 0;
            for i = 1:numel(signalsToAdd)
                signalInfo = signalsToAdd{i};

                % Check if already assigned
                alreadyAssigned = false;
                for j = 1:numel(currentAssignments)
                    if isequal(currentAssignments{j}, signalInfo)
                        alreadyAssigned = true;
                        break;
                    end
                end

                if ~alreadyAssigned
                    currentAssignments{end+1} = signalInfo;
                    addedCount = addedCount + 1;

                    % NEW: Apply linking for this signal
                    if isprop(app, 'LinkingManager') && ~isempty(app.LinkingManager)
                        app.LinkingManager.applyLinking(signalInfo);
                    end
                end
            end

            % Update assignments
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = currentAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);

            % Update signal properties table
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData;
                end
            end
            app.updateSignalPropsTable(selectedSignals);

            if addedCount > 0
                app.StatusLabel.Text = sprintf('➕ Added %d signal(s) to subplot', addedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'All selected signals already assigned';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end
        % Remove selected signals from current subplot
        function removeSelectedSignals(app)
            selectedNodes = app.SignalTree.SelectedNodes;

            % Get signal info from selected nodes
            selectedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData; %#ok<AGROW>
                end
            end

            if isempty(selectedSignals)
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Remove selected signals
            newAssignments = {};
            removedCount = 0;

            for i = 1:numel(currentAssignments)
                shouldKeep = true;
                for j = 1:numel(selectedSignals)
                    if isequal(currentAssignments{i}, selectedSignals{j})
                        shouldKeep = false;
                        removedCount = removedCount + 1;
                        break;
                    end
                end

                if shouldKeep
                    newAssignments{end+1} = currentAssignments{i};
                end
            end

            % Update assignments
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = newAssignments;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(newAssignments);

            if removedCount > 0
                app.StatusLabel.Text = sprintf('❌ Removed %d signal(s) from subplot', removedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'No selected signals were assigned';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end

        % Preview multiple selected signals
        function previewSelectedSignals(app, signalsToPreview)
            if isempty(signalsToPreview)
                return;
            end

            % Create preview figure with subplots
            numSignals = numel(signalsToPreview);
            rows = ceil(sqrt(numSignals));
            cols = ceil(numSignals / rows);

            fig = figure('Name', sprintf('Preview: %d Selected Signals', numSignals), ...
                'Position', [100 100 1200 800]);

            for i = 1:numSignals
                signalInfo = signalsToPreview{i};

                try
                    % FIXED: Use SignalOperationsManager.getSignalData for both regular and derived signals
                    if signalInfo.CSVIdx == -1
                        % Derived signal - use SignalOperations to get data
                        [timeData, signalData] = app.SignalOperations.getSignalData(signalInfo.Signal);
                        signalSource = sprintf('Derived');
                    else
                        % Regular CSV signal - use DataManager
                        T = app.DataManager.DataTables{signalInfo.CSVIdx};
                        if isempty(T) || ~ismember(signalInfo.Signal, T.Properties.VariableNames)
                            continue;
                        end

                        timeData = T.Time;
                        signalData = T.(signalInfo.Signal);
                        signalSource = sprintf('CSV %d', signalInfo.CSVIdx);

                        % Apply scaling if exists
                        if app.DataManager.SignalScaling.isKey(signalInfo.Signal)
                            signalData = signalData * app.DataManager.SignalScaling(signalInfo.Signal);
                        end

                        % Remove NaN values
                        validIdx = ~isnan(signalData);
                        timeData = timeData(validIdx);
                        signalData = signalData(validIdx);
                    end

                    if isempty(timeData)
                        continue;
                    end

                    % Create subplot
                    subplot(rows, cols, i);

                    % Get color if custom color is set
                    plotColor = [0 0.4470 0.7410]; % default
                    if ~isempty(app.SignalStyles) && isfield(app.SignalStyles, signalInfo.Signal)
                        if isfield(app.SignalStyles.(signalInfo.Signal), 'Color')
                            plotColor = app.SignalStyles.(signalInfo.Signal).Color;
                        end
                    end

                    plot(timeData, signalData, 'LineWidth', 1.5, 'Color', plotColor);
                    title(sprintf('%s (%s)', signalInfo.Signal, signalSource), 'FontSize', 10);
                    xlabel('Time');
                    ylabel('Value');
                    grid on;

                catch ME
                    % Skip signals that can't be plotted
                    fprintf('Warning: Could not preview signal %s: %s\n', signalInfo.Signal, ME.message);
                end
            end

            app.StatusLabel.Text = sprintf('📊 Previewing %d selected signals', numSignals);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
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
        function menuExportToPlotBrowser(app)
            app.PlotManager.exportTabsToPlotBrowser();
        end
        function menuStatistics(app)
            app.UIController.showStatsDialog();
            figure(app.UIFigure);
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