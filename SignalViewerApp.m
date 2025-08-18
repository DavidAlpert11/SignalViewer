% Updated SignalViewerApp.m - Main changes for light mode and streaming - REMOVED REDUNDANT DRAWNOW
classdef SignalViewerApp < matlab.apps.AppBase
    properties
        % Main UI
        RemoveSelectedSignalsButton
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
        ResetZoomButton
        CSVPathField
        AutoScaleCheckbox
        StatusLabel
        DataRateLabel
        CursorState = false

        % Visual Enhancement Properties
        SubplotHighlightBoxes
        CurrentHighlightColor = [0.2 0.8 0.4]  % Green highlight color


        % === PDF Defaults ===
        PDFReportTitle  = 'Signal Analysis Report';
        PDFReportAuthor = '';
        PDFReportDate   = datetime('now');
        PDFFigureLabel  = 'Figure';   % <-- this was your new line

        % === PPT Defaults ===
        PPTReportTitle  = 'Signal Analysis Report';
        PPTReportAuthor = '';
        PPTReportDate   = datetime('now');
        PPTFigureLabel  = 'Figure';   % same idea for PPT
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

function populateCSVContextMenu(app, contextMenu, clickedCSVIndex)
    % Dynamically populate CSV context menu based on selection

    % Clear existing menu items
    delete(contextMenu.Children);

    % Get all selected CSV nodes
    selectedNodes = app.SignalTree.SelectedNodes;
    selectedCSVIndices = [];

    % Find CSV nodes by matching text to CSV filenames
    for i = 1:numel(selectedNodes)
        node = selectedNodes(i);

        % Check if this is a CSV folder node
        if isstruct(node.NodeData) && isfield(node.NodeData, 'Type') && ...
                strcmp(node.NodeData.Type, 'csv_folder') && ...
                isfield(node.NodeData, 'CSVIdx')
            % Direct CSV index from NodeData
            csvIdx = node.NodeData.CSVIdx;
            if csvIdx > 0 && csvIdx <= length(app.DataManager.CSVFilePaths)
                selectedCSVIndices(end+1) = csvIdx;
            end
        else
            % Try to find CSV index by matching the node text to CSV file names
            csvIdx = app.findCSVIndexByName(node.Text);
            if csvIdx > 0
                selectedCSVIndices(end+1) = csvIdx;
            end
        end
    end

    % If no CSV nodes found, use the clicked CSV
    if isempty(selectedCSVIndices) && clickedCSVIndex > 0
        selectedCSVIndices = clickedCSVIndex;
    end

    % Remove duplicates and sort
    selectedCSVIndices = unique(selectedCSVIndices);
    numSelectedCSVs = length(selectedCSVIndices);

    if numSelectedCSVs == 0
        uimenu(contextMenu, 'Text', '⚠️ No valid CSV selected', 'Enable', 'off');
        return;
    end

    % Get CSV names for display
    csvNames = {};
    for i = 1:length(selectedCSVIndices)
        csvIdx = selectedCSVIndices(i);
        if csvIdx <= length(app.DataManager.CSVFilePaths)
            [~, name, ext] = fileparts(app.DataManager.CSVFilePaths{csvIdx});
            csvNames{end+1} = [name ext];
        end
    end

    % ========== ADD THESE LINES: LINKING OPTIONS ==========
    if numSelectedCSVs >= 2
        % Multiple CSVs - show create link option
        uimenu(contextMenu, 'Text', sprintf('🔗 Create Link Group (%d CSVs)', numSelectedCSVs), ...
            'MenuSelectedFcn', @(src, event) app.createQuickLinkFromCSVs(selectedCSVIndices));
%         uimenu(contextMenu, 'Text', '', 'Separator', 'on');
    end
    % ========== END LINKING OPTIONS ==========

    if numSelectedCSVs == 1
        % Single CSV selected - show individual options
        csvIdx = selectedCSVIndices(1);
        csvName = csvNames{1};

        uimenu(contextMenu, 'Text', '📌 Assign All to Current Subplot', ...
            'MenuSelectedFcn', @(src, event) app.assignAllSignalsFromCSV(csvIdx));
        uimenu(contextMenu, 'Text', '❌ Remove All from Current Subplot', ...
            'MenuSelectedFcn', @(src, event) app.removeAllSignalsFromCSV(csvIdx));
        uimenu(contextMenu, 'Text', '⚙️ Bulk Edit Properties', ...
            'MenuSelectedFcn', @(src, event) app.bulkEditSignalProperties(csvIdx), 'Separator', 'on');

        uimenu(contextMenu, 'Text', sprintf('🗑️ Delete "%s"', csvName), ...
            'MenuSelectedFcn', @(src, event) app.deleteCSVFromSystem(csvIdx), ...
            'Separator', 'on', 'ForegroundColor', [0.8 0.2 0.2]);

    else
        % Multiple CSVs selected - show bulk options
        uimenu(contextMenu, 'Text', sprintf('📌 Assign All Signals from %d CSVs', numSelectedCSVs), ...
            'MenuSelectedFcn', @(src, event) app.assignAllSignalsFromMultipleCSVs(selectedCSVIndices));
        uimenu(contextMenu, 'Text', sprintf('❌ Remove All Signals from %d CSVs', numSelectedCSVs), ...
            'MenuSelectedFcn', @(src, event) app.removeAllSignalsFromMultipleCSVs(selectedCSVIndices));

        % Create deletion menu text with CSV names
        if numSelectedCSVs <= 3
            % Show all names if 3 or fewer
            csvNamesStr = strjoin(csvNames, '", "');
            deleteText = sprintf('🗑️ Delete "%s"', csvNamesStr);
        else
            % Show first 2 names + "and X more" if more than 3
            csvNamesStr = strjoin(csvNames(1:2), '", "');
            deleteText = sprintf('🗑️ Delete "%s" and %d more', csvNamesStr, numSelectedCSVs - 2);
        end

        uimenu(contextMenu, 'Text', deleteText, ...
            'MenuSelectedFcn', @(src, event) app.deleteMultipleCSVsFromSystem(selectedCSVIndices), ...
            'Separator', 'on', 'ForegroundColor', [0.8 0.2 0.2]);
    end

    % Common options
    uimenu(contextMenu, 'Text', '👁️ Manage Hidden Signals', ...
        'MenuSelectedFcn', @(src, event) app.showHiddenSignalsManager(), 'Separator', 'on');

    % Selection info
    if numSelectedCSVs > 1
        % Show selected CSV names in info section
        if numSelectedCSVs <= 5
            infoText = sprintf('📋 Selected: %s', strjoin(csvNames, ', '));
        else
            infoText = sprintf('📋 %d CSVs selected: %s, ...', numSelectedCSVs, strjoin(csvNames(1:3), ', '));
        end

        uimenu(contextMenu, 'Text', infoText, ...
            'Enable', 'off', 'Separator', 'on');
    end
end

% ========== ADD ONLY THIS ONE METHOD ==========
function createQuickLinkFromCSVs(app, selectedCSVIndices)
    % Simple method to create link using existing LinkingManager
    try
        if isprop(app, 'LinkingManager') && ~isempty(app.LinkingManager)
            % Create new group using existing LinkingManager method
            newGroup = struct();
            newGroup.Type = 'nodes';
            newGroup.CSVIndices = selectedCSVIndices;
            
            % Generate simple name
            newGroup.Name = sprintf('Quick Link %d (%d CSVs)', ...
                length(app.LinkingManager.LinkedGroups) + 1, length(selectedCSVIndices));
            
            % Use existing color logic
            if isempty(app.LinkingManager.LinkColors)
                app.LinkingManager.LinkColors = [
                    0.9 0.2 0.2; 0.2 0.9 0.2; 0.2 0.2 0.9; 
                    0.9 0.9 0.2; 0.9 0.2 0.9; 0.2 0.9 0.9];
            end
            colorIdx = mod(length(app.LinkingManager.LinkedGroups), size(app.LinkingManager.LinkColors, 1)) + 1;
            newGroup.Color = app.LinkingManager.LinkColors(colorIdx, :);
            
            % Add to linked groups
            app.LinkingManager.LinkedGroups{end+1} = newGroup;
            app.LinkingManager.AutoLinkEnabled = true;
            
            % Update status
            app.StatusLabel.Text = sprintf('✅ Created link group with %d CSVs', length(selectedCSVIndices));
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        else
            uialert(app.UIFigure, 'LinkingManager not available.', 'Error');
        end
    catch ME
        uialert(app.UIFigure, sprintf('Failed to create link: %s', ME.message), 'Error');
    end
end

        function csvIdx = findCSVIndexByName(app, nodeText)
            % Find CSV index by matching the node text to CSV file names
            csvIdx = 0;

            for i = 1:length(app.DataManager.CSVFilePaths)
                [~, name, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                if strcmp(nodeText, [name ext])
                    csvIdx = i;
                    return;
                end
            end
        end
        function assignAllSignalsFromMultipleCSVs(app, csvIndices)
            % Assign all signals from multiple CSVs to current subplot

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Collect all signals from selected CSVs
            allSignals = {};
            totalSignalCount = 0;

            for i = 1:length(csvIndices)
                csvIdx = csvIndices(i);
                if csvIdx <= length(app.DataManager.DataTables) && ~isempty(app.DataManager.DataTables{csvIdx})
                    T = app.DataManager.DataTables{csvIdx};
                    signals = setdiff(T.Properties.VariableNames, {'Time'});

                    for j = 1:length(signals)
                        signalInfo = struct('CSVIdx', csvIdx, 'Signal', signals{j});
                        allSignals{end+1} = signalInfo;
                        totalSignalCount = totalSignalCount + 1;
                    end
                end
            end

            if isempty(allSignals)
                app.StatusLabel.Text = '⚠️ No signals found in selected CSVs';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Replace current assignments with all collected signals
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = allSignals;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(allSignals);

            app.StatusLabel.Text = sprintf('📌 Assigned %d signals from %d CSVs', totalSignalCount, length(csvIndices));
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function removeAllSignalsFromMultipleCSVs(app, csvIndices)
            % Remove all signals from multiple CSVs from current subplot

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Filter out signals from selected CSVs
            filteredSignals = {};
            removedCount = 0;

            for i = 1:numel(currentAssignments)
                signal = currentAssignments{i};
                shouldKeep = true;

                % Check if this signal is from any of the selected CSVs
                if ismember(signal.CSVIdx, csvIndices)
                    shouldKeep = false;
                    removedCount = removedCount + 1;
                end

                if shouldKeep
                    filteredSignals{end+1} = signal;
                end
            end

            % Update assignments
            app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = filteredSignals;

            % Refresh visuals
            app.buildSignalTree();
            app.PlotManager.refreshPlots(tabIdx);
            app.updateSignalPropsTable(filteredSignals);

            app.StatusLabel.Text = sprintf('❌ Removed %d signals from %d CSVs', removedCount, length(csvIndices));
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function deleteCSVFromSystem(app, csvIndex)
            % Delete a single CSV from the system
            app.deleteMultipleCSVsFromSystem([csvIndex]);
        end

        function deleteMultipleCSVsFromSystem(app, csvIndices)
            % Delete multiple CSVs from the system
            if isempty(csvIndices)
                return;
            end

            % Get CSV information for confirmation
            csvNames = {};
            totalSignals = 0;

            for i = 1:length(csvIndices)
                idx = csvIndices(i);
                if idx <= length(app.DataManager.CSVFilePaths)
                    [~, name, ext] = fileparts(app.DataManager.CSVFilePaths{idx});
                    csvNames{end+1} = [name ext];

                    % Count signals in this CSV
                    if idx <= length(app.DataManager.DataTables) && ~isempty(app.DataManager.DataTables{idx})
                        signals = setdiff(app.DataManager.DataTables{idx}.Properties.VariableNames, {'Time'});
                        totalSignals = totalSignals + length(signals);
                    end
                end
            end

            if isempty(csvNames)
                app.StatusLabel.Text = '⚠️ No valid CSVs selected for deletion';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Create confirmation message
            if length(csvIndices) == 1
                confirmMsg = sprintf(['Delete CSV file from system?\n\n' ...
                    'CSV: %s\n' ...
                    'Signals: %d\n\n' ...
                    'This will:\n' ...
                    '• Remove all signals from all subplots\n' ...
                    '• Clear all related data from memory\n' ...
                    '• Stop any streaming for this CSV\n\n' ...
                    'This action cannot be undone!'], ...
                    csvNames{1}, totalSignals);
                confirmTitle = 'Confirm CSV Deletion';
            else
                confirmMsg = sprintf(['Delete %d CSV files from system?\n\n' ...
                    'CSVs: %s\n' ...
                    'Total Signals: %d\n\n' ...
                    'This will:\n' ...
                    '• Remove all signals from all subplots\n' ...
                    '• Clear all related data from memory\n' ...
                    '• Stop any streaming for these CSVs\n\n' ...
                    'This action cannot be undone!'], ...
                    length(csvIndices), strjoin(csvNames, ', '), totalSignals);
                confirmTitle = 'Confirm Multiple CSV Deletion';
            end

            % Show confirmation dialog
            answer = uiconfirm(app.UIFigure, confirmMsg, confirmTitle, ...
                'Options', {'Delete', 'Cancel'}, ...
                'DefaultOption', 'Cancel', ...
                'Icon', 'warning');

            if strcmp(answer, 'Cancel')
                return;
            end

            % Perform deletion
            try
                app.performCSVDeletion(csvIndices);

                % Update status
                if length(csvIndices) == 1
                    app.StatusLabel.Text = sprintf('🗑️ Deleted CSV: %s (%d signals)', csvNames{1}, totalSignals);
                else
                    app.StatusLabel.Text = sprintf('🗑️ Deleted %d CSVs (%d total signals)', length(csvIndices), totalSignals);
                end
                app.StatusLabel.FontColor = [0.9 0.3 0.3];

            catch ME
                app.StatusLabel.Text = sprintf('❌ CSV deletion failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                fprintf('CSV deletion error: %s\n', ME.message);
            end
        end

        function performCSVDeletion(app, csvIndices)
            % Perform the actual CSV deletion process

            % Sort indices in descending order to maintain proper indexing during deletion
            csvIndices = sort(csvIndices, 'descend');

            % 1. Stop streaming for the CSVs being deleted
            for i = 1:length(csvIndices)
                idx = csvIndices(i);
                if idx <= length(app.DataManager.CSVFilePaths)
                    try
                        app.DataManager.stopStreaming(idx);
                    catch
                        % Ignore streaming stop errors
                    end
                end
            end

            % 2. Collect signals to be removed from all CSVs being deleted
            signalsToRemove = {};
            for i = 1:length(csvIndices)
                idx = csvIndices(i);
                if idx <= length(app.DataManager.DataTables) && ~isempty(app.DataManager.DataTables{idx})
                    T = app.DataManager.DataTables{idx};
                    signals = setdiff(T.Properties.VariableNames, {'Time'});
                    for j = 1:length(signals)
                        signalInfo = struct('CSVIdx', idx, 'Signal', signals{j});
                        signalsToRemove{end+1} = signalInfo;
                    end
                end
            end

            % 3. Remove all signals from all subplots
            if ~isempty(signalsToRemove)
                app.removeSignalsFromAllSubplots(signalsToRemove);
            end

            % 4. Remove signals from scaling and state maps
            for i = 1:length(signalsToRemove)
                signalName = signalsToRemove{i}.Signal;
                if app.DataManager.SignalScaling.isKey(signalName)
                    app.DataManager.SignalScaling.remove(signalName);
                end
                if app.DataManager.StateSignals.isKey(signalName)
                    app.DataManager.StateSignals.remove(signalName);
                end

                % Remove from signal styles if exists
                if ~isempty(app.SignalStyles) && isfield(app.SignalStyles, signalName)
                    app.SignalStyles = rmfield(app.SignalStyles, signalName);
                end

                % Remove from hidden signals if exists
                if isprop(app, 'HiddenSignals') && ~isempty(app.HiddenSignals)
                    signalKey = app.getSignalKey(signalsToRemove{i});
                    if app.HiddenSignals.isKey(signalKey)
                        app.HiddenSignals.remove(signalKey);
                    end
                end
            end

            % 5. Delete CSV data and file paths (in reverse order to maintain indices)
            for i = 1:length(csvIndices)
                idx = csvIndices(i);

                % Remove from DataTables
                if idx <= length(app.DataManager.DataTables)
                    app.DataManager.DataTables(idx) = [];
                end

                % Remove from CSVFilePaths
                if idx <= length(app.DataManager.CSVFilePaths)
                    app.DataManager.CSVFilePaths(idx) = [];
                end

                % Remove from LastReadRows if it exists
                if isprop(app.DataManager, 'LastReadRows') && idx <= length(app.DataManager.LastReadRows)
                    app.DataManager.LastReadRows(idx) = [];
                end

                % Remove from CSVColors if it exists
                if isprop(app, 'CSVColors') && idx <= length(app.CSVColors)
                    app.CSVColors(idx) = [];
                end
            end

            % 6. Update CSV indices in all remaining assignments
            app.updateCSVIndicesAfterDeletion(csvIndices);

            % 7. Rebuild signal names list using existing method
            app.DataManager.updateSignalNamesAfterClear();

            % 8. Refresh UI
            app.buildSignalTree();
            % 9. Refresh all plots in all tabs - FIXED METHOD CALL
            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                if ~isempty(app.PlotManager.AxesArrays{tabIdx})
                    app.PlotManager.refreshPlots(tabIdx);
                end
            end

            % 10. Clear signal properties table if it was showing deleted signals
            app.SignalPropsTable.Data = {};
            app.RemoveSelectedSignalsButton.Enable = 'off';
        end

        function removeSignalsFromAllSubplots(app, signalsToRemove)
            % Remove specified signals from all subplots in all tabs

            numTabs = numel(app.PlotManager.AxesArrays);

            for tabIdx = 1:numTabs
                if tabIdx > numel(app.PlotManager.AssignedSignals)
                    continue;
                end

                if ~isempty(app.PlotManager.AxesArrays{tabIdx})
                    numSubplots = numel(app.PlotManager.AxesArrays{tabIdx});
                else
                    continue;
                end

                for subplotIdx = 1:numSubplots
                    if subplotIdx > numel(app.PlotManager.AssignedSignals{tabIdx})
                        continue;
                    end

                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                    if isempty(assignedSignals)
                        continue;
                    end

                    % Filter out signals that should be removed
                    filteredSignals = {};
                    for i = 1:numel(assignedSignals)
                        signal = assignedSignals{i};
                        shouldKeep = true;

                        for j = 1:numel(signalsToRemove)
                            if isequal(signal, signalsToRemove{j})
                                shouldKeep = false;
                                break;
                            end
                        end

                        if shouldKeep
                            filteredSignals{end+1} = signal;
                        end
                    end

                    % Update the assignments for this subplot
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = filteredSignals;
                end
            end

            % Also remove from X-axis assignments
            if isprop(app.PlotManager, 'XAxisSignals') && ~isempty(app.PlotManager.XAxisSignals)
                for tabIdx = 1:size(app.PlotManager.XAxisSignals, 1)
                    for subplotIdx = 1:size(app.PlotManager.XAxisSignals, 2)
                        if ~isempty(app.PlotManager.XAxisSignals{tabIdx, subplotIdx})
                            currentXAxis = app.PlotManager.XAxisSignals{tabIdx, subplotIdx};
                            for j = 1:numel(signalsToRemove)
                                if isequal(currentXAxis, signalsToRemove{j})
                                    app.PlotManager.XAxisSignals{tabIdx, subplotIdx} = [];
                                    break;
                                end
                            end
                        end
                    end
                end
            end
        end

        function updateCSVIndicesAfterDeletion(app, deletedIndices)
            % Update CSV indices in all assignments after CSV deletion

            % Create mapping from old indices to new indices
            oldToNewMap = containers.Map('KeyType', 'int32', 'ValueType', 'int32');

            % Calculate new indices
            newIdx = 1;
            maxOldIdx = length(app.DataManager.CSVFilePaths) + length(deletedIndices);
            for oldIdx = 1:maxOldIdx
                if ~ismember(oldIdx, deletedIndices)
                    oldToNewMap(oldIdx) = newIdx;
                    newIdx = newIdx + 1;
                end
            end

            % Update assignments with better error handling
            if isprop(app, 'PlotManager') && isprop(app.PlotManager, 'AssignedSignals')
                numTabs = numel(app.PlotManager.AssignedSignals);
                for tabIdx = 1:numTabs
                    try
                        if tabIdx <= numel(app.PlotManager.AssignedSignals)
                            numSubplots = numel(app.PlotManager.AssignedSignals{tabIdx});
                            for subplotIdx = 1:numSubplots
                                if subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                                    for i = 1:length(assignedSignals)
                                        signal = assignedSignals{i};
                                        % Check if signal is a struct with CSVIdx field
                                        if isstruct(signal) && isfield(signal, 'CSVIdx') && signal.CSVIdx > 0
                                            if oldToNewMap.isKey(signal.CSVIdx)
                                                assignedSignals{i}.CSVIdx = oldToNewMap(signal.CSVIdx);
                                            else
                                                % Signal from deleted CSV - remove it
                                                fprintf('Warning: Signal from deleted CSV %d found in assignments\n', signal.CSVIdx);
                                            end
                                        end
                                    end

                                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = assignedSignals;
                                end
                            end
                        end
                    catch ME
                        fprintf('Error updating assignments for tab %d: %s\n', tabIdx, ME.message);
                    end
                end
            end

            % Update X-axis assignments
            if isprop(app, 'PlotManager') && isprop(app.PlotManager, 'XAxisSignals') && ~isempty(app.PlotManager.XAxisSignals)
                try
                    [numTabRows, numSubplotCols] = size(app.PlotManager.XAxisSignals);
                    for tabIdx = 1:numTabRows
                        for subplotIdx = 1:numSubplotCols
                            if ~isempty(app.PlotManager.XAxisSignals{tabIdx, subplotIdx})
                                xAxisSignal = app.PlotManager.XAxisSignals{tabIdx, subplotIdx};

                                % Check if xAxisSignal is a struct with CSVIdx field
                                if isstruct(xAxisSignal) && isfield(xAxisSignal, 'CSVIdx') && xAxisSignal.CSVIdx > 0
                                    if oldToNewMap.isKey(xAxisSignal.CSVIdx)
                                        app.PlotManager.XAxisSignals{tabIdx, subplotIdx}.CSVIdx = oldToNewMap(xAxisSignal.CSVIdx);
                                    else
                                        % X-axis signal from deleted CSV - clear it
                                        app.PlotManager.XAxisSignals{tabIdx, subplotIdx} = [];
                                    end
                                end
                            end
                        end
                    end
                catch ME
                    fprintf('Error updating X-axis assignments: %s\n', ME.message);
                end
            end

            % Update hidden signals keys
            if isprop(app, 'HiddenSignals') && ~isempty(app.HiddenSignals)
                try
                    hiddenKeys = keys(app.HiddenSignals);
                    newHiddenSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');

                    for i = 1:length(hiddenKeys)
                        key = hiddenKeys{i};
                        % Use robust regex to parse key instead of fragile split()
                        tokens = regexp(key, '^CSV(\d+)_(.*)$', 'tokens', 'once');
                        if ~isempty(tokens)
                            oldCsvIdx = str2double(tokens{1});
                            signalName = tokens{2};

                            if ~isnan(oldCsvIdx) && oldToNewMap.isKey(oldCsvIdx)
                                newCsvIdx = oldToNewMap(oldCsvIdx);
                                % Reconstruct key with the new index
                                newKey = sprintf('CSV%d_%s', newCsvIdx, signalName);
                                newHiddenSignals(newKey) = app.HiddenSignals(key);
                            end
                            % If CSV was deleted, don't add to new map (effectively removing it)
                        else
                            % Keep derived signals and other keys as-is
                            newHiddenSignals(key) = app.HiddenSignals(key);
                        end
                    end

                    app.HiddenSignals = newHiddenSignals;

                catch ME
                    fprintf('Error updating hidden signals: %s\n', ME.message);
                    % Don't fail the entire operation for this
                end
            end
        end
        function createLinkingMenu(app)
            % Create linking menu - called AFTER LinkingManager is initialized
            linkingMenu = uimenu(app.UIFigure, 'Text', 'Linking');
            uimenu(linkingMenu, 'Text', '🔗 Configure Signal Linking', 'MenuSelectedFcn', @(src, event) app.LinkingManager.showLinkingDialog());
            uimenu(linkingMenu, 'Text', '📊 Generate Comparison Analysis', 'MenuSelectedFcn', @(src, event) app.LinkingManager.showComparisonDialog());
            uimenu(linkingMenu, 'Text', '⚡ Quick Link Selected Nodes', 'MenuSelectedFcn', @(src, event) app.LinkingManager.quickLinkSelected());
            uimenu(linkingMenu, 'Text', '🔓 Clear All Links', 'MenuSelectedFcn', @(src, event) app.LinkingManager.clearAllLinks());
        end


        function app = SignalViewerApp()
            % Create UIFigure
            app.UIFigure = uifigure('Name', 'Signal Viewer Pro', ...
                'Position', [100 100 1200 800], ...
                'Color', [0.94 0.94 0.94], ...
                'Resize', 'on');

            app.UIFigure.AutoResizeChildren = 'off';

            %             % THEN set the resize callback
            app.UIFigure.SizeChangedFcn = @(src, event) app.onFigureResize();

            % Create panels with AutoResizeChildren disabled
            app.ControlPanel = uipanel(app.UIFigure, ...
                'Position', [1 1 318 799], ...
                'AutoResizeChildren', 'off');

            app.MainTabGroup = uitabgroup(app.UIFigure, ...
                'Position', [320 1 880 799], ...
                'AutoResizeChildren', 'off');

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
            app.setupDynamicResizing();
        end

        function setupDynamicResizing(app)
            % Configure the layout for dynamic resizing
            %             app.UIFigure.AutoResizeChildren = 'off';  % We'll handle resizing manually

            % Set minimum window size
            app.UIFigure.WindowState = 'normal';

            % Initial resize to ensure proper layout
            app.onFigureResize();
        end

        function onFigureResize(app)
            % Get current figure size
            figPos = app.UIFigure.Position;
            figWidth = figPos(3);
            figHeight = figPos(4);

            % Minimum size constraints
            minWidth = 800;
            minHeight = 600;

            if figWidth < minWidth || figHeight < minHeight
                app.UIFigure.Position = [figPos(1), figPos(2), max(figWidth, minWidth), max(figHeight, minHeight)];
                figWidth = max(figWidth, minWidth);
                figHeight = max(figHeight, minHeight);
            end

            % Calculate panel dimensions (control panel takes 25% of width, min 250px, max 400px)
            controlPanelWidth = max(250, min(400, figWidth * 0.25));
            plotPanelX = controlPanelWidth + 2;
            plotPanelWidth = figWidth - plotPanelX;

            % Resize control panel
            app.ControlPanel.Position = [1, 1, controlPanelWidth, figHeight];

            % Resize main tab group (plot area)
            app.MainTabGroup.Position = [plotPanelX, 1, plotPanelWidth, figHeight];

            % Resize components within control panel
            app.resizeControlPanelComponents(controlPanelWidth, figHeight);
        end

        function resizeControlPanelComponents(app, panelWidth, panelHeight)
            % Resize components within the control panel based on new dimensions

            margin = 20;
            componentWidth = panelWidth - 2 * margin;

            % Auto Scale button
            if isvalid(app.AutoScaleButton)
                buttonWidth = min(120, (componentWidth - 10) / 2);
                app.AutoScaleButton.Position = [margin, panelHeight - 60, buttonWidth, 30];
            end

            % Refresh CSVs button
            if isvalid(app.RefreshCSVsButton)
                buttonWidth = min(120, (componentWidth - 10) / 2);
                app.RefreshCSVsButton.Position = [margin + buttonWidth + 10, panelHeight - 60, buttonWidth, 30];
            end

            % Search field
            if isvalid(app.SignalSearchField)
                app.SignalSearchField.Position = [margin, panelHeight - 90, componentWidth, 25];
            end

            % Calculate space for bottom components (status labels + remove button + some padding)
            bottomSpace = 100; % Space reserved for bottom components

            % Properties table - MAKE IT MUCH LARGER
            if isvalid(app.SignalPropsTable)
                % Table gets 25% of available space (was fixed 85px)
                tableHeight = max(150, floor((panelHeight - 150 - bottomSpace) * 0.25)); % Minimum 120px, 25% of available space
                tableY = bottomSpace + 30; % Position above bottom components
                app.SignalPropsTable.Position = [margin, tableY, componentWidth, tableHeight];

                % Adjust column widths proportionally
                if componentWidth > 200
                    colWidths = {25, floor(componentWidth*0.35), 50, 40, 45, floor(componentWidth*0.15)};
                    app.SignalPropsTable.ColumnWidth = colWidths;
                end
            else
                tableHeight = 120;
                tableY = bottomSpace + 30;
            end

            % Signal tree - takes remaining space above the properties table
            if isvalid(app.SignalTree)
                treeY = tableY + tableHeight + 10; % Start above the table
                treeHeight = max(200, panelHeight - 120 - treeY); % Remaining space
                app.SignalTree.Position = [margin, treeY, componentWidth, treeHeight];
            end

            % Remove button - positioned above status labels
            if isvalid(app.RemoveSelectedSignalsButton)
                app.RemoveSelectedSignalsButton.Position = [margin, bottomSpace, componentWidth, 20];
            end

            % Status labels at the very bottom
            if isvalid(app.StatusLabel)
                app.StatusLabel.Position = [margin, 25, componentWidth, 15];
            end

            if isvalid(app.DataRateLabel)
                labelWidth = componentWidth / 2 - 5;
                app.DataRateLabel.Position = [margin, 55, labelWidth, 15];
            end

            if isvalid(app.StreamingInfoLabel)
                labelWidth = componentWidth / 2 - 5;
                app.StreamingInfoLabel.Position = [margin + labelWidth + 10, 55, labelWidth, 15];
            end
        end

        function createEnhancedComponents(app)
            % Enhanced layout with ALL original menus and components

            % FILE MENU
            fileMenu = uimenu(app.UIFigure, 'Text', 'File');
            uimenu(fileMenu, 'Text', '💾 Save Layout Config', 'MenuSelectedFcn', @(src, event) app.ConfigManager.saveConfig());
            uimenu(fileMenu, 'Text', '📁 Load Layout Config', 'MenuSelectedFcn', @(src, event) app.ConfigManager.loadConfig());
            uimenu(fileMenu, 'Text', '💾 Save Full Session', 'MenuSelectedFcn', @(src, event) app.saveSession());
            uimenu(fileMenu, 'Text', '📁 Load Full Session', 'MenuSelectedFcn', @(src, event) app.loadSession());

            % ACTIONS MENU
            actionsMenu = uimenu(app.UIFigure, 'Text', 'Actions');
            uimenu(actionsMenu, 'Text', '▶️ Start (Load CSVs)', 'MenuSelectedFcn', @(src, event) app.menuStart());
            uimenu(actionsMenu, 'Text', '➕ Add More CSVs', 'MenuSelectedFcn', @(src, event) app.menuAddMoreCSVs());
            uimenu(actionsMenu, 'Text', '⏹️ Stop', 'MenuSelectedFcn', @(src, event) app.menuStop());
            uimenu(actionsMenu, 'Text', '🗑️ Clear Plots Only', 'MenuSelectedFcn', @(src, event) app.menuClearPlotsOnly());
            uimenu(actionsMenu, 'Text', '🗑️ Clear Everything', 'MenuSelectedFcn', @(src, event) app.menuClearAll());
            uimenu(actionsMenu, 'Text', '📈 Statistics', 'MenuSelectedFcn', @(src, event) app.menuStatistics());


            % EXPORT MENU
            exportMenu = uimenu(app.UIFigure, 'Text', 'Export');
            uimenu(exportMenu, 'Text', '📊 Export CSV', 'MenuSelectedFcn', @(src, event) app.menuExportCSV());
            uimenu(exportMenu, 'Text', '📄 Export PDF', 'MenuSelectedFcn', @(src, event) app.menuExportPDF());
            uimenu(exportMenu, 'Text', '📄 Export PPT', 'MenuSelectedFcn', @(src, event) app.menuExportPPT());


            uimenu(exportMenu, 'Text', '📂 Open Plot Browser View', 'MenuSelectedFcn', @(src, event) app.menuExportToPlotBrowser());
            uimenu(exportMenu, 'Text', '📡 Export to SDI', 'MenuSelectedFcn', @(src, event) app.PlotManager.exportToSDI());

            % NEW VIEW MENU for layout control
            viewMenu = uimenu(app.UIFigure, 'Text', 'View');

            uimenu(viewMenu, 'Text', '👁️ Manage Hidden Signals', ...
                'MenuSelectedFcn', @(src, event) app.showHiddenSignalsManager(), 'Separator', 'on');
            uimenu(viewMenu, 'Text', '⬅️ Narrow Control Panel', 'MenuSelectedFcn', @(src, event) app.adjustControlPanelRatio(0.2), 'Separator', 'on');
            uimenu(viewMenu, 'Text', '➡️ Wide Control Panel', 'MenuSelectedFcn', @(src, event) app.adjustControlPanelRatio(0.35));
            uimenu(viewMenu, 'Text', '🎯 Default Layout', 'MenuSelectedFcn', @(src, event) app.adjustControlPanelRatio(0.25));

            % CONTROL PANEL COMPONENTS (initial positions - will be adjusted by resize)

            % Top buttons
            app.AutoScaleButton = uibutton(app.ControlPanel, 'push', 'Text', 'Auto Scale All', ...
                'Position', [20 740 120 30], ...
                'ButtonPushedFcn', @(src, event) app.autoScaleCurrentSubplot(), ...
                'Tooltip', 'Auto-scale all subplots in current tab to fit data', ...
                'FontSize', 11, 'FontWeight', 'bold');

            app.RefreshCSVsButton = uibutton(app.ControlPanel, 'push', 'Text', 'Refresh CSVs', ...
                'Position', [150 740 120 30], ...
                'ButtonPushedFcn', @(src, event) app.refreshCSVs(), ...
                'FontSize', 11, 'FontWeight', 'bold');

            % Search box
            app.SignalSearchField = uieditfield(app.ControlPanel, 'text', ...
                'Position', [20 710 280 25], ...
                'Placeholder', 'Search signals...', ...
                'ValueChangingFcn', @(src, event) app.filterSignals(event.Value), ...
                'FontSize', 11);

            % Signal tree - main component
            app.SignalTree = uitree(app.ControlPanel, ...
                'Position', [20 200 280 500], ...
                'SelectionChangedFcn', @(src, event) app.onSignalTreeSelectionChanged(), ...
                'FontSize', 11);

            % Set up tree properties
            try
                app.SignalTree.Multiselect = 'on';
            catch
                % Multiselect not available in older versions
            end

            try
                app.SignalTree.Draggable = 'on';
            catch
                % Draggable not available in older versions
            end

            % Context menu setup
            cm = uicontextmenu(app.UIFigure);
            app.SignalTree.ContextMenu = cm;
            app.setupMultiSelectionContextMenu();

            % Properties table
            app.SignalPropsTable = uitable(app.ControlPanel, ...
                'Position', [20 110 280 85], ...
                'ColumnName', {'☐', 'Signal', 'Scale', 'State', 'Color', 'LineWidth'}, ...
                'ColumnWidth', {25, 100, 50, 40, 45, 60}, ...
                'ColumnEditable', [true false true true false true], ...
                'CellEditCallback', @(src, event) app.onSignalPropsEdit(event), ...
                'CellSelectionCallback', @(src, event) app.onSignalPropsSelection(event), ...
                'FontSize', 10);

            % Remove button
            app.RemoveSelectedSignalsButton = uibutton(app.ControlPanel, 'push', ...
                'Text', '🗑️ Remove Selected from Subplot', ...
                'Position', [20 85 280 20], ...
                'ButtonPushedFcn', @(src, event) app.removeSelectedSignalsFromTable(), ...
                'FontSize', 9, 'Enable', 'off');

            % Status labels at bottom
            app.StatusLabel = uilabel(app.ControlPanel, ...
                'Position', [20 25 280 15], ...
                'Text', 'Ready', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 10, ...
                'FontWeight', 'bold');

            app.DataRateLabel = uilabel(app.ControlPanel, ...
                'Position', [20 55 140 15], ...
                'Text', 'Data Rate: 0 Hz', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 9);

            app.StreamingInfoLabel = uilabel(app.ControlPanel, ...
                'Position', [160 65 140 15], ...
                'Text', '', ...
                'FontColor', [0.2 0.2 0.2], ...
                'FontSize', 9);

        end


        function adjustControlPanelRatio(app, ratio)
            % Adjust the control panel to take a specific ratio of the window width
            figPos = app.UIFigure.Position;
            figWidth = figPos(3);

            % Force a specific control panel width
            controlPanelWidth = max(250, min(500, figWidth * ratio));

            % Temporarily override the automatic calculation
            app.ControlPanel.Position(3) = controlPanelWidth;
            app.MainTabGroup.Position(1) = controlPanelWidth + 2;
            app.MainTabGroup.Position(3) = figWidth - controlPanelWidth - 2;

            % Resize control panel components
            app.resizeControlPanelComponents(controlPanelWidth, figPos(4));
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
                        signalKey = app.getSignalKey(signalInfo);

                        % Scale filter
                        scale = 1.0;
                        if app.DataManager.SignalScaling.isKey(signalKey)
                            scale = app.DataManager.SignalScaling(signalKey);
                        end
                        if scale < minScale || scale > maxScale
                            continue;
                        end

                        % Type filter
                        isState = false;
                        if app.DataManager.StateSignals.isKey(signalKey)
                            isState = app.DataManager.StateSignals(signalKey);
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
                            signalInfo = filteredSignals{i};
                            signalKey = app.getSignalKey(signalInfo);
                            app.DataManager.SignalScaling(signalKey) = newScale;
                        end
                    end
                    app.PlotManager.refreshPlots(); % Refresh all plots
                    close(bd);
                end

                function applyBulkStateFiltered(isState)
                    for i = selectedIndices
                        if i <= length(filteredSignals)
                            app.DataManager.StateSignals(filteredSignals{i}.Signal) = isState;
                            signalInfo = filteredSignals{i};
                            signalKey = app.getSignalKey(signalInfo);
                            app.DataManager.StateSignals(signalKey) = isState;
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
                    app.SignalStyles = containers.Map('KeyType', 'char', 'ValueType', 'any');

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

                app.SignalStyles = containers.Map('KeyType', 'char', 'ValueType', 'any');

                colorIndex = 1;
                colorCount = 0;

                for i = 1:numel(app.DataManager.DataTables)
                    T = app.DataManager.DataTables{i};
                    if isempty(T), continue; end

                    signals = setdiff(T.Properties.VariableNames, {'Time'});
                    for j = 1:numel(signals)
                        signalName = signals{j};
                        signalInfo = struct('CSVIdx', i, 'Signal', signalName);
                        signalKey = app.getSignalKey(signalInfo);

                        app.SignalStyles(signalKey) = struct('Color', colorPalette(colorIndex, :), 'LineWidth', 2);
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
            signalKey = app.getSignalKey(signalInfo);

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
            if app.DataManager.SignalScaling.isKey(signalKey)
                currentScale = app.DataManager.SignalScaling(signalKey);
            end

            scaleField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [130 270 100 25], 'String', num2str(currentScale), ...
                'HorizontalAlignment', 'left');

            % State signal checkbox
            currentState = false;
            if app.DataManager.StateSignals.isKey(signalKey)
                currentState = app.DataManager.StateSignals(signalKey);
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
            %             uicontrol('Parent', d, 'Style', 'text', 'Position', [20 110 200 20], ...
            %                 'String', 'Signal Filtering:', 'FontWeight', 'bold');

            %             filterCheck = uicontrol('Parent', d, 'Style', 'checkbox', ...
            %                 'Position', [20 80 150 20], 'String', 'Hide from tree view', ...
            %                 'Value', false);

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
                ylabel(signalInfo.Signal);
                grid on;

                % Add basic statistics as text
                stats = sprintf('Mean: %.3f | Std: %.3f | Min: %.3f | Max: %.3f | Samples: %d', ...
                    mean(signalData), std(signalData), min(signalData), max(signalData), length(signalData));

                annotation(fig, 'textbox', [0.1 0.05 0.8 0.05], 'String', stats, ...
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
        function onSignalTreeSelectionChanged(app, ~)
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
                app.StatusLabel.Text = sprintf('Selected: %s (right-click for options, double-click to toggle)', selectedSignals{1}.Signal);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            elseif signalCount > 1
                app.StatusLabel.Text = sprintf('Selected: %d signals (right-click for options, double-click to toggle)', signalCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'No signals selected';
                app.StatusLabel.FontColor = [0.5 0.5 0.5];
            end


        end

        function updateSignalPropsTable(app, selectedSignals)
            % Enhanced version that shows tuple info in tuple mode
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Check if current subplot is in tuple mode
            if app.isSubplotInTupleMode(tabIdx, subplotIdx)
                % Show tuple information instead of regular signal properties
                app.updateTuplePropsTable(tabIdx, subplotIdx);
                return;
            end

            % Regular signal properties table (existing implementation)
            n = numel(selectedSignals);

            if n == 0
                app.SignalPropsTable.Data = {};
                app.RemoveSelectedSignalsButton.Enable = 'off';
                return;
            end

            % Create data with checkbox column
            data = cell(n, 6); % 6 columns: checkbox, signal, scale, state, color, linewidth

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

                % Fill data row
                data{i,1} = false;  % Checkbox
                data{i,2} = sigName;  % Signal name
                data{i,3} = scale;    % Scale
                data{i,4} = state;    % State
                data{i,5} = mat2str(color); % Color as string
                data{i,6} = width;    % Line width
            end

            app.SignalPropsTable.Data = data;
            app.RemoveSelectedSignalsButton.Enable = 'off';
            app.SignalPropsTable.CellSelectionCallback = @(src, event) app.onSignalPropsCellSelect(event);
        end

        function onSignalPropsEdit(app, event)
            % Callback for when the user edits properties in the table

            data = app.SignalPropsTable.Data;
            if isempty(data)
                return;
            end

            row = event.Indices(1);
            col = event.Indices(2);

            % Handle different columns (note: columns shifted due to checkbox)
            if col == 1
                % Checkbox column - update remove button state
                app.updateRemoveButtonState();
                return;

            elseif col == 3 % Scale (was column 2)
                sigName = data{row,2}; % Signal name in column 2
                scale = event.NewData;
                if ischar(scale) || isstring(scale)
                    scale = str2double(scale);
                end
                if isnumeric(scale) && isfinite(scale) && scale ~= 0
                    app.DataManager.SignalScaling(sigName) = scale;
                else
                    app.DataManager.SignalScaling(sigName) = 1.0;
                    data{row,3} = 1.0;
                    app.SignalPropsTable.Data = data;
                end

            elseif col == 4 % State (was column 3)
                sigName = data{row,2};
                app.DataManager.StateSignals(sigName) = logical(event.NewData);

            elseif col == 6 % LineWidth (was column 5)
                sigName = data{row,2};
                width = event.NewData;
                if ischar(width) || isstring(width)
                    width = str2double(width);
                end
                if isnumeric(width) && isfinite(width) && width > 0
                    if isempty(app.SignalStyles), app.SignalStyles = struct(); end
                    if ~isfield(app.SignalStyles, sigName), app.SignalStyles.(sigName) = struct(); end
                    app.SignalStyles.(sigName).LineWidth = width;
                else
                    data{row,6} = 2;
                    app.SignalPropsTable.Data = data;
                end
            end

            % Small delay for value to commit
            pause(0.01);

            % Refresh plots (will only affect plots where this signal is assigned)
            app.PlotManager.refreshPlots();

            % Update status
            if col > 1 % Only for non-checkbox edits
                sigName = data{row,2};
                app.StatusLabel.Text = sprintf('✅ Updated %s properties', sigName);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
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

        function buildSignalTree(app)
            % Enhanced version with hidden signal filtering

            % Initialize hidden signals map
            app.initializeHiddenSignalsMap();

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

                % Filter out hidden signals
                visibleSignals = {};
                for j = 1:numel(signals)
                    signalName = signals{j};
                    signalInfo = struct('CSVIdx', i, 'Signal', signalName);

                    if ~app.isSignalHidden(signalInfo)
                        visibleSignals{end+1} = signalName;
                    end
                end

                % Create CSV node only if it has visible signals
                if ~isempty(visibleSignals)
                    csvNode = uitreenode(app.SignalTree, 'Text', csvDisplay);

                    % FIXED: Set proper NodeData for CSV folder
                    csvNode.NodeData = struct('Type', 'csv_folder', 'CSVIdx', i);

                    % Store the node for later expansion restoration
                    createdNodes{end+1} = struct('Node', csvNode, 'Text', csvDisplay);

                    % FIXED: Create dynamic context menu that detects multiple CSV selection
                    csvContextMenu = uicontextmenu(app.UIFigure);

                    % Set dynamic context menu that populates when opened
                    csvContextMenu.ContextMenuOpeningFcn = @(src, event) app.populateCSVContextMenu(csvContextMenu, i);

                    csvNode.ContextMenu = csvContextMenu;

                    % Add visible signals to this CSV node
                    for j = 1:numel(visibleSignals)
                        signalName = visibleSignals{j};
                        signalInfo = struct('CSVIdx', i, 'Signal', signalName);

                        child = uitreenode(csvNode, 'Text', signalName);
                        child.NodeData = signalInfo;

                        % Use the enhanced context menu system for all signals
                        app.attachMultiSelectionContextMenu(child);
                    end
                end
            end

            % Add derived signals section if they exist
            if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations.DerivedSignals)
                % Filter derived signals for hidden ones
                derivedNames = keys(app.SignalOperations.DerivedSignals);
                visibleDerivedSignals = {};

                for i = 1:length(derivedNames)
                    signalName = derivedNames{i};
                    signalInfo = struct('CSVIdx', -1, 'Signal', signalName);

                    % Apply search filter if active
                    searchMatch = true;
                    if ~isempty(app.SignalSearchField.Value)
                        searchMatch = contains(lower(signalName), lower(app.SignalSearchField.Value));
                    end

                    if searchMatch && ~app.isSignalHidden(signalInfo)
                        visibleDerivedSignals{end+1} = signalName;
                    end
                end

                % Only create derived signals node if there are visible derived signals
                if ~isempty(visibleDerivedSignals)
                    derivedNode = uitreenode(app.SignalTree, 'Text', '⚙️ Derived Signals');
                    derivedNode.NodeData = struct('Type', 'derived_signals_folder');

                    createdNodes{end+1} = struct('Node', derivedNode, 'Text', '⚙️ Derived Signals');

                    % Add derived signals management context menu
                    derivedContextMenu = uicontextmenu(app.UIFigure);
                    uimenu(derivedContextMenu, 'Text', '📋 Operation History', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.showOperationHistory());
                    uimenu(derivedContextMenu, 'Text', '🗑️ Clear All Derived Signals', ...
                        'MenuSelectedFcn', @(src, event) app.confirmAndClearDerivedSignals());
                    uimenu(derivedContextMenu, 'Text', '👁️ Manage Hidden Signals', ...
                        'MenuSelectedFcn', @(src, event) app.showHiddenSignalsManager(), 'Separator', 'on');
                    derivedNode.ContextMenu = derivedContextMenu;

                    for i = 1:length(visibleDerivedSignals)
                        signalName = visibleDerivedSignals{i};
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
                        signalInfo = struct('CSVIdx', -1, 'Signal', signalName, 'IsDerived', true);
                        child.NodeData = signalInfo;

                        % Use the enhanced context menu system for derived signals
                        app.attachMultiSelectionContextMenu(child);
                    end
                end
            end

            % Restore expanded state for previously expanded nodes
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
                    catch
                        try
                            node.Expanded = true;
                        catch
                            % Ignore expansion errors
                        end
                    end
                end
            end

            % Setup axes drop targets and enable data tips
            app.setupAxesDropTargets();

            app.restoreTreeExpandedState();
        end

        function fixDerivedSignalContextMenus(app, derivedSignalsNode)
            % Fix context menus for all derived signal children
            children = derivedSignalsNode.Children;
            for i = 1:numel(children)
                child = children(i);
                if isfield(child.NodeData, 'Signal') && isfield(child.NodeData, 'CSVIdx')
                    % Replace the context menu with our unified system
                    app.attachMultiSelectionContextMenu(child);
                end
            end
        end

        function attachMultiSelectionContextMenu(app, signalNode)
            % Attach a context menu that will dynamically detect multi-selection

            % Create a context menu that will be populated when opened
            contextMenu = uicontextmenu(app.UIFigure);

            % Set the ContextMenuOpeningFcn to populate the menu dynamically
            contextMenu.ContextMenuOpeningFcn = @(src, event) app.populateMultiSelectionContextMenu(contextMenu, signalNode.NodeData);

            % Assign to the node
            signalNode.ContextMenu = contextMenu;
        end

        function createSignalContextMenu(app, contextMenu, signalInfo)
            % Create context menu items for a signal node that handles multi-selection

            % Clear any existing items
            delete(contextMenu.Children);

            % ============= CHECK FOR MULTIPLE SELECTED SIGNALS =============
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = app.getSelectedSignalsFromNodes(selectedNodes);

            % If no valid signals selected, use the clicked signal
            if isempty(selectedSignals)
                selectedSignals = {signalInfo};
            end

            % Get current assignments to determine what actions are available
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            currentAssignments = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Separate assigned and unassigned signals
            assignedSignals = {};
            unassignedSignals = {};

            for i = 1:numel(selectedSignals)
                isAssigned = false;
                signal = selectedSignals{i};

                % Check if this signal is assigned
                for j = 1:numel(currentAssignments)
                    if isequal(currentAssignments{j}, signal)
                        isAssigned = true;
                        break;
                    end
                end

                if isAssigned
                    assignedSignals{end+1} = signal;
                else
                    unassignedSignals{end+1} = signal;
                end
            end

            % ============= ASSIGNMENT/REMOVAL OPERATIONS =============
            if ~isempty(unassignedSignals)
                if numel(unassignedSignals) == 1
                    uimenu(contextMenu, 'Text', '➕ Add to Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.addMultipleSignalsToCurrentSubplot(unassignedSignals));
                else
                    uimenu(contextMenu, 'Text', sprintf('➕ Add %d Signals to Subplot', numel(unassignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.addMultipleSignalsToCurrentSubplot(unassignedSignals));
                end
            end

            if ~isempty(assignedSignals)
                if numel(assignedSignals) == 1
                    uimenu(contextMenu, 'Text', '❌ Remove from Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.removeMultipleSignalsFromCurrentSubplot(assignedSignals));
                else
                    uimenu(contextMenu, 'Text', sprintf('❌ Remove %d Signals from Subplot', numel(assignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.removeMultipleSignalsFromCurrentSubplot(assignedSignals));
                end
            end

            % ============= PREVIEW AND SINGLE SIGNAL OPTIONS =============
            if numel(selectedSignals) == 1
                signal = selectedSignals{1};

                uimenu(contextMenu, 'Text', '📊 Quick Preview', ...
                    'MenuSelectedFcn', @(src, event) app.showSignalPreview(signal), ...
                    'Separator', 'on');

                uimenu(contextMenu, 'Text', '📈 Set as X-Axis', ...
                    'MenuSelectedFcn', @(src, event) app.setSignalAsXAxis(signal));

                % Single signal operations
                operationsMenu = uimenu(contextMenu, 'Text', '🔢 Single Signal Operations', 'Separator', 'on');

                signalName = app.getSignalNameForOperations(signal);
                uimenu(operationsMenu, 'Text', '∂ Derivative', ...
                    'MenuSelectedFcn', @(src, event) app.showDerivativeForSelected(signalName));
                uimenu(operationsMenu, 'Text', '∫ Integral', ...
                    'MenuSelectedFcn', @(src, event) app.showIntegralForSelected(signalName));

                % Export options for single signal
                if signal.CSVIdx == -1  % Derived signal
                    uimenu(contextMenu, 'Text', '📋 Show Operation Details', ...
                        'MenuSelectedFcn', @(src, event) app.showDerivedSignalDetails(signal.Signal), ...
                        'Separator', 'on');

                    uimenu(contextMenu, 'Text', '💾 Export Signal', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.exportDerivedSignal(signal.Signal));

                    uimenu(contextMenu, 'Text', '🗑️ Delete Signal', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.confirmDeleteDerivedSignal(signal.Signal));
                else
                    uimenu(contextMenu, 'Text', '💾 Export Signal to CSV', ...
                        'MenuSelectedFcn', @(src, event) app.exportSingleSignalToCSV(signal), ...
                        'Separator', 'on');
                end

                uimenu(contextMenu, 'Text', '🗑️ Clear from All Subplots', ...
                    'MenuSelectedFcn', @(src, event) app.clearSpecificSignalFromAllSubplots(signal), ...
                    'Separator', 'on');

            else
                % Multiple signals selected
                uimenu(contextMenu, 'Text', sprintf('📊 Preview %d Signals', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.previewSelectedSignals(selectedSignals), ...
                    'Separator', 'on');
            end

            % ============= MULTI-SIGNAL OPERATIONS =============
            if numel(selectedSignals) >= 2
                multiOpsMenu = uimenu(contextMenu, 'Text', sprintf('⚡ Multi-Signal Ops (%d selected)', numel(selectedSignals)), ...
                    'Separator', 'on');

                uimenu(multiOpsMenu, 'Text', '📊 Vector Magnitude', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickVectorMagnitudeForSelected(selectedSignals));

                uimenu(multiOpsMenu, 'Text', '📈 Signal Average', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickAverageForSelected(selectedSignals));

                uimenu(multiOpsMenu, 'Text', '‖‖ Norm of Signals', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickNormForSelected(selectedSignals));

                % Dual operations for exactly 2 signals
                if numel(selectedSignals) == 2
                    dualMenu = uimenu(multiOpsMenu, 'Text', '📈 Dual Operations');

                    signal1Name = app.getSignalNameForOperations(selectedSignals{1});
                    signal2Name = app.getSignalNameForOperations(selectedSignals{2});

                    uimenu(dualMenu, 'Text', '➕ Add (A + B)', ...
                        'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('add', signal1Name, signal2Name));
                    uimenu(dualMenu, 'Text', '➖ Subtract (A - B)', ...
                        'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('subtract', signal1Name, signal2Name));
                    uimenu(dualMenu, 'Text', '✖️ Multiply (A × B)', ...
                        'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('multiply', signal1Name, signal2Name));
                    uimenu(dualMenu, 'Text', '➗ Divide (A ÷ B)', ...
                        'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('divide', signal1Name, signal2Name));
                end

                % Export multiple signals
                uimenu(contextMenu, 'Text', sprintf('💾 Export %d Signals to CSV', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.exportMultipleSignalsToCSV(selectedSignals), ...
                    'Separator', 'on');

                % Clear multiple signals from all subplots
                uimenu(contextMenu, 'Text', sprintf('🗑️ Clear %d Signals from All Subplots', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.clearMultipleSignalsFromAllSubplots(selectedSignals));
            end

            % ============= SELECTION INFO =============
            if numel(selectedSignals) > 1
                uimenu(contextMenu, 'Text', sprintf('📋 %d signals selected', numel(selectedSignals)), ...
                    'Enable', 'off', 'Separator', 'on');
            elseif numel(selectedSignals) == 1
                signal = selectedSignals{1};
                if signal.CSVIdx == -1
                    signalType = 'derived signal';
                else
                    signalType = sprintf('CSV %d signal', signal.CSVIdx);
                end
                uimenu(contextMenu, 'Text', sprintf('📋 %s: %s', signalType, signal.Signal), ...
                    'Enable', 'off', 'Separator', 'on');
            end
        end

        function signalName = getSignalNameForOperations(app, signalInfo)
            % Convert signal info to name format expected by operations
            if signalInfo.CSVIdx == -1
                signalName = sprintf('%s (Derived)', signalInfo.Signal);
            else
                % Format: "signal_name (CSV1: filename)"
                if numel(app.DataManager.CSVFilePaths) > 1
                    [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{signalInfo.CSVIdx});
                    signalName = sprintf('%s (CSV%d: %s)', signalInfo.Signal, signalInfo.CSVIdx, csvName);
                else
                    signalName = signalInfo.Signal;
                end
            end
        end

        function showDerivativeForSelected(app, signalName)
            % Show derivative dialog with pre-selected signal
            try
                app.SignalOperations.showSingleSignalDialog('derivative');
            catch ME
                uialert(app.UIFigure, sprintf('Failed to open derivative dialog: %s', ME.message), 'Operation Failed');
            end
        end

        function showIntegralForSelected(app, signalName)
            % Show integral dialog with pre-selected signal
            try
                app.SignalOperations.showSingleSignalDialog('integral');
            catch ME
                uialert(app.UIFigure, sprintf('Failed to open integral dialog: %s', ME.message), 'Operation Failed');
            end
        end

        function showDualOperationForSelected(app, operation, signal1Name, signal2Name)
            % Show dual signal operation dialog
            try
                app.SignalOperations.showDualSignalDialog(operation);
            catch ME
                uialert(app.UIFigure, sprintf('Failed to open %s dialog: %s', operation, ME.message), 'Operation Failed');
            end
        end

        function showQuickVectorMagnitudeForSelected(app, selectedSignals)
            % Execute vector magnitude with selected signals
            if length(selectedSignals) < 2
                uialert(app.UIFigure, 'Please select at least 2 signals for vector magnitude.', 'Invalid Selection');
                return;
            end

            % Convert to signal names
            signalNames = cell(length(selectedSignals), 1);
            for i = 1:length(selectedSignals)
                signalNames{i} = app.getSignalNameForOperations(selectedSignals{i});
            end

            % Generate default result name
            defaultName = sprintf('vector_magnitude_%d_signals', length(selectedSignals));

            try
                app.SignalOperations.executeVectorMagnitude(signalNames, defaultName);
            catch ME
                uialert(app.UIFigure, sprintf('Vector magnitude failed: %s', ME.message), 'Operation Failed');
            end
        end

        function showQuickAverageForSelected(app, selectedSignals)
            % Execute signal average with selected signals
            if length(selectedSignals) < 2
                uialert(app.UIFigure, 'Please select at least 2 signals for averaging.', 'Invalid Selection');
                return;
            end

            % Convert to signal names
            signalNames = cell(length(selectedSignals), 1);
            for i = 1:length(selectedSignals)
                signalNames{i} = app.getSignalNameForOperations(selectedSignals{i});
            end

            % Generate default result name
            defaultName = sprintf('average_%d_signals', length(selectedSignals));

            try
                app.SignalOperations.executeSignalAverage(signalNames, defaultName);
            catch ME
                uialert(app.UIFigure, sprintf('Signal averaging failed: %s', ME.message), 'Operation Failed');
            end
        end

        function showQuickNormForSelected(app, selectedSignals)
            % Show norm dialog (it will handle signal selection)
            if length(selectedSignals) < 2
                uialert(app.UIFigure, 'Please select at least 2 signals for norm calculation.', 'Invalid Selection');
                return;
            end

            try
                app.SignalOperations.showNormDialog();
            catch ME
                uialert(app.UIFigure, sprintf('Failed to open norm dialog: %s', ME.message), 'Operation Failed');
            end
        end

        function showQuickMovingAverageForSelected(app, selectedSignal)
            % Execute moving average with default parameters
            signalName = app.getSignalNameForOperations(selectedSignal);
            defaultWindowSize = 20;
            defaultName = sprintf('%s_moving_avg', selectedSignal.Signal);

            try
                app.SignalOperations.executeMovingAverage(signalName, defaultWindowSize, defaultName);
            catch ME
                uialert(app.UIFigure, sprintf('Moving average failed: %s', ME.message), 'Operation Failed');
            end
        end

        function showQuickFFTForSelected(app, selectedSignal)
            % Execute FFT analysis with default parameters
            signalName = app.getSignalNameForOperations(selectedSignal);
            outputType = 1; % Magnitude
            defaultName = sprintf('%s_fft_magnitude', selectedSignal.Signal);

            try
                app.SignalOperations.executeFFT(signalName, outputType, defaultName);
            catch ME
                uialert(app.UIFigure, sprintf('FFT analysis failed: %s', ME.message), 'Operation Failed');
            end
        end

        function showQuickRMSForSelected(app, selectedSignal)
            % Execute RMS calculation with default parameters
            signalName = app.getSignalNameForOperations(selectedSignal);
            defaultWindowSize = 100;
            defaultName = sprintf('%s_rms', selectedSignal.Signal);

            try
                app.SignalOperations.executeRMS(signalName, defaultWindowSize, defaultName);
            catch ME
                uialert(app.UIFigure, sprintf('RMS calculation failed: %s', ME.message), 'Operation Failed');
            end
        end

        function showStatisticalAnalysisForSelected(app, selectedSignals)
            % Show statistical analysis for multiple signals
            if length(selectedSignals) < 3
                uialert(app.UIFigure, 'Statistical analysis requires at least 3 signals.', 'Invalid Selection');
                return;
            end

            % Create a simple statistical analysis dialog
            d = dialog('Name', 'Statistical Analysis', 'Position', [300 300 400 300]);

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 360 25], ...
                'String', sprintf('Statistical Analysis of %d Signals', length(selectedSignals)), ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Analysis options
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 120 20], ...
                'String', 'Analysis Type:', 'FontWeight', 'bold');

            analysisDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 220 200 25], ...
                'String', {'Mean and Std Dev', 'Correlation Matrix', 'Principal Components'});

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 180 200 25], 'String', 'statistical_analysis', ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Analyze', ...
                'Position', [220 20 80 30], 'Callback', @(~,~) performAnalysis(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 20 80 30], 'Callback', @(~,~) close(d));

            function performAnalysis()
                % Placeholder for statistical analysis
                uialert(d, 'Statistical analysis feature coming soon!', 'Feature Preview');
                close(d);
            end
        end

        function showDerivedSignalDetails(app, signalName)
            % Show detailed information about a derived signal
            if ~app.SignalOperations.DerivedSignals.isKey(signalName)
                uialert(app.UIFigure, 'Derived signal not found.', 'Signal Not Found');
                return;
            end

            derivedData = app.SignalOperations.DerivedSignals(signalName);
            app.SignalOperations.showOperationDetails(derivedData.Operation);
        end

        function exportSingleSignalToCSV(app, signalInfo)
            % Export a single signal to CSV
            try
                % Get signal data
                if signalInfo.CSVIdx == -1
                    % Derived signal
                    [timeData, signalData] = app.SignalOperations.getSignalData(signalInfo.Signal);
                else
                    % Original signal
                    T = app.DataManager.DataTables{signalInfo.CSVIdx};
                    timeData = T.Time;
                    signalData = T.(signalInfo.Signal);

                    % Apply scaling
                    if app.DataManager.SignalScaling.isKey(signalInfo.Signal)
                        signalData = signalData * app.DataManager.SignalScaling(signalInfo.Signal);
                    end
                end

                if isempty(timeData)
                    uialert(app.UIFigure, 'Signal data is empty.', 'Export Failed');
                    return;
                end

                % Get save location
                defaultName = sprintf('%s.csv', signalInfo.Signal);
                [file, path] = uiputfile('*.csv', 'Export Signal', defaultName);
                if isequal(file, 0)
                    return;
                end

                % Create and save table
                exportTable = table(timeData, signalData, 'VariableNames', {'Time', signalInfo.Signal});
                writetable(exportTable, fullfile(path, file));

                app.StatusLabel.Text = sprintf('✅ Exported signal: %s', file);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                uialert(app.UIFigure, sprintf('Export failed: %s', ME.message), 'Export Error');
            end
        end

        function exportMultipleSignalsToCSV(app, selectedSignals)
            % Export multiple signals to a single CSV file
            try
                % Get save location
                defaultName = sprintf('multiple_signals_%d.csv', length(selectedSignals));
                [file, path] = uiputfile('*.csv', 'Export Multiple Signals', defaultName);
                if isequal(file, 0)
                    return;
                end

                % Collect all signal data
                allTimeData = {};
                allSignalData = {};
                signalNames = {};

                for i = 1:length(selectedSignals)
                    signalInfo = selectedSignals{i};

                    if signalInfo.CSVIdx == -1
                        % Derived signal
                        [timeData, signalData] = app.SignalOperations.getSignalData(signalInfo.Signal);
                    else
                        % Original signal
                        T = app.DataManager.DataTables{signalInfo.CSVIdx};
                        timeData = T.Time;
                        signalData = T.(signalInfo.Signal);

                        % Apply scaling
                        if app.DataManager.SignalScaling.isKey(signalInfo.Signal)
                            signalData = signalData * app.DataManager.SignalScaling(signalInfo.Signal);
                        end
                    end

                    if ~isempty(timeData)
                        allTimeData{end+1} = timeData;
                        allSignalData{end+1} = signalData;
                        signalNames{end+1} = signalInfo.Signal;
                    end
                end

                if isempty(allTimeData)
                    uialert(app.UIFigure, 'No valid signal data to export.', 'Export Failed');
                    return;
                end

                % Align signals to common time base
                [commonTime, alignedData] = app.SignalOperations.alignMultipleSignals(allTimeData, allSignalData, 'linear', 1);

                % Create export table
                exportData = [commonTime, alignedData];
                variableNames = ['Time', signalNames];
                exportTable = array2table(exportData, 'VariableNames', variableNames);

                % Save table
                writetable(exportTable, fullfile(path, file));

                app.StatusLabel.Text = sprintf('✅ Exported %d signals: %s', length(selectedSignals), file);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                uialert(app.UIFigure, sprintf('Export failed: %s', ME.message), 'Export Error');
            end
        end

        function onTreeNodeExpanded(app, csvNodeText)
            % Call this when a node is manually expanded
            if nargin < 2 || isempty(csvNodeText)
                return; % Safety check for missing arguments
            end

            if ~isprop(app, 'ExpandedTreeNodes') || isempty(app.ExpandedTreeNodes)
                app.ExpandedTreeNodes = string.empty;
            end

            if ~any(strcmp(csvNodeText, app.ExpandedTreeNodes))
                app.ExpandedTreeNodes(end+1) = string(csvNodeText);
            end

            % DEBUG: Track expansion
            fprintf('Node expanded: %s\n', csvNodeText);
        end

        function onTreeNodeCollapsed(app, csvNodeText)
            % Call this when a node is manually collapsed
            if nargin < 2 || isempty(csvNodeText)
                return; % Safety check for missing arguments
            end

            if ~isprop(app, 'ExpandedTreeNodes') || isempty(app.ExpandedTreeNodes)
                app.ExpandedTreeNodes = string.empty;
                return;
            end

            app.ExpandedTreeNodes = app.ExpandedTreeNodes(~strcmp(app.ExpandedTreeNodes, csvNodeText));

            % DEBUG: Track collapse
            fprintf('Node collapsed: %s\n', csvNodeText);
        end

        function filterSignals(app, searchText)
            % Enhanced filter with hidden signal support and UNIFIED context menu recreation

            % Initialize hidden signals map
            app.initializeHiddenSignalsMap();

            % Clear existing tree
            delete(app.SignalTree.Children);

            if isempty(searchText)
                searchText = '';
            end

            hasFilteredResults = false;
            nodesToExpand = {};

            % Get current subplot assignments for visual indicators
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            assignedSignals = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Process each CSV file
            for i = 1:numel(app.DataManager.CSVFilePaths)
                [~, csvName, ext] = fileparts(app.DataManager.CSVFilePaths{i});
                csvDisplay = [csvName ext];
                T = app.DataManager.DataTables{i};
                if isempty(T), continue; end

                signals = setdiff(T.Properties.VariableNames, {'Time'});

                % Filter signals by search text AND hidden status
                filteredSignals = {};
                for j = 1:numel(signals)
                    signalName = signals{j};
                    signalInfo = struct('CSVIdx', i, 'Signal', signalName);

                    % Check search filter
                    searchMatch = true;
                    if ~isempty(searchText)
                        searchMatch = contains(lower(signalName), lower(searchText));
                    end

                    % Check if signal is hidden
                    isHidden = app.isSignalHidden(signalInfo);

                    % Include signal if it matches search AND is not hidden
                    if searchMatch && ~isHidden
                        filteredSignals{end+1} = signalName;
                    end
                end

                % Only create CSV node if it has filtered signals OR no search is active
                if ~isempty(filteredSignals) || (isempty(searchText) && ~isempty(signals))
                    csvNode = uitreenode(app.SignalTree, 'Text', csvDisplay);
                    csvNode.NodeData = struct('Type', 'csv_folder', 'CSVIdx', i);

                    % Add CSV-level context menu
                    csvContextMenu = uicontextmenu(app.UIFigure);
                    uimenu(csvContextMenu, 'Text', '📌 Assign All to Current Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.assignAllSignalsFromCSV(i));
                    uimenu(csvContextMenu, 'Text', '❌ Remove All from Current Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.removeAllSignalsFromCSV(i));
                    uimenu(csvContextMenu, 'Text', '⚙️ Bulk Edit Properties', ...
                        'MenuSelectedFcn', @(src, event) app.bulkEditSignalProperties(i), 'Separator', 'on');
                    uimenu(csvContextMenu, 'Text', '👁️ Manage Hidden Signals', ...
                        'MenuSelectedFcn', @(src, event) app.showHiddenSignalsManager(), 'Separator', 'on');
                    csvNode.ContextMenu = csvContextMenu;

                    % Add signals to this CSV node
                    for j = 1:numel(filteredSignals)
                        signalName = filteredSignals{j};
                        signalInfo = struct('CSVIdx', i, 'Signal', signalName);

                        child = uitreenode(csvNode, 'Text', signalName);
                        child.NodeData = signalInfo;

                        % UNIFIED: Use the enhanced context menu system for filtered signals
                        app.attachMultiSelectionContextMenu(child);
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

                % Filter derived signals by search text AND hidden status
                filteredDerived = {};
                for i = 1:length(derivedNames)
                    signalName = derivedNames{i};
                    signalInfo = struct('CSVIdx', -1, 'Signal', signalName);

                    % Check search filter
                    searchMatch = true;
                    if ~isempty(searchText)
                        searchMatch = contains(lower(signalName), lower(searchText));
                    end

                    % Check if signal is hidden
                    isHidden = app.isSignalHidden(signalInfo);

                    % Include signal if it matches search AND is not hidden
                    if searchMatch && ~isHidden
                        filteredDerived{end+1} = signalName;
                    end
                end

                % Only create derived signals node if it has filtered signals OR no search is active
                if ~isempty(filteredDerived) || (isempty(searchText) && ~isempty(derivedNames))
                    derivedNode = uitreenode(app.SignalTree, 'Text', '⚙️ Derived Signals');
                    derivedNode.NodeData = struct('Type', 'derived_signals_folder');

                    % Add management context menu
                    derivedContextMenu = uicontextmenu(app.UIFigure);
                    uimenu(derivedContextMenu, 'Text', '📋 Operation History', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.showOperationHistory());
                    uimenu(derivedContextMenu, 'Text', '🗑️ Clear All Derived Signals', ...
                        'MenuSelectedFcn', @(src, event) app.confirmAndClearDerivedSignals());
                    uimenu(derivedContextMenu, 'Text', '👁️ Manage Hidden Signals', ...
                        'MenuSelectedFcn', @(src, event) app.showHiddenSignalsManager(), 'Separator', 'on');
                    derivedNode.ContextMenu = derivedContextMenu;

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
                        signalInfo = struct('CSVIdx', -1, 'Signal', signalName, 'IsDerived', true);
                        child.NodeData = signalInfo;

                        % UNIFIED: Use the enhanced context menu system for derived signals
                        app.attachMultiSelectionContextMenu(child);
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
                pause(0.05);
                for i = 1:length(nodesToExpand)
                    try
                        nodesToExpand{i}.expand();
                    catch
                        % Ignore expansion errors
                    end
                end
                drawnow;
            end

            % CRITICAL: Reset the tree's context menu to ensure it works
            if isempty(app.SignalTree.ContextMenu) || ~isvalid(app.SignalTree.ContextMenu)
                cm = uicontextmenu(app.UIFigure);
                app.SignalTree.ContextMenu = cm;
                app.setupMultiSelectionContextMenu();
            end

            drawnow;
        end

        function handleContextMenuAction(app, action, signalInfo)
            % Centralized handler for all context menu actions
            try
                switch action
                    case 'add'
                        app.addSignalToCurrentSubplot(signalInfo);
                    case 'remove'
                        app.removeSignalFromCurrentSubplot(signalInfo);
                    case 'preview'
                        app.showSignalPreview(signalInfo);
                    case 'set_x_axis'
                        app.setSignalAsXAxis(signalInfo);
                    case 'show_details'
                        app.showDerivedSignalDetails(signalInfo.Signal);
                    case 'export_derived'
                        app.SignalOperations.exportDerivedSignal(signalInfo.Signal);
                    case 'delete_derived'
                        app.SignalOperations.confirmDeleteDerivedSignal(signalInfo.Signal);
                    case 'export_csv'
                        app.exportSingleSignalToCSV(signalInfo);
                    case 'clear_all'
                        app.clearSpecificSignalFromAllSubplots(signalInfo);
                    otherwise
                        fprintf('Unknown context menu action: %s\n', action);
                end
            catch ME
                fprintf('Context menu action error (%s): %s\n', action, ME.message);
            end
        end

        function createStaticSignalContextMenu(app, contextMenu, signalInfo, assignedSignals)
            % Create a complete static context menu for a signal that handles multi-selection

            % Check if this signal is assigned to current subplot
            isAssigned = false;
            for k = 1:numel(assignedSignals)
                if isequal(assignedSignals{k}, signalInfo)
                    isAssigned = true;
                    break;
                end
            end

            % Assignment/Removal options - these will handle multiple signals
            if isAssigned
                uimenu(contextMenu, 'Text', '❌ Remove from Subplot', ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('remove', signalInfo));
            else
                uimenu(contextMenu, 'Text', '➕ Add to Subplot', ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('add', signalInfo));
            end

            % Preview and analysis - single signal only
            uimenu(contextMenu, 'Text', '📊 Quick Preview', ...
                'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('preview', signalInfo), ...
                'Separator', 'on');

            uimenu(contextMenu, 'Text', '📈 Set as X-Axis', ...
                'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('set_x_axis', signalInfo));

            % Multi-signal operations (only show if multiple signals selected)
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = app.getSelectedSignalsFromNodes(selectedNodes);

            if numel(selectedSignals) > 1
                multiMenu = uimenu(contextMenu, 'Text', sprintf('⚡ Multi-Signal Ops (%d selected)', numel(selectedSignals)), ...
                    'Separator', 'on');

                if numel(selectedSignals) >= 2
                    uimenu(multiMenu, 'Text', '📊 Vector Magnitude', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('vector_magnitude', signalInfo));

                    uimenu(multiMenu, 'Text', '📈 Signal Average', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('signal_average', signalInfo));
                end

                if numel(selectedSignals) == 2
                    dualMenu = uimenu(multiMenu, 'Text', '📈 Dual Operations');
                    uimenu(dualMenu, 'Text', '➕ Add (A + B)', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('add_signals', signalInfo));
                    uimenu(dualMenu, 'Text', '➖ Subtract (A - B)', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('subtract_signals', signalInfo));
                    uimenu(dualMenu, 'Text', '✖️ Multiply (A × B)', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('multiply_signals', signalInfo));
                    uimenu(dualMenu, 'Text', '➗ Divide (A ÷ B)', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('divide_signals', signalInfo));
                end
            end

            % Signal-specific options (single signal)
            if signalInfo.CSVIdx == -1  % Derived signal
                uimenu(contextMenu, 'Text', '📋 Show Operation Details', ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('show_details', signalInfo), ...
                    'Separator', 'on');

                uimenu(contextMenu, 'Text', '💾 Export Signal', ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('export_derived', signalInfo));

                uimenu(contextMenu, 'Text', '🗑️ Delete Signal', ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('delete_derived', signalInfo));
            else
                exportMenu = uimenu(contextMenu, 'Text', '💾 Export Options', 'Separator', 'on');

                if numel(selectedSignals) == 1
                    uimenu(exportMenu, 'Text', '💾 Export This Signal to CSV', ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('export_csv', signalInfo));
                else
                    uimenu(exportMenu, 'Text', sprintf('💾 Export %d Signals to CSV', numel(selectedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('export_multiple_csv', signalInfo));
                end
            end

            % Global actions
            if numel(selectedSignals) == 1
                uimenu(contextMenu, 'Text', '🗑️ Clear from All Subplots', ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('clear_all', signalInfo), ...
                    'Separator', 'on');
            else
                uimenu(contextMenu, 'Text', sprintf('🗑️ Clear %d Signals from All Subplots', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.handleMultiSignalContextMenuAction('clear_multiple_all', signalInfo), ...
                    'Separator', 'on');
            end
        end

        function handleMultiSignalContextMenuAction(app, action, clickedSignalInfo)
            % Enhanced handler for context menu actions that handles multiple selected signals

            % Get all currently selected signals
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = app.getSelectedSignalsFromNodes(selectedNodes);

            % If no multi-selection, fall back to the clicked signal
            if isempty(selectedSignals)
                selectedSignals = {clickedSignalInfo};
            end

            try
                switch action
                    case 'add'
                        % Add all selected signals to current subplot
                        app.addMultipleSignalsToCurrentSubplot(selectedSignals);

                    case 'remove'
                        % Remove all selected signals from current subplot
                        app.removeMultipleSignalsFromCurrentSubplot(selectedSignals);

                    case 'preview'
                        if numel(selectedSignals) == 1
                            app.showSignalPreview(selectedSignals{1});
                        else
                            app.previewSelectedSignals(selectedSignals);
                        end

                    case 'set_x_axis'
                        if numel(selectedSignals) == 1
                            app.setSignalAsXAxis(selectedSignals{1});
                        else
                            app.StatusLabel.Text = '⚠️ Can only set one signal as X-axis';
                            app.StatusLabel.FontColor = [0.9 0.6 0.2];
                        end

                    case 'export_csv'
                        app.exportSingleSignalToCSV(clickedSignalInfo);

                    case 'export_multiple_csv'
                        app.exportMultipleSignalsToCSV(selectedSignals);

                    case 'clear_all'
                        app.clearSpecificSignalFromAllSubplots(clickedSignalInfo);

                    case 'clear_multiple_all'
                        app.clearMultipleSignalsFromAllSubplots(selectedSignals);

                        % Multi-signal operations
                    case 'vector_magnitude'
                        app.showQuickVectorMagnitudeForSelected(selectedSignals);

                    case 'signal_average'
                        app.showQuickAverageForSelected(selectedSignals);

                    case 'add_signals'
                        if numel(selectedSignals) == 2
                            app.showDualOperationForSelected('add', ...
                                app.getSignalNameForOperations(selectedSignals{1}), ...
                                app.getSignalNameForOperations(selectedSignals{2}));
                        end

                    case 'subtract_signals'
                        if numel(selectedSignals) == 2
                            app.showDualOperationForSelected('subtract', ...
                                app.getSignalNameForOperations(selectedSignals{1}), ...
                                app.getSignalNameForOperations(selectedSignals{2}));
                        end

                    case 'multiply_signals'
                        if numel(selectedSignals) == 2
                            app.showDualOperationForSelected('multiply', ...
                                app.getSignalNameForOperations(selectedSignals{1}), ...
                                app.getSignalNameForOperations(selectedSignals{2}));
                        end

                    case 'divide_signals'
                        if numel(selectedSignals) == 2
                            app.showDualOperationForSelected('divide', ...
                                app.getSignalNameForOperations(selectedSignals{1}), ...
                                app.getSignalNameForOperations(selectedSignals{2}));
                        end

                        % Single signal operations
                    case 'show_details'
                        app.showDerivedSignalDetails(clickedSignalInfo.Signal);
                    case 'export_derived'
                        app.SignalOperations.exportDerivedSignal(clickedSignalInfo.Signal);
                    case 'delete_derived'
                        app.SignalOperations.confirmDeleteDerivedSignal(clickedSignalInfo.Signal);

                    otherwise
                        fprintf('Unknown context menu action: %s\n', action);
                end
            catch ME
                fprintf('Context menu action error (%s): %s\n', action, ME.message);
            end
        end


        function removeMultipleSignalsFromCurrentSubplot(app, signalsToRemove)
            % Remove multiple signals from current subplot
            if isempty(signalsToRemove)
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

            % Keep showing properties of selected signals
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = app.getSelectedSignalsFromNodes(selectedNodes);
            app.updateSignalPropsTable(selectedSignals);

            % Update status
            if removedCount > 0
                app.StatusLabel.Text = sprintf('❌ Removed %d signal(s) from subplot', removedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'No selected signals were assigned';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end


        function clearMultipleSignalsFromAllSubplots(app, signalsToRemove)
            % Clear multiple signals from all subplots in all tabs

            if isempty(signalsToRemove)
                return;
            end

            % Confirm action
            signalNames = cellfun(@(s) s.Signal, signalsToRemove, 'UniformOutput', false);
            answer = uiconfirm(app.UIFigure, ...
                sprintf('Remove %d signals from ALL subplots in ALL tabs?\n\nSignals: %s', ...
                numel(signalsToRemove), strjoin(signalNames, ', ')), ...
                'Confirm Clear Multiple Signals', ...
                'Options', {'Remove All', 'Cancel'}, ...
                'DefaultOption', 'Cancel', 'Icon', 'warning');

            if strcmp(answer, 'Cancel')
                return;
            end

            % Remove signals from all subplots in all tabs
            removedCount = 0;
            numTabs = numel(app.PlotManager.AxesArrays);

            for tabIdx = 1:numTabs
                if tabIdx > numel(app.PlotManager.AssignedSignals)
                    continue;
                end

                if ~isempty(app.PlotManager.AxesArrays{tabIdx})
                    numSubplots = numel(app.PlotManager.AxesArrays{tabIdx});
                else
                    continue;
                end

                for subplotIdx = 1:numSubplots
                    if subplotIdx > numel(app.PlotManager.AssignedSignals{tabIdx})
                        continue;
                    end

                    assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                    if isempty(assignedSignals)
                        continue;
                    end

                    % Filter out signals that should be removed
                    filteredSignals = {};
                    for i = 1:numel(assignedSignals)
                        signal = assignedSignals{i};
                        shouldKeep = true;

                        for j = 1:numel(signalsToRemove)
                            if isequal(signal, signalsToRemove{j})
                                shouldKeep = false;
                                removedCount = removedCount + 1;
                                break;
                            end
                        end

                        if shouldKeep
                            filteredSignals{end+1} = signal; %#ok<AGROW>
                        end
                    end

                    % Update the assignments for this subplot
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = filteredSignals;
                end
            end

            % Refresh all plots in all tabs
            for tabIdx = 1:numTabs
                app.PlotManager.refreshPlots(tabIdx);
            end

            % Clear tree selection
            app.SignalTree.SelectedNodes = [];

            % Update status
            if removedCount > 0
                app.StatusLabel.Text = sprintf('🗑️ Removed %d signal assignments across all tabs', removedCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'No selected signals were assigned to any subplots';
                app.StatusLabel.FontColor = [0.5 0.5 0.5];
            end
        end

        function selectedSignals = getSelectedSignalsFromNodes(app, selectedNodes)
            % Extract signal info from selected tree nodes, excluding folder nodes
            selectedSignals = {};

            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);

                % Skip folder nodes and operation nodes
                if isstruct(node.NodeData) && isfield(node.NodeData, 'Type')
                    nodeType = node.NodeData.Type;
                    if strcmp(nodeType, 'derived_signals_folder') || strcmp(nodeType, 'operations') || strcmp(nodeType, 'csv_folder')
                        continue;
                    end
                end

                % Include actual signals (both original and derived)
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal')
                    selectedSignals{end+1} = node.NodeData; %#ok<AGROW>
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
            % Enhanced delete method with proper cleanup

            % Clean up timers first
            app.cleanupTimers();

            % Stop any streaming operations
            if isprop(app, 'DataManager') && ~isempty(app.DataManager)
                try
                    app.DataManager.stopStreamingAll();
                catch
                    % Ignore errors during cleanup
                end
            end

            % Delete the UI figure
            if isvalid(app.UIFigure)
                delete(app.UIFigure);
            end
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

        function updateDerivedSignalContextMenu(app, contextMenu, clickedSignalInfo)
            % Dynamic context menu specifically for derived signals

            % Clear existing menu items
            delete(contextMenu.Children);

            % Get ALL selected nodes
            selectedNodes = app.SignalTree.SelectedNodes;

            % Get derived signal info from selected nodes
            selectedDerivedSignals = {};
            for k = 1:numel(selectedNodes)
                node = selectedNodes(k);

                % Only include derived signals
                if isfield(node.NodeData, 'CSVIdx') && isfield(node.NodeData, 'Signal') && ...
                        node.NodeData.CSVIdx == -1
                    selectedDerivedSignals{end+1} = node.NodeData; %#ok<AGROW>
                end
            end

            % If no valid derived signals selected, use the clicked signal
            if isempty(selectedDerivedSignals)
                selectedDerivedSignals = {clickedSignalInfo};
            end

            % Get current assignments to determine what actions are available
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            currentAssignments = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Separate assigned and unassigned derived signals
            assignedSignals = {};
            unassignedSignals = {};

            for i = 1:numel(selectedDerivedSignals)
                isAssigned = false;
                signalInfo = selectedDerivedSignals{i};

                % Check if this derived signal is assigned
                for j = 1:numel(currentAssignments)
                    currentSignal = currentAssignments{j};
                    if isstruct(currentSignal) && isstruct(signalInfo) && ...
                            currentSignal.CSVIdx == -1 && signalInfo.CSVIdx == -1 && ...
                            strcmp(currentSignal.Signal, signalInfo.Signal)
                        isAssigned = true;
                        break;
                    end
                end

                if isAssigned
                    assignedSignals{end+1} = selectedDerivedSignals{i};
                else
                    unassignedSignals{end+1} = selectedDerivedSignals{i};
                end
            end

            % ============= ASSIGNMENT/REMOVAL OPERATIONS =============
            if ~isempty(unassignedSignals)
                if numel(unassignedSignals) == 1
                    uimenu(contextMenu, 'Text', '➕ Add to Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.addSelectedSignalsToSubplot(unassignedSignals));
                else
                    uimenu(contextMenu, 'Text', sprintf('➕ Add %d Derived Signals to Subplot', numel(unassignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.addSelectedSignalsToSubplot(unassignedSignals));
                end
            end

            if ~isempty(assignedSignals)
                if numel(assignedSignals) == 1
                    uimenu(contextMenu, 'Text', '❌ Remove from Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.removeSelectedSignalsFromSubplot(assignedSignals));
                else
                    uimenu(contextMenu, 'Text', sprintf('❌ Remove %d Derived Signals from Subplot', numel(assignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.removeSelectedSignalsFromSubplot(assignedSignals));
                end
            end

            % ============= SINGLE DERIVED SIGNAL OPTIONS =============
            if numel(selectedDerivedSignals) == 1
                signalInfo = selectedDerivedSignals{1};

                uimenu(contextMenu, 'Text', '📊 Quick Preview', ...
                    'MenuSelectedFcn', @(src, event) app.showSignalPreview(signalInfo), ...
                    'Separator', 'on');

                uimenu(contextMenu, 'Text', '⚙️ Edit Properties', ...
                    'MenuSelectedFcn', @(src, event) app.editSignalProperties(signalInfo));

                % *** THIS WAS MISSING - SET AS X-AXIS FOR DERIVED SIGNALS ***
                uimenu(contextMenu, 'Text', '📈 Set as X-Axis', ...
                    'MenuSelectedFcn', @(src, event) app.setSignalAsXAxis(signalInfo));

                % Derived signal specific options
                uimenu(contextMenu, 'Text', '📋 Show Operation Details', ...
                    'MenuSelectedFcn', @(src, event) app.showDerivedSignalDetails(signalInfo.Signal), ...
                    'Separator', 'on');

                uimenu(contextMenu, 'Text', '💾 Export Signal', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.exportDerivedSignal(signalInfo.Signal));

                uimenu(contextMenu, 'Text', '🗑️ Delete Signal', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.confirmDeleteDerivedSignal(signalInfo.Signal));

                uimenu(contextMenu, 'Text', '🗑️ Clear from All Subplots', ...
                    'MenuSelectedFcn', @(src, event) app.clearSpecificSignalFromAllSubplots(signalInfo), ...
                    'Separator', 'on');

            elseif numel(selectedDerivedSignals) > 1
                uimenu(contextMenu, 'Text', sprintf('📊 Preview %d Derived Signals', numel(selectedDerivedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.previewSelectedSignals(selectedDerivedSignals), ...
                    'Separator', 'on');

                % Multi-derived signal operations
                uimenu(contextMenu, 'Text', '⚡ Multi-Signal Operations', 'Separator', 'on');

                uimenu(contextMenu, 'Text', '📊 Vector Magnitude', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickVectorMagnitudeForSelected(selectedDerivedSignals));

                uimenu(contextMenu, 'Text', '📈 Signal Average', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickAverageForSelected(selectedDerivedSignals));

                uimenu(contextMenu, 'Text', '💾 Export All to CSV', ...
                    'MenuSelectedFcn', @(src, event) app.exportMultipleSignalsToCSV(selectedDerivedSignals));
            end

            % ============= FURTHER OPERATIONS ON DERIVED SIGNALS =============
            if numel(selectedDerivedSignals) == 1
                % Single derived signal operations
                derivedOpsMenu = uimenu(contextMenu, 'Text', '🔢 Further Operations', 'Separator', 'on');

                signalInfo = selectedDerivedSignals{1};
                signalName = app.getSignalNameForOperations(signalInfo);

                uimenu(derivedOpsMenu, 'Text', '∂ Derivative of Derived Signal', ...
                    'MenuSelectedFcn', @(src, event) app.showDerivativeForSelected(signalName));

                uimenu(derivedOpsMenu, 'Text', '∫ Integral of Derived Signal', ...
                    'MenuSelectedFcn', @(src, event) app.showIntegralForSelected(signalName));

                uimenu(derivedOpsMenu, 'Text', '🌊 Moving Average', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickMovingAverageForSelected(signalInfo));

                uimenu(derivedOpsMenu, 'Text', '📏 RMS Calculation', ...
                    'MenuSelectedFcn', @(src, event) app.showQuickRMSForSelected(signalInfo));

            elseif numel(selectedDerivedSignals) == 2
                % Dual derived signal operations
                dualOpsMenu = uimenu(contextMenu, 'Text', '📈 Dual Operations', 'Separator', 'on');

                signal1Name = app.getSignalNameForOperations(selectedDerivedSignals{1});
                signal2Name = app.getSignalNameForOperations(selectedDerivedSignals{2});

                uimenu(dualOpsMenu, 'Text', '➕ Add Derived Signals', ...
                    'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('add', signal1Name, signal2Name));

                uimenu(dualOpsMenu, 'Text', '➖ Subtract Derived Signals', ...
                    'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('subtract', signal1Name, signal2Name));

                uimenu(dualOpsMenu, 'Text', '✖️ Multiply Derived Signals', ...
                    'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('multiply', signal1Name, signal2Name));

                uimenu(dualOpsMenu, 'Text', '➗ Divide Derived Signals', ...
                    'MenuSelectedFcn', @(src, event) app.showDualOperationForSelected('divide', signal1Name, signal2Name));
            end

            % ============= SELECTION INFO =============
            if numel(selectedDerivedSignals) > 1
                uimenu(contextMenu, 'Text', sprintf('📋 %d derived signals selected', numel(selectedDerivedSignals)), ...
                    'Enable', 'off', 'Separator', 'on');
            elseif numel(selectedDerivedSignals) == 1
                signalInfo = selectedDerivedSignals{1};
                uimenu(contextMenu, 'Text', sprintf('📋 Derived signal: %s', signalInfo.Signal), ...
                    'Enable', 'off', 'Separator', 'on');
            end
        end
        % =========================================================================
        % IMPROVED SESSION VALIDATION WITH DEBUGGING - Add to SignalViewerApp.m
        % =========================================================================
        function saveSession(app)
            [file, path] = uiputfile('*.mat', 'Save Session');
            if isequal(file, 0), return; end

            try
                session = struct();

                % === METADATA ===
                session.SessionVersion = '3.0';
                session.MatlabVersion = version();
                session.SaveTimestamp = datetime('now');

                % === DATA MANAGER STATE ===
                session.CSVFilePaths = app.safeGetProperty('DataManager', 'CSVFilePaths', {});
                session.SignalNames = app.safeGetProperty('DataManager', 'SignalNames', {});
                session.SignalScaling = app.safeGetProperty('DataManager', 'SignalScaling', containers.Map());
                session.StateSignals = app.safeGetProperty('DataManager', 'StateSignals', containers.Map());
                session.CSVColors = app.safeGetProperty('CSVColors', {});

                % === PLOT MANAGER STATE ===
                session.AssignedSignals = app.safeGetProperty('PlotManager', 'AssignedSignals', {});
                session.TabLayouts = app.safeGetProperty('PlotManager', 'TabLayouts', {[2,1]});
                session.CurrentTabIdx = app.safeGetProperty('PlotManager', 'CurrentTabIdx', 1);
                session.SelectedSubplotIdx = app.safeGetProperty('PlotManager', 'SelectedSubplotIdx', 1);
                session.XAxisSignals = app.safeGetProperty('PlotManager', 'XAxisSignals', {});
                session.TabLinkedAxes = app.safeGetProperty('PlotManager', 'TabLinkedAxes', []);
                session.CustomYLabels = app.safeGetProperty('PlotManager', 'CustomYLabels', containers.Map());

                % === TAB CONTROLS STATE ===
                session.TabControlsData = app.extractTabControlsData();

                % === UI STATE ===
                session.SubplotCaptions = app.safeGetProperty('SubplotCaptions', {});
                session.SubplotDescriptions = app.safeGetProperty('SubplotDescriptions', {});
                session.SubplotTitles = app.safeGetProperty('SubplotTitles', {});
                session.SubplotMetadata = app.safeGetProperty('SubplotMetadata', {});
                session.SignalStyles = app.safeGetProperty('SignalStyles', struct());
                session.HiddenSignals = app.safeGetProperty('HiddenSignals', containers.Map());
                session.ExpandedTreeNodes = app.safeGetProperty('ExpandedTreeNodes', string.empty);

                % === PDF SETTINGS ===
                session.PDFReportTitle = app.safeGetProperty('PDFReportTitle', 'Signal Analysis Report');
                session.PDFReportAuthor = app.safeGetProperty('PDFReportAuthor', '');
                session.PDFFigureLabel = app.safeGetProperty('PDFFigureLabel', 'Figure');
                session.PDFReportLanguage = app.safeGetProperty('PDFReportLanguage', 'English');

                % === PPT SETTINGS (reuse PDF defaults) ===
                session.PPTReportTitle     = app.safeGetProperty('PPTReportTitle', session.PDFReportTitle);
                session.PPTReportAuthor    = app.safeGetProperty('PPTReportAuthor', session.PDFReportAuthor);
                session.PPTFigureLabel     = app.safeGetProperty('PPTFigureLabel', session.PDFFigureLabel);
                session.PPTReportLanguage  = app.safeGetProperty('PPTReportLanguage', session.PDFReportLanguage);


                % === DERIVED SIGNALS ===
                if app.hasValidProperty('SignalOperations')
                    session.DerivedSignals = app.safeGetProperty('SignalOperations', 'DerivedSignals', containers.Map());
                    session.OperationHistory = app.safeGetProperty('SignalOperations', 'OperationHistory', {});
                    session.OperationCounter = app.safeGetProperty('SignalOperations', 'OperationCounter', 0);
                else
                    session.DerivedSignals = containers.Map();
                    session.OperationHistory = {};
                    session.OperationCounter = 0;
                end

                % === LINKING SYSTEM ===
                if app.hasValidProperty('LinkingManager')
                    session.LinkedGroups = app.safeGetProperty('LinkingManager', 'LinkedGroups', {});
                    session.AutoLinkEnabled = app.safeGetProperty('LinkingManager', 'AutoLinkEnabled', false);
                    session.LinkingMode = app.safeGetProperty('LinkingManager', 'LinkingMode', 'nodes');
                else
                    session.LinkedGroups = {};
                    session.AutoLinkEnabled = false;
                    session.LinkingMode = 'nodes';
                end

                % === VALIDATION ===
                session.NumTabs = numel(session.TabLayouts);
                session.NumCSVs = numel(session.CSVFilePaths);
                session.NumSignals = numel(session.SignalNames);

                session.TupleSignals = app.safeGetProperty('PlotManager', 'TupleSignals', {});
                session.TupleMode = app.safeGetProperty('PlotManager', 'TupleMode', {});

                % === SAVE ===
                save(fullfile(path, file), 'session', '-v7.3');

                app.StatusLabel.Text = sprintf('✅ Session saved: %s', file);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                app.StatusLabel.Text = sprintf('❌ Save failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                app.logError('Session Save', ME);
            end

            app.restoreFocus();
        end

        function tabControlsData = extractTabControlsData(app)
            % Extract tab controls data safely
            tabControlsData = {};
            try
                if app.hasValidProperty('PlotManager') && isprop(app.PlotManager, 'TabControls')
                    tabControls = app.PlotManager.TabControls;
                    tabControlsData = cell(1, numel(tabControls));

                    for i = 1:numel(tabControls)
                        if ~isempty(tabControls{i}) && isstruct(tabControls{i})
                            controls = tabControls{i};
                            data = struct();

                            if isfield(controls, 'RowsSpinner') && isvalid(controls.RowsSpinner)
                                data.RowsValue = controls.RowsSpinner.Value;
                            else
                                data.RowsValue = 2;
                            end

                            if isfield(controls, 'ColsSpinner') && isvalid(controls.ColsSpinner)
                                data.ColsValue = controls.ColsSpinner.Value;
                            else
                                data.ColsValue = 1;
                            end

                            if isfield(controls, 'LinkAxesToggle') && isvalid(controls.LinkAxesToggle)
                                data.LinkAxesValue = controls.LinkAxesToggle.Value;
                            else
                                data.LinkAxesValue = false;
                            end

                            tabControlsData{i} = data;
                        end
                    end
                end
            catch ME
                fprintf('Warning: Could not extract tab controls data: %s\n', ME.message);
                tabControlsData = {};
            end
        end

        function tf = hasValidProperty(app, propName)
            % Check if property exists and is valid
            tf = isprop(app, propName) && ~isempty(app.(propName)) && isvalid(app.(propName));
        end

        function value = safeGetProperty(app, varargin)
            % Enhanced safe property getter with containers.Map support

            try
                if nargin == 3  % app.safeGetProperty(propName, defaultValue)
                    propName = varargin{1};
                    defaultValue = varargin{2};

                    if isprop(app, propName)
                        propValue = app.(propName);
                        if ~isempty(propValue)
                            value = propValue;
                        else
                            value = defaultValue;
                        end
                    else
                        value = defaultValue;
                    end

                elseif nargin == 4  % app.safeGetProperty(subObj, propName, defaultValue)
                    subObjName = varargin{1};
                    propName = varargin{2};
                    defaultValue = varargin{3};

                    if isprop(app, subObjName) && ~isempty(app.(subObjName)) && ...
                            isprop(app.(subObjName), propName)
                        propValue = app.(subObjName).(propName);
                        if ~isempty(propValue)
                            value = propValue;
                        else
                            value = defaultValue;
                        end
                    else
                        value = defaultValue;
                    end
                else
                    error('Invalid number of arguments');
                end

                % Special handling for containers.Map
                if isa(value, 'containers.Map') && value.Count == 0
                    value = defaultValue;
                end

            catch
                value = varargin{end};  % Use last argument as default
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

                % === VALIDATE SESSION ===
                if ~app.validateSession(session)
                    return;
                end

                % === CRITICAL: RESTORE IN CORRECT ORDER ===
                % 1. Clear current state
                app.clearCurrentSession();

                % 2. Restore PLOT STRUCTURE FIRST (before loading data)
                app.restorePlotStructureFirst(session);

                % 3. Then restore data and other components
                app.restoreDataManager(session);
                app.restoreSignalOperations(session);
                app.restoreLinkingManager(session);

                % 4. Restore UI state
                app.restoreUIState(session);

                % 5. Finalize
                app.finalizeSessionLoad(session);

                app.StatusLabel.Text = sprintf('✅ Session loaded: %s', file);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                app.StatusLabel.Text = sprintf('❌ Load failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                app.logError('Session Load', ME);

                % Show detailed error for debugging
                fprintf('Session Load Error Details:\n');
                fprintf('Message: %s\n', ME.message);
                for i = 1:length(ME.stack)
                    fprintf('  %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
                end
            end

            app.restoreFocus();
        end

        function restorePlotStructureFirst(app, session)
            % Restore plot structure without refreshing plots

            % Remove + tab temporarily
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
            end

            % Create required tabs
            requiredTabs = numel(session.TabLayouts);
            while numel(app.PlotManager.PlotTabs) < requiredTabs
                app.PlotManager.addNewTab();
            end

            % CRITICAL: Initialize AssignedSignals FIRST with correct structure
            app.PlotManager.TabLayouts = session.TabLayouts;
            app.PlotManager.AssignedSignals = cell(1, requiredTabs);

            % Initialize each tab's assignments
            for tabIdx = 1:requiredTabs
                layout = session.TabLayouts{tabIdx};
                numSubplots = layout(1) * layout(2);
                app.PlotManager.AssignedSignals{tabIdx} = cell(numSubplots, 1);

                % Initialize empty assignments
                for subplotIdx = 1:numSubplots
                    app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = {};
                end
            end

            % Now restore the actual assignments from session
            if isfield(session, 'AssignedSignals') && ~isempty(session.AssignedSignals)
                for tabIdx = 1:min(requiredTabs, numel(session.AssignedSignals))
                    if ~isempty(session.AssignedSignals{tabIdx})
                        sessionAssignments = session.AssignedSignals{tabIdx};
                        for subplotIdx = 1:min(numel(app.PlotManager.AssignedSignals{tabIdx}), numel(sessionAssignments))
                            if ~isempty(sessionAssignments{subplotIdx})
                                app.PlotManager.AssignedSignals{tabIdx}{subplotIdx} = sessionAssignments{subplotIdx};
                            end
                        end
                    end
                end
            end

            % Set other PlotManager properties
            app.PlotManager.CurrentTabIdx = min(session.CurrentTabIdx, requiredTabs);
            app.PlotManager.SelectedSubplotIdx = session.SelectedSubplotIdx;

            % Restore X-axis signals
            if isfield(session, 'XAxisSignals')
                app.PlotManager.XAxisSignals = session.XAxisSignals;
            end

            % Restore per-tab linking
            if isfield(session, 'TabLinkedAxes')
                app.PlotManager.TabLinkedAxes = session.TabLinkedAxes;
            end

            % Restore custom Y labels
            if isfield(session, 'CustomYLabels')
                try
                    app.PlotManager.CustomYLabels = session.CustomYLabels;
                catch
                    app.PlotManager.CustomYLabels = containers.Map();
                end
            else
                app.PlotManager.CustomYLabels = containers.Map();
            end

            % NOW create the visual subplot structure
            for tabIdx = 1:requiredTabs
                layout = session.TabLayouts{tabIdx};
                app.PlotManager.createSubplotsForTab(tabIdx, layout(1), layout(2));
            end

            % Restore tab controls
            if isfield(session, 'TabControlsData')
                app.restoreTabControls(session.TabControlsData);
            end
        end


        function logError(app, context, ME)
            % Enhanced error logging
            fprintf('=== %s Error ===\n', context);
            fprintf('Message: %s\n', ME.message);
            fprintf('Stack:\n');
            for i = 1:length(ME.stack)
                fprintf('  %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
            end
            fprintf('================\n');
        end

        function finalizeSessionLoad(app, session)
            % Finalize session loading

            % Rebuild signal tree
            app.buildSignalTree();

            % Refresh all plots
            for tabIdx = 1:numel(app.PlotManager.TabLayouts)
                app.PlotManager.refreshPlots(tabIdx);
            end

            % Apply per-tab axis linking
            if isfield(session, 'TabLinkedAxes')
                for tabIdx = 1:length(app.PlotManager.TabLinkedAxes)
                    if tabIdx <= length(app.PlotManager.TabLinkedAxes) && app.PlotManager.TabLinkedAxes(tabIdx)
                        app.PlotManager.linkTabAxes(tabIdx);
                    end
                end
            end

            if isfield(session, 'CustomYLabels')
                try
                    app.PlotManager.CustomYLabels = session.CustomYLabels;
                catch
                    % Handle conversion issues (e.g., from struct to containers.Map)
                    app.PlotManager.CustomYLabels = containers.Map();
                    if isstruct(session.CustomYLabels)
                        fieldNames = fieldnames(session.CustomYLabels);
                        for i = 1:length(fieldNames)
                            app.PlotManager.CustomYLabels(fieldNames{i}) = session.CustomYLabels.(fieldNames{i});
                        end
                    end
                end
            else
                app.PlotManager.CustomYLabels = containers.Map();
            end

            % Restore tree expanded state
            if isfield(session, 'ExpandedTreeNodes')
                app.restoreTreeExpandedState();
            end
            if isfield(session, 'TupleSignals')
                app.PlotManager.TupleSignals = session.TupleSignals;
            else
                app.PlotManager.TupleSignals = {};
            end

            if isfield(session, 'TupleMode')
                app.PlotManager.TupleMode = session.TupleMode;
            else
                app.PlotManager.TupleMode = {};
            end
            % Ensure + tab at end
            app.PlotManager.ensurePlusTabAtEnd();
            app.PlotManager.updateTabTitles();

            % Set current tab
            if app.PlotManager.CurrentTabIdx <= numel(app.PlotManager.PlotTabs)
                app.MainTabGroup.SelectedTab = app.PlotManager.PlotTabs{app.PlotManager.CurrentTabIdx};
            end

            % Highlight current subplot
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, app.PlotManager.SelectedSubplotIdx);

            % Update status
            fprintf('Session loaded successfully: %d tabs, %d CSVs, %d signals\n', ...
                session.NumTabs, session.NumCSVs, session.NumSignals);
        end

        function restorePlotStructure(app, session)
            % Restore plot structure (tabs, layouts, assignments)

            % Remove + tab temporarily
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
            end

            % Create required tabs
            requiredTabs = numel(session.TabLayouts);
            while numel(app.PlotManager.PlotTabs) < requiredTabs
                app.PlotManager.addNewTab();
            end


            % Restore custom Y-axis labels with migration support
            if app.hasValidProperty('PlotManager')
                app.PlotManager.migrateCustomYLabels(session);
                app.PlotManager.validateCustomYLabels();
            end
            % Restore layouts and assignments
            app.PlotManager.TabLayouts = session.TabLayouts;
            app.PlotManager.AssignedSignals = session.AssignedSignals;
            app.PlotManager.CurrentTabIdx = min(session.CurrentTabIdx, requiredTabs);
            app.PlotManager.SelectedSubplotIdx = session.SelectedSubplotIdx;

            % Restore X-axis signals
            if isfield(session, 'XAxisSignals')
                app.PlotManager.XAxisSignals = session.XAxisSignals;
            end

            % Restore per-tab linking
            if isfield(session, 'TabLinkedAxes')
                app.PlotManager.TabLinkedAxes = session.TabLinkedAxes;
            end

            % Recreate each tab with correct layout
            for tabIdx = 1:requiredTabs
                layout = session.TabLayouts{tabIdx};
                app.PlotManager.createSubplotsForTab(tabIdx, layout(1), layout(2));
            end

            % Restore tab controls
            if isfield(session, 'TabControlsData')
                app.restoreTabControls(session.TabControlsData);
            end
        end


        function restoreTabControls(app, tabControlsData)
            % Restore tab controls state
            for i = 1:min(numel(tabControlsData), numel(app.PlotManager.TabControls))
                if ~isempty(tabControlsData{i}) && ~isempty(app.PlotManager.TabControls{i})
                    data = tabControlsData{i};
                    controls = app.PlotManager.TabControls{i};

                    if isfield(data, 'RowsValue') && isfield(controls, 'RowsSpinner')
                        controls.RowsSpinner.Value = data.RowsValue;
                    end

                    if isfield(data, 'ColsValue') && isfield(controls, 'ColsSpinner')
                        controls.ColsSpinner.Value = data.ColsValue;
                    end

                    if isfield(data, 'LinkAxesValue') && isfield(controls, 'LinkAxesToggle')
                        controls.LinkAxesToggle.Value = data.LinkAxesValue;
                    end
                end
            end
        end

        function restoreUIState(app, session)
            % Restore UI state
            uiStateFields = {
                'SubplotCaptions', 'SubplotDescriptions', 'SubplotTitles', ...
                'SubplotMetadata', 'SignalStyles', 'HiddenSignals', ...
                'ExpandedTreeNodes', ...
                % PDF fields
                'PDFReportTitle', 'PDFReportAuthor', 'PDFFigureLabel', 'PDFReportLanguage', ...
                % PPT fields
                'PPTReportTitle', 'PPTReportAuthor', 'PPTFigureLabel', 'PPTReportLanguage'
                };

            for i = 1:numel(uiStateFields)
                field = uiStateFields{i};
                if isfield(session, field)
                    try
                        app.(field) = session.(field);
                    catch ME
                        fprintf('Warning: Could not restore %s: %s\n', field, ME.message);
                    end
                end
            end
        end

        function restoreLinkingManager(app, session)
            % Restore LinkingManager state
            if app.hasValidProperty('LinkingManager')
                if isfield(session, 'LinkedGroups')
                    app.LinkingManager.LinkedGroups = session.LinkedGroups;
                end

                if isfield(session, 'AutoLinkEnabled')
                    app.LinkingManager.AutoLinkEnabled = session.AutoLinkEnabled;
                end

                if isfield(session, 'LinkingMode')
                    app.LinkingManager.LinkingMode = session.LinkingMode;
                end
            end
        end

        function restoreSignalOperations(app, session)
            % Restore SignalOperations state
            if app.hasValidProperty('SignalOperations')
                if isfield(session, 'DerivedSignals')
                    app.SignalOperations.DerivedSignals = session.DerivedSignals;

                    % Add derived signal names to main signal list
                    derivedNames = keys(session.DerivedSignals);
                    for i = 1:length(derivedNames)
                        if ~ismember(derivedNames{i}, app.DataManager.SignalNames)
                            app.DataManager.SignalNames{end+1} = derivedNames{i};
                        end
                    end
                end

                if isfield(session, 'OperationHistory')
                    app.SignalOperations.OperationHistory = session.OperationHistory;
                end

                if isfield(session, 'OperationCounter')
                    app.SignalOperations.OperationCounter = session.OperationCounter;
                end
            end
        end

        function restoreDataManager(app, session)
            % Restore DataManager state without triggering plot refresh

            app.DataManager.CSVFilePaths = session.CSVFilePaths;
            app.DataManager.SignalNames = session.SignalNames;
            app.DataManager.SignalScaling = session.SignalScaling;
            app.DataManager.StateSignals = session.StateSignals;

            % Reload CSV data WITHOUT refreshing plots
            app.DataManager.DataTables = cell(1, numel(session.CSVFilePaths));
            for i = 1:numel(session.CSVFilePaths)
                if isfile(session.CSVFilePaths{i})
                    app.readInitialDataSilent(i);  % Use silent version
                end
            end

            if isfield(session, 'CSVColors')
                app.CSVColors = session.CSVColors;
            else
                app.CSVColors = app.assignCSVColors(numel(session.CSVFilePaths));
            end
        end

        function readInitialDataSilent(app, idx)
            % Read CSV data without triggering UI updates

            filePath = app.DataManager.CSVFilePaths{idx};
            if ~isfile(filePath)
                app.DataManager.DataTables{idx} = [];
                return;
            end

            try
                fileInfo = dir(filePath);
                if ~isstruct(fileInfo) || isempty(fileInfo) || fileInfo(1).bytes == 0
                    app.DataManager.DataTables{idx} = [];
                    return;
                end

                opts = detectImportOptions(filePath);
                if isempty(opts.VariableNames)
                    app.DataManager.DataTables{idx} = [];
                    return;
                end

                opts = setvartype(opts, 'double');
                T = readtable(filePath, opts);

                if ~istable(T) || isempty(T)
                    app.DataManager.DataTables{idx} = [];
                    return;
                end

                % Validate CSV format
                if ~app.DataManager.validateCSVFormat(T, filePath)
                    app.DataManager.DataTables{idx} = [];
                    return;
                end

                % Set first column as Time
                if ~isempty(T.Properties.VariableNames)
                    T.Properties.VariableNames{1} = 'Time';
                else
                    app.DataManager.DataTables{idx} = [];
                    return;
                end

                app.DataManager.DataTables{idx} = T;
                app.DataManager.LastReadRows{idx} = height(T);

                % Update signal names
                allSignals = {};
                for k = 1:numel(app.DataManager.DataTables)
                    if ~isempty(app.DataManager.DataTables{k})
                        allSignals = union(allSignals, setdiff(app.DataManager.DataTables{k}.Properties.VariableNames, {'Time'}));
                    end
                end
                app.DataManager.SignalNames = allSignals;
                app.DataManager.initializeSignalMaps();

                % DON'T refresh plots or build signal tree here

            catch ME
                fprintf('Silent data read failed for CSV %d: %s\n', idx, ME.message);
                app.DataManager.DataTables{idx} = [];
            end
        end

        function clearCurrentSession(app)
            % Clear current session state
            try
                app.DataManager.stopStreamingAll();
                %                 app.DataManager.clearData();
                app.PlotManager.AssignedSignals = {};
                app.SignalTree.Children.delete();
            catch ME
                fprintf('Warning during session clear: %s\n', ME.message);
            end
        end

        function tf = validateSession(app, session)
            % Validate session before loading
            tf = true;

            try
                % Check version compatibility
                if isfield(session, 'SessionVersion')
                    if str2double(session.SessionVersion) < 2.0
                        answer = uiconfirm(app.UIFigure, ...
                            'This session was saved with an older version. Continue loading?', ...
                            'Version Compatibility', ...
                            'Options', {'Continue', 'Cancel'}, ...
                            'DefaultOption', 'Cancel');
                        if strcmp(answer, 'Cancel')
                            tf = false;
                            return;
                        end
                    end
                end

                % Check for missing files
                if isfield(session, 'CSVFilePaths')
                    missingFiles = {};
                    for i = 1:numel(session.CSVFilePaths)
                        if ~isfile(session.CSVFilePaths{i})
                            missingFiles{end+1} = session.CSVFilePaths{i};
                        end
                    end

                    if ~isempty(missingFiles)
                        answer = uiconfirm(app.UIFigure, ...
                            sprintf('Some CSV files are missing. Continue?\n\nMissing: %s', ...
                            strjoin(missingFiles, '\n')), ...
                            'Missing Files', ...
                            'Options', {'Continue', 'Cancel'}, ...
                            'DefaultOption', 'Continue');
                        if strcmp(answer, 'Cancel')
                            tf = false;
                            return;
                        end
                    end
                end

            catch ME
                uialert(app.UIFigure, sprintf('Session validation failed: %s', ME.message), 'Validation Error');
                tf = false;
            end
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
            % Simplified context menu setup for MATLAB 2021b
            % Individual nodes get their own context menus in buildSignalTree

            % Create a simple tree-level context menu for empty areas
            treeContextMenu = uicontextmenu(app.UIFigure);
            uimenu(treeContextMenu, 'Text', '🔍 Advanced Signal Filter', ...
                'MenuSelectedFcn', @(src, event) app.showAdvancedSignalFilter());
            uimenu(treeContextMenu, 'Text', '🔄 Refresh Signal Tree', ...
                'MenuSelectedFcn', @(src, event) app.buildSignalTree());

            % Only assign to tree for empty area clicks
            app.SignalTree.ContextMenu = treeContextMenu;

            % Note: Individual signal nodes get their own context menus in buildSignalTree
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

            if numel(selectedSignals) == 1
                signalInfo = selectedSignals{1};  % has fields: Signal, CSVIdx
                uimenu(app.SignalTree.ContextMenu, 'Text', '📈 Set as X-Axis', ...
                    'MenuSelectedFcn', @(src, event) app.setSignalAsXAxis(signalInfo));
            end

        end

        function setSignalAsXAxis(app, signalInfo)
            % Get the active subplot location
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Overwrite the X-axis assignment for this subplot only
            app.PlotManager.XAxisSignals{tabIdx, subplotIdx} = signalInfo;

            % Refresh only the current tab
            app.PlotManager.refreshPlots(tabIdx);
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


        % 5. Add new method to handle removing selected signals:
        function removeSelectedSignalsFromTable(app)
            % Enhanced version that handles both regular signals and tuples
            data = app.SignalPropsTable.Data;
            if isempty(data)
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Check if we're in tuple mode
            isTupleMode = app.isSubplotInTupleMode(tabIdx, subplotIdx);

            if isTupleMode
                % TUPLE MODE: Remove selected tuples
                app.removeSelectedTuples(tabIdx, subplotIdx, data);
            else
                % REGULAR MODE: Remove selected signals (existing logic)
                app.removeSelectedRegularSignals(tabIdx, subplotIdx, data);
            end
        end

        % ADD new method for removing selected tuples:
        function removeSelectedTuples(app, tabIdx, subplotIdx, data)
            % Remove selected tuples from tuple mode subplot

            if tabIdx > numel(app.PlotManager.TupleSignals) || ...
                    subplotIdx > numel(app.PlotManager.TupleSignals{tabIdx}) || ...
                    isempty(app.PlotManager.TupleSignals{tabIdx}{subplotIdx})
                app.StatusLabel.Text = '⚠️ No tuples to remove';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Find which tuples are selected for removal
            tuplesToRemove = [];
            selectedTupleNames = {};

            for i = 1:size(data, 1)
                if size(data, 2) >= 1 && data{i,1} % Checkbox is checked
                    if size(data, 2) >= 2
                        tupleName = data{i,2}; % Tuple name is in column 2
                        selectedTupleNames{end+1} = tupleName;
                        tuplesToRemove(end+1) = i;
                    end
                end
            end

            if isempty(tuplesToRemove)
                app.StatusLabel.Text = '⚠️ No tuples selected for removal';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Confirm removal if multiple tuples
            if numel(tuplesToRemove) > 1
                answer = uiconfirm(app.UIFigure, ...
                    sprintf('Remove %d selected tuples from subplot?', numel(tuplesToRemove)), ...
                    'Confirm Tuple Removal', ...
                    'Options', {'Remove', 'Cancel'}, ...
                    'DefaultOption', 'Remove', 'Icon', 'question');

                if strcmp(answer, 'Cancel')
                    return;
                end
            end

            % Remove the selected tuples (in reverse order to maintain indices)
            currentTuples = app.PlotManager.TupleSignals{tabIdx}{subplotIdx};
            for i = length(tuplesToRemove):-1:1
                tupleIdx = tuplesToRemove(i);
                if tupleIdx <= numel(currentTuples)
                    currentTuples(tupleIdx) = [];
                end
            end

            % Update tuple assignments
            app.PlotManager.TupleSignals{tabIdx}{subplotIdx} = currentTuples;

            % If no tuples left, exit tuple mode
            if isempty(currentTuples)
                app.PlotManager.TupleMode{tabIdx}{subplotIdx} = false;
                app.StatusLabel.Text = sprintf('🗑️ Removed %d tuple(s) - switched back to regular mode', numel(tuplesToRemove));
            else
                app.StatusLabel.Text = sprintf('🗑️ Removed %d tuple(s) from subplot', numel(tuplesToRemove));
            end
            app.StatusLabel.FontColor = [0.2 0.6 0.9];

            % Refresh visuals
            app.PlotManager.refreshPlots(tabIdx);

            % Update the properties table to show remaining tuples
            app.updateTuplePropsTable(tabIdx, subplotIdx);
        end

        % ADD new method for removing regular signals (extracted from original logic):
        function removeSelectedRegularSignals(app, tabIdx, subplotIdx, data)
            % Remove selected regular signals (original logic)

            currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

            % Find which signals are selected for removal
            signalsToRemove = {};
            selectedSignalNames = {};

            for i = 1:size(data, 1)
                if data{i,1} % Checkbox is checked
                    signalName = data{i,2};
                    selectedSignalNames{end+1} = signalName;

                    % Find the corresponding signal info in current assignments
                    for j = 1:numel(currentAssignments)
                        if strcmp(currentAssignments{j}.Signal, signalName)
                            signalsToRemove{end+1} = currentAssignments{j};
                            break;
                        end
                    end
                end
            end

            if isempty(signalsToRemove)
                app.StatusLabel.Text = '⚠️ No signals selected for removal';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Confirm removal if multiple signals
            if numel(signalsToRemove) > 1
                answer = uiconfirm(app.UIFigure, ...
                    sprintf('Remove %d selected signals from subplot?', numel(signalsToRemove)), ...
                    'Confirm Removal', ...
                    'Options', {'Remove', 'Cancel'}, ...
                    'DefaultOption', 'Remove', 'Icon', 'question');

                if strcmp(answer, 'Cancel')
                    return;
                end
            end

            % Remove the selected signals
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

            % Update the properties table to show remaining signals
            app.updateSignalPropsTable(newAssignments);

            % Update status
            app.StatusLabel.Text = sprintf('🗑️ Removed %d signal(s) from subplot', removedCount);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        % ALSO UPDATE the updateRemoveButtonState method to work with tuple mode:
        function updateRemoveButtonState(app)
            % Enable/disable remove button based on checkbox selections
            data = app.SignalPropsTable.Data;

            if isempty(data)
                app.RemoveSelectedSignalsButton.Enable = 'off';
                return;
            end

            % Check if any checkboxes are selected
            hasSelection = false;
            for i = 1:size(data, 1)
                if size(data, 2) >= 1 && data{i,1} % Checkbox in first column
                    hasSelection = true;
                    break;
                end
            end

            % Check if we're in tuple mode to set appropriate button text
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            isTupleMode = app.isSubplotInTupleMode(tabIdx, subplotIdx);

            if hasSelection
                app.RemoveSelectedSignalsButton.Enable = 'on';
                if isTupleMode
                    app.RemoveSelectedSignalsButton.Text = '🗑️ Remove Selected Tuples';
                else
                    app.RemoveSelectedSignalsButton.Text = '🗑️ Remove Selected Signals';
                end
            else
                app.RemoveSelectedSignalsButton.Enable = 'off';
                if isTupleMode
                    app.RemoveSelectedSignalsButton.Text = '🗑️ Remove Selected Tuples';
                else
                    app.RemoveSelectedSignalsButton.Text = '🗑️ Remove Selected Signals';
                end
            end
        end

        function onSignalPropsCellSelect(app, event)
            % Handle color picker for Color column and checkbox updates
            if isempty(event.Indices), return; end

            row = event.Indices(1);
            col = event.Indices(2);

            if col == 5 % Color column
                data = app.SignalPropsTable.Data;
                sigName = data{row,2};
                oldColor = str2num(data{row,5}); %#ok<ST2NM>
                if isempty(oldColor), oldColor = [0 0.4470 0.7410]; end
                newColor = uisetcolor(oldColor, sprintf('Pick color for %s', sigName));
                if length(newColor) == 3 % user did not cancel
                    data{row,5} = mat2str(newColor);
                    app.SignalPropsTable.Data = data;
                    if isempty(app.SignalStyles), app.SignalStyles = struct(); end
                    if ~isfield(app.SignalStyles, sigName), app.SignalStyles.(sigName) = struct(); end
                    app.SignalStyles.(sigName).Color = newColor;
                    app.PlotManager.refreshPlots();
                end
            elseif col == 1 % Checkbox column
                % Update remove button state when checkbox is clicked
                pause(0.01); % Small delay for checkbox state to update
                app.updateRemoveButtonState();
            end
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


        function addMultipleSignalsToCurrentSubplot(app, signalsToAdd)
            % Enhanced method that handles both regular and tuple mode
            if isempty(signalsToAdd)
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % ADD THIS TUPLE MODE CHECK AT THE BEGINNING:
            % =============================================
            % Check if we're in tuple mode for this subplot
            isTupleMode = false;
            if tabIdx <= numel(app.PlotManager.TupleMode) && ...
                    subplotIdx <= numel(app.PlotManager.TupleMode{tabIdx}) && ...
                    ~isempty(app.PlotManager.TupleMode{tabIdx})
                isTupleMode = app.PlotManager.TupleMode{tabIdx}{subplotIdx};
            end

            if isTupleMode
                % TUPLE MODE: Handle pairs of signals as X-Y tuples
                if numel(signalsToAdd) < 2
                    app.StatusLabel.Text = '⚠️ X-Y mode: Please select exactly 2 signals (X and Y)';
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                    return;
                elseif numel(signalsToAdd) > 2
                    app.StatusLabel.Text = '⚠️ X-Y mode: Too many signals selected. Using first 2 as X-Y pair.';
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                    signalsToAdd = signalsToAdd(1:2); % Take only first 2
                    return;
                else
                    signalsToAdd = signalsToAdd(1:2); % Take only first 2
                end

                % Show tuple naming dialog
                app.showTupleNamingDialog(tabIdx, subplotIdx, signalsToAdd{1}, signalsToAdd{2});
                return; % Exit here for tuple mode
            end
            % =============================================
            % END OF TUPLE MODE CHECK

            % KEEP ALL THE EXISTING CODE BELOW EXACTLY AS IT WAS:
            % SAVE EXPANDED STATE BEFORE ANY CHANGES
            app.saveTreeExpandedState();

            % Use PlotManager's safe method
            addedCount = app.PlotManager.addSignalsToSubplot(tabIdx, subplotIdx, signalsToAdd);

            % Apply linking for added signals
            if addedCount > 0 && isprop(app, 'LinkingManager') && ~isempty(app.LinkingManager)
                for i = 1:numel(signalsToAdd)
                    app.LinkingManager.applyLinking(signalsToAdd{i});
                end
            end

            % Instead of full rebuild, just update visual indicators
            if addedCount > 0
                % Get current assignments for visual update
                currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};

                % USE EXISTING PlotManager method - it already handles everything correctly
                app.PlotManager.updateSignalTreeVisualIndicators(currentAssignments);

                % Refresh plots
                app.PlotManager.refreshPlots(tabIdx);

                % Update properties table
                selectedNodes = app.SignalTree.SelectedNodes;
                selectedSignals = app.getSelectedSignalsFromNodes(selectedNodes);
                app.updateSignalPropsTable(selectedSignals);
            end

            % RESTORE EXPANDED STATE AFTER UPDATES
            app.restoreTreeExpandedState();

            % Update status
            if addedCount > 0
                app.StatusLabel.Text = sprintf('➕ Added %d signal(s) to subplot %d', addedCount, subplotIdx);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'All selected signals already assigned';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end

        function showTupleNamingDialog(app, tabIdx, subplotIdx, xSignalInfo, ySignalInfo)
            % Dialog to name the X-Y tuple with swap functionality
            d = dialog('Name', 'Configure X-Y Tuple', ...
                'Position', [400 400 350 220], 'Resize', 'off');

            % Store current signal info (will be swapped if needed)
            currentXSignal = xSignalInfo;
            currentYSignal = ySignalInfo;

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 310 25], ...
                'String', 'Configure X-Y Signal Pair', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % X Signal display
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 80 20], ...
                'String', 'X Signal:', 'FontWeight', 'bold');
            xSignalDisplay = uicontrol('Parent', d, 'Style', 'text', 'Position', [100 150 200 20], ...
                'String', currentXSignal.Signal, 'HorizontalAlignment', 'left', ...
                'BackgroundColor', [0.94 0.94 0.94]);

            % Y Signal display
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 125 80 20], ...
                'String', 'Y Signal:', 'FontWeight', 'bold');
            ySignalDisplay = uicontrol('Parent', d, 'Style', 'text', 'Position', [100 125 200 20], ...
                'String', currentYSignal.Signal, 'HorizontalAlignment', 'left', ...
                'BackgroundColor', [0.94 0.94 0.94]);

            % Swap button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', '⇅ Swap', ...
                'Position', [150 137 150 25], 'Callback', @swapSignals, ...
                'FontSize', 10, 'FontWeight', 'bold', 'ToolTipString', 'Swap X and Y signals');

            % Tuple name input
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 95 80 20], ...
                'String', 'Tuple Name:', 'FontWeight', 'bold');
            defaultLabel = sprintf('%s vs %s', currentYSignal.Signal, currentXSignal.Signal);
            labelField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [20 70 310 25], 'String', defaultLabel, ...
                'HorizontalAlignment', 'left', 'FontSize', 10);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Add Tuple', ...
                'Position', [180 25 80 30], 'Callback', @addTuple, ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [270 25 60 30], 'Callback', @(~,~) close(d));

            % Focus on label field
            uicontrol(labelField);

            function swapSignals(~, ~)
                % Swap the X and Y signals
                tempSignal = currentXSignal;
                currentXSignal = currentYSignal;
                currentYSignal = tempSignal;

                % Update the display
                xSignalDisplay.String = currentXSignal.Signal;
                ySignalDisplay.String = currentYSignal.Signal;

                % Update the default tuple name
                updateDefaultLabel();
            end

            function updateDefaultLabel()
                % Update the default tuple name when signals change
                newDefault = sprintf('%s vs %s', currentYSignal.Signal, currentXSignal.Signal);
                labelField.String = newDefault;
            end

            function addTuple(~, ~)
                tupleLabel = labelField.String;
                if isempty(tupleLabel)
                    tupleLabel = sprintf('%s vs %s', currentYSignal.Signal, currentXSignal.Signal);
                end

                % Add the tuple with current (possibly swapped) signals
                app.PlotManager.addTupleToSubplot(tabIdx, subplotIdx, currentXSignal, currentYSignal, tupleLabel);

                % Update status
                app.StatusLabel.Text = sprintf('➕ Added X-Y tuple: %s', tupleLabel);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
                close(d);
            end
        end

        function isTupleMode = isSubplotInTupleMode(app, tabIdx, subplotIdx)
            isTupleMode = false;
            if tabIdx <= numel(app.PlotManager.TupleMode) && ...
                    subplotIdx <= numel(app.PlotManager.TupleMode{tabIdx})
                isTupleMode = app.PlotManager.TupleMode{tabIdx}{subplotIdx};
            end
        end

        % ADD method to clear all tuples:
        function clearAllTuples(app, tabIdx, subplotIdx)
            if tabIdx <= numel(app.PlotManager.TupleSignals) && ...
                    subplotIdx <= numel(app.PlotManager.TupleSignals{tabIdx})

                % Clear tuples and disable tuple mode
                app.PlotManager.TupleSignals{tabIdx}{subplotIdx} = {};
                app.PlotManager.TupleMode{tabIdx}{subplotIdx} = false;

                % Refresh plots
                app.PlotManager.refreshPlots(tabIdx);

                app.StatusLabel.Text = sprintf('🗑️ Cleared all tuples from Plot %d (back to regular mode)', subplotIdx);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            end
        end



        function saveTreeExpandedState(app)
            % Save the current expanded state of all tree nodes
            if isempty(app.SignalTree) || isempty(app.SignalTree.Children)
                return;
            end

            % Clear previous state
            app.ExpandedTreeNodes = string.empty;

            % Save expanded state of all root nodes
            for i = 1:numel(app.SignalTree.Children)
                node = app.SignalTree.Children(i);
                try
                    % Check if node is expanded (different methods for different MATLAB versions)
                    isExpanded = false;
                    if isprop(node, 'Expanded')
                        isExpanded = node.Expanded;
                    elseif isprop(node, 'NodeExpanded')
                        isExpanded = node.NodeExpanded;
                    else
                        % For older versions, assume expanded if has visible children
                        isExpanded = ~isempty(node.Children);
                    end

                    if isExpanded
                        app.ExpandedTreeNodes(end+1) = string(node.Text);
                    end
                catch
                    % Ignore errors - just skip this node
                end
            end
        end


        function restoreTreeExpandedState(app)
            % Restore the previously saved expanded state
            if isempty(app.ExpandedTreeNodes) || isempty(app.SignalTree.Children)
                return;
            end

            % Small delay to ensure tree is fully built
            pause(0.01);

            % Restore expanded state
            for i = 1:numel(app.SignalTree.Children)
                node = app.SignalTree.Children(i);
                nodeText = string(node.Text);

                % Check if this node should be expanded
                if any(strcmp(nodeText, app.ExpandedTreeNodes))
                    try
                        % Try different methods to expand the node
                        if isprop(node, 'expand') && isa(node.expand, 'function_handle')
                            node.expand();
                        elseif isprop(node, 'Expanded')
                            node.Expanded = true;
                        elseif isprop(node, 'NodeExpanded')
                            node.NodeExpanded = true;
                        end
                    catch
                        % Ignore expansion errors
                    end
                end
            end

            % Force UI update
            drawnow;
        end

        function colors = assignCSVColors(~, n)
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

        function menuExportPPT(app)
            app.PlotManager.exportToPPT();
            figure(app.UIFigure);
        end


        function menuExportToPlotBrowser(app)
            app.PlotManager.exportTabsToPlotBrowser();
        end
        function menuStatistics(app)
            app.UIController.showStatsDialog();
            figure(app.UIFigure);
        end

        function populateMultiSelectionContextMenu(app, contextMenu, clickedSignalInfo)
            % Enhanced context menu with all operations and hide functionality

            % Clear existing menu items
            delete(contextMenu.Children);

            % Get currently selected signals
            selectedNodes = app.SignalTree.SelectedNodes;
            selectedSignals = app.getSelectedSignalsFromNodes(selectedNodes);

            % If no valid signals selected, use the clicked signal
            if isempty(selectedSignals)
                selectedSignals = {clickedSignalInfo};
            end

            % Get current assignments
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            currentAssignments = {};
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                currentAssignments = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Separate assigned and unassigned signals
            assignedSignals = {};
            unassignedSignals = {};

            for i = 1:numel(selectedSignals)
                isAssigned = false;
                signal = selectedSignals{i};

                for j = 1:numel(currentAssignments)
                    if isequal(currentAssignments{j}, signal)
                        isAssigned = true;
                        break;
                    end
                end

                if isAssigned
                    assignedSignals{end+1} = signal;
                else
                    unassignedSignals{end+1} = signal;
                end
            end

            % ============= ASSIGNMENT/REMOVAL OPERATIONS =============
            if ~isempty(unassignedSignals)
                if numel(unassignedSignals) == 1
                    uimenu(contextMenu, 'Text', '➕ Add to Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.addMultipleSignalsToCurrentSubplot(unassignedSignals));
                else
                    uimenu(contextMenu, 'Text', sprintf('➕ Add %d Signals to Subplot', numel(unassignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.addMultipleSignalsToCurrentSubplot(unassignedSignals));
                end
            end

            if ~isempty(assignedSignals)
                if numel(assignedSignals) == 1
                    uimenu(contextMenu, 'Text', '❌ Remove from Subplot', ...
                        'MenuSelectedFcn', @(src, event) app.removeMultipleSignalsFromCurrentSubplot(assignedSignals));
                else
                    uimenu(contextMenu, 'Text', sprintf('❌ Remove %d Signals from Subplot', numel(assignedSignals)), ...
                        'MenuSelectedFcn', @(src, event) app.removeMultipleSignalsFromCurrentSubplot(assignedSignals));
                end
            end

            % ============= SINGLE SIGNAL OPERATIONS =============
            if numel(selectedSignals) == 1
                signal = selectedSignals{1};

                % Preview and basic options
                uimenu(contextMenu, 'Text', '📊 Quick Preview', ...
                    'MenuSelectedFcn', @(src, event) app.showSignalPreview(signal), 'Separator', 'on');
                uimenu(contextMenu, 'Text', '📈 Set as X-Axis', ...
                    'MenuSelectedFcn', @(src, event) app.setSignalAsXAxis(signal));

                % === SINGLE SIGNAL OPERATIONS SUBMENU ===
                singleOpsMenu = uimenu(contextMenu, 'Text', '🔢 Single Signal Operations', 'Separator', 'on');

                % Convert signal to proper format for operations
                signalNameForOps = app.getSignalNameForOperations(signal);

                % In the single signal operations section, replace:
                uimenu(singleOpsMenu, 'Text', '∂ Derivative', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showSimplifiedSingleSignalDialog('derivative', signalNameForOps));
                uimenu(singleOpsMenu, 'Text', '∫ Integral', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showSimplifiedSingleSignalDialog('integral', signalNameForOps));
                % Quick single operations - pass the signal directly for immediate execution
                quickSingleMenu = uimenu(singleOpsMenu, 'Text', '⚡ Quick Operations', 'Separator', 'on');
                uimenu(quickSingleMenu, 'Text', '🌊 Moving Average', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickMovingAverageWithPreselection(signalNameForOps));
                uimenu(quickSingleMenu, 'Text', '📊 FFT Analysis', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickFFTWithPreselection(signalNameForOps));
                uimenu(quickSingleMenu, 'Text', '📏 RMS Calculation', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickRMSWithPreselection(signalNameForOps));

                % Hide/Show option for single signal
                if app.isSignalHidden(signal)
                    uimenu(contextMenu, 'Text', '👁️ Show Signal in Tree', ...
                        'MenuSelectedFcn', @(src, event) app.showSignalInTree(signal), 'Separator', 'on');
                else
                    uimenu(contextMenu, 'Text', '🙈 Hide Signal from Tree', ...
                        'MenuSelectedFcn', @(src, event) app.hideSignalFromTree(signal), 'Separator', 'on');
                end

                % Signal-specific options
                if signal.CSVIdx == -1  % Derived signal
                    uimenu(contextMenu, 'Text', '📋 Show Operation Details', ...
                        'MenuSelectedFcn', @(src, event) app.showDerivedSignalDetails(signal.Signal), 'Separator', 'on');
                    uimenu(contextMenu, 'Text', '💾 Export Derived Signal', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.exportDerivedSignal(signal.Signal));
                    uimenu(contextMenu, 'Text', '🗑️ Delete Derived Signal', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.confirmDeleteDerivedSignal(signal.Signal));
                else
                    uimenu(contextMenu, 'Text', '💾 Export Signal to CSV', ...
                        'MenuSelectedFcn', @(src, event) app.exportSingleSignalToCSV(signal), 'Separator', 'on');
                end

                uimenu(contextMenu, 'Text', '🗑️ Clear from All Subplots', ...
                    'MenuSelectedFcn', @(src, event) app.clearSpecificSignalFromAllSubplots(signal));

            elseif numel(selectedSignals) >= 2
                % ============= MULTI-SIGNAL OPERATIONS =============

                % Preview for multiple signals
                uimenu(contextMenu, 'Text', sprintf('📊 Preview %d Signals', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.previewSelectedSignals(selectedSignals), 'Separator', 'on');

                % === DUAL SIGNAL OPERATIONS (exactly 2 signals) ===
                if numel(selectedSignals) == 2
                    dualOpsMenu = uimenu(contextMenu, 'Text', '📈 Dual Signal Operations', 'Separator', 'on');

                    % Convert signals to proper format for operations
                    signal1Name = app.getSignalNameForOperations(selectedSignals{1});
                    signal2Name = app.getSignalNameForOperations(selectedSignals{2});

                    uimenu(dualOpsMenu, 'Text', '➕ Add (A + B)', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialogWithPreselection('add', signal1Name, signal2Name));
                    uimenu(dualOpsMenu, 'Text', '➖ Subtract (A - B)', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialogWithPreselection('subtract', signal1Name, signal2Name));
                    uimenu(dualOpsMenu, 'Text', '✖️ Multiply (A × B)', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialogWithPreselection('multiply', signal1Name, signal2Name));
                    uimenu(dualOpsMenu, 'Text', '➗ Divide (A ÷ B)', ...
                        'MenuSelectedFcn', @(src, event) app.SignalOperations.showDualSignalDialogWithPreselection('divide', signal1Name, signal2Name));
                end

                % === MULTI-SIGNAL OPERATIONS (2+ signals) ===
                multiOpsMenu = uimenu(contextMenu, 'Text', '⚡ Multi-Signal Operations', 'Separator', 'on');

                % Convert all selected signals to proper format
                selectedSignalNames = cell(length(selectedSignals), 1);
                for i = 1:length(selectedSignals)
                    selectedSignalNames{i} = app.getSignalNameForOperations(selectedSignals{i});
                end

                uimenu(multiOpsMenu, 'Text', '📊 Vector Magnitude', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickVectorMagnitudeWithPreselection(selectedSignalNames));
                uimenu(multiOpsMenu, 'Text', '📈 Signal Average', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showQuickAverageWithPreselection(selectedSignalNames));
                uimenu(multiOpsMenu, 'Text', '‖‖ Norm of Signals', ...
                    'MenuSelectedFcn', @(src, event) app.SignalOperations.showNormDialogWithPreselection(selectedSignalNames));

                % Hide/Show options for multiple signals
                hideShowMenu = uimenu(contextMenu, 'Text', '👁️ Hide/Show Options', 'Separator', 'on');
                uimenu(hideShowMenu, 'Text', sprintf('🙈 Hide %d Signals from Tree', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.hideMultipleSignalsFromTree(selectedSignals));
                uimenu(hideShowMenu, 'Text', '👁️ Show All Hidden Signals', ...
                    'MenuSelectedFcn', @(src, event) app.showAllHiddenSignals());

                % Export and clear options
                uimenu(contextMenu, 'Text', sprintf('💾 Export %d Signals to CSV', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.exportMultipleSignalsToCSV(selectedSignals), 'Separator', 'on');
                uimenu(contextMenu, 'Text', sprintf('🗑️ Clear %d Signals from All Subplots', numel(selectedSignals)), ...
                    'MenuSelectedFcn', @(src, event) app.clearMultipleSignalsFromAllSubplots(selectedSignals));
            end

            % === OPERATION HISTORY AND MANAGEMENT ===
            managementMenu = uimenu(contextMenu, 'Text', '⚙️ Management', 'Separator', 'on');
            uimenu(managementMenu, 'Text', '📋 Operation History', ...
                'MenuSelectedFcn', @(src, event) app.SignalOperations.showOperationHistory());
            uimenu(managementMenu, 'Text', '🗑️ Clear All Derived Signals', ...
                'MenuSelectedFcn', @(src, event) app.confirmAndClearDerivedSignals());

            % Selection info
            if numel(selectedSignals) > 1
                uimenu(contextMenu, 'Text', sprintf('📋 %d signals selected', numel(selectedSignals)), ...
                    'Enable', 'off', 'Separator', 'on');
            elseif numel(selectedSignals) == 1
                signal = selectedSignals{1};
                if signal.CSVIdx == -1
                    signalType = 'derived signal';
                else
                    signalType = sprintf('CSV %d signal', signal.CSVIdx);
                end
                uimenu(contextMenu, 'Text', sprintf('📋 %s: %s', signalType, signal.Signal), ...
                    'Enable', 'off', 'Separator', 'on');
            end
        end

        % Add these methods to SignalViewerApp.m

        function initializeHiddenSignalsMap(app)
            % Initialize the hidden signals map if it doesn't exist
            if ~isprop(app, 'HiddenSignals') || isempty(app.HiddenSignals)
                app.HiddenSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
            end
        end

        function signalKey = getSignalKey(app, signalInfo)
            % Create a unique key for a signal
            if signalInfo.CSVIdx == -1
                % Derived signal
                signalKey = sprintf('DERIVED_%s', signalInfo.Signal);
            else
                % Regular signal
                signalKey = sprintf('CSV%d_%s', signalInfo.CSVIdx, signalInfo.Signal);
            end
        end

        function tf = isSignalHidden(app, signalInfo)
            % Check if a signal is hidden
            app.initializeHiddenSignalsMap();
            signalKey = app.getSignalKey(signalInfo);
            tf = app.HiddenSignals.isKey(signalKey) && app.HiddenSignals(signalKey);
        end

        function hideSignalFromTree(app, signalInfo)
            % Hide a signal from the tree view
            app.initializeHiddenSignalsMap();
            signalKey = app.getSignalKey(signalInfo);
            app.HiddenSignals(signalKey) = true;

            % Rebuild tree to apply hiding
            app.buildSignalTree();

            % Update status
            app.StatusLabel.Text = sprintf('🙈 Hidden signal: %s', signalInfo.Signal);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function showSignalInTree(app, signalInfo)
            % Show a previously hidden signal in the tree view
            app.initializeHiddenSignalsMap();
            signalKey = app.getSignalKey(signalInfo);

            if app.HiddenSignals.isKey(signalKey)
                app.HiddenSignals(signalKey) = false;
            end

            % Rebuild tree to apply changes
            app.buildSignalTree();

            % Update status
            app.StatusLabel.Text = sprintf('👁️ Showing signal: %s', signalInfo.Signal);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function hideMultipleSignalsFromTree(app, selectedSignals)
            % Hide multiple signals from the tree view
            app.initializeHiddenSignalsMap();

            hiddenCount = 0;
            for i = 1:numel(selectedSignals)
                signalKey = app.getSignalKey(selectedSignals{i});
                if ~app.HiddenSignals.isKey(signalKey) || ~app.HiddenSignals(signalKey)
                    app.HiddenSignals(signalKey) = true;
                    hiddenCount = hiddenCount + 1;
                end
            end

            % Rebuild tree to apply hiding
            app.buildSignalTree();

            % Update status
            app.StatusLabel.Text = sprintf('🙈 Hidden %d signals from tree', hiddenCount);
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function showAllHiddenSignals(app)
            % Show all previously hidden signals
            app.initializeHiddenSignalsMap();

            % Count currently hidden signals
            hiddenKeys = keys(app.HiddenSignals);
            hiddenCount = 0;

            for i = 1:length(hiddenKeys)
                if app.HiddenSignals(hiddenKeys{i})
                    hiddenCount = hiddenCount + 1;
                    app.HiddenSignals(hiddenKeys{i}) = false;
                end
            end

            % Rebuild tree to show all signals
            app.buildSignalTree();

            % Update status
            if hiddenCount > 0
                app.StatusLabel.Text = sprintf('👁️ Showing %d previously hidden signals', hiddenCount);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = 'ℹ️ No hidden signals found';
                app.StatusLabel.FontColor = [0.5 0.5 0.5];
            end
        end

        function showHiddenSignalsManager(app)
            % Show dialog to manage hidden signals
            app.initializeHiddenSignalsMap();

            % Get all hidden signals
            hiddenKeys = keys(app.HiddenSignals);
            hiddenSignalNames = {};
            hiddenSignalInfos = {};

            for i = 1:length(hiddenKeys)
                if app.HiddenSignals(hiddenKeys{i})
                    key = hiddenKeys{i};
                    % Parse the key to get signal info
                    if startsWith(key, 'DERIVED_')
                        signalName = strrep(key, 'DERIVED_', '');
                        hiddenSignalNames{end+1} = sprintf('🔄 %s (Derived)', signalName);
                        hiddenSignalInfos{end+1} = struct('CSVIdx', -1, 'Signal', signalName);
                    elseif startsWith(key, 'CSV')
                        parts = split(key, '_');
                        csvIdxStr = strrep(parts{1}, 'CSV', '');
                        csvIdx = str2double(csvIdxStr);
                        signalName = strjoin(parts(2:end), '_');
                        hiddenSignalNames{end+1} = sprintf('📊 %s (CSV %d)', signalName, csvIdx);
                        hiddenSignalInfos{end+1} = struct('CSVIdx', csvIdx, 'Signal', signalName);
                    end
                end
            end

            if isempty(hiddenSignalNames)
                uialert(app.UIFigure, 'No hidden signals found.', 'No Hidden Signals');
                return;
            end

            % Create management dialog
            d = dialog('Name', 'Hidden Signals Manager', 'Position', [300 300 500 400], 'Resize', 'on');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 360 460 25], ...
                'String', sprintf('Manage Hidden Signals (%d hidden)', length(hiddenSignalNames)), ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % List of hidden signals
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 330 200 20], ...
                'String', 'Hidden Signals:', 'FontWeight', 'bold');

            hiddenListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 180 460 145], 'String', hiddenSignalNames, 'Max', length(hiddenSignalNames));

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Show Selected', ...
                'Position', [20 140 120 30], 'Callback', @(~,~) showSelected(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Show All', ...
                'Position', [150 140 120 30], 'Callback', @(~,~) showAll());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Delete Selected from System', ...
                'Position', [280 140 200 30], 'Callback', @(~,~) deleteSelected(), ...
                'BackgroundColor', [0.9 0.3 0.3], 'ForegroundColor', 'white');

            % Statistics
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 460 30], ...
                'String', sprintf('Total signals hidden: %d\nHidden signals remain in memory but are not visible in the tree.', ...
                length(hiddenSignalNames)), ...
                'FontSize', 9, 'HorizontalAlignment', 'left');

            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [400 20 80 30], 'Callback', @(~,~) close(d));

            function showSelected()
                selectedIndices = hiddenListbox.Value;
                if isempty(selectedIndices)
                    return;
                end

                for i = selectedIndices
                    app.showSignalInTree(hiddenSignalInfos{i});
                end

                close(d);
            end

            function showAll()
                app.showAllHiddenSignals();
                close(d);
            end

            function deleteSelected()
                selectedIndices = hiddenListbox.Value;
                if isempty(selectedIndices)
                    return;
                end

                selectedNames = hiddenSignalNames(selectedIndices);
                answer = uiconfirm(d, ...
                    sprintf('Permanently delete %d selected signals from the system?\n\nSignals: %s\n\nThis cannot be undone!', ...
                    length(selectedNames), strjoin(selectedNames, ', ')), ...
                    'Confirm Permanent Delete', ...
                    'Options', {'Delete Permanently', 'Cancel'}, ...
                    'DefaultOption', 'Cancel', 'Icon', 'warning');

                if strcmp(answer, 'Delete Permanently')
                    for i = selectedIndices
                        signalInfo = hiddenSignalInfos{i};
                        if signalInfo.CSVIdx == -1
                            % Delete derived signal
                            app.SignalOperations.deleteDerivedSignal(signalInfo.Signal);
                        else
                            % For CSV signals, we can only remove from assignments and hide
                            app.clearSpecificSignalFromAllSubplots(signalInfo);
                        end
                    end
                    close(d);
                    app.StatusLabel.Text = sprintf('🗑️ Permanently deleted %d signals', length(selectedIndices));
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                end
            end
        end

        function updateTuplePropsTable(app, tabIdx, subplotIdx)
            % Show tuple information in properties table
            if tabIdx <= numel(app.PlotManager.TupleSignals) && ...
                    subplotIdx <= numel(app.PlotManager.TupleSignals{tabIdx}) && ...
                    ~isempty(app.PlotManager.TupleSignals{tabIdx}{subplotIdx})

                tuples = app.PlotManager.TupleSignals{tabIdx}{subplotIdx};
                n = numel(tuples);

                % Modify table headers for tuple mode
                app.SignalPropsTable.ColumnName = {'☐', 'Tuple Name', 'X Signal', 'Y Signal', 'Color', 'Remove'};
                app.SignalPropsTable.ColumnWidth = {25, 120, 80, 80, 45, 60};
                app.SignalPropsTable.ColumnEditable = [true false false false false true];

                data = cell(n, 6);
                for i = 1:n
                    tuple = tuples{i};
                    data{i,1} = false;  % Checkbox
                    data{i,2} = tuple.Label;  % Tuple name
                    data{i,3} = tuple.XSignal.Signal;  % X signal
                    data{i,4} = tuple.YSignal.Signal;  % Y signal
                    data{i,5} = mat2str(tuple.Color);  % Color
                    data{i,6} = 'Delete';  % Remove button placeholder
                end

                app.SignalPropsTable.Data = data;
                app.RemoveSelectedSignalsButton.Text = '🗑️ Remove Selected Tuples';
                app.RemoveSelectedSignalsButton.Enable = 'off';

            else
                % No tuples - show instruction
                app.SignalPropsTable.ColumnName = {'Info'};
                app.SignalPropsTable.ColumnWidth = {280};
                app.SignalPropsTable.ColumnEditable = false;
                app.SignalPropsTable.Data = {'X-Y Mode: Select 2 signals from tree and add to create tuple'};
                app.RemoveSelectedSignalsButton.Enable = 'off';
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
        function cleanupTimers(app)
            % Clean up all timer objects to prevent memory leaks

            % Clean up DataManager timers
            if isprop(app, 'DataManager') && ~isempty(app.DataManager)
                if isprop(app.DataManager, 'StreamingTimers') && ~isempty(app.DataManager.StreamingTimers)
                    for i = 1:length(app.DataManager.StreamingTimers)
                        timer_obj = app.DataManager.StreamingTimers{i};
                        if isa(timer_obj, 'timer') && isvalid(timer_obj)
                            try
                                stop(timer_obj);
                                delete(timer_obj);
                            catch
                                % Ignore cleanup errors
                            end
                        end
                    end
                    app.DataManager.StreamingTimers = {};
                end
            end

            % Clean up any other timer references
            % Add any other timer cleanup here as needed
        end
        function onAxesDrop(app, tabIdx, subplotIdx, event)
            % Handle drop event: assign the dragged signal to the target subplot
            if isempty(event.Data)
                return;
            end
            node = event.Data;
            if isfield(node.NodeData, 'CSVIdx')
                sigInfo = node.NodeData;
                % Add (nots replace) the signal to the subplot assignment
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
