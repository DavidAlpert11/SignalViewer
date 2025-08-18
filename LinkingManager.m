classdef LinkingManager < handle
    properties
        App
        LinkedGroups        % cell array of linked node/signal groups
        LinkColors          % color scheme for visual indicators
        AutoLinkEnabled     % boolean
        LinkingMode         % 'nodes', 'signals', 'patterns'
    end

    methods
        function obj = LinkingManager(app)
            obj.App = app;
            obj.LinkedGroups = {};
            obj.LinkColors = [
                0.9 0.2 0.2;    % Red group
                0.2 0.9 0.2;    % Green group
                0.2 0.2 0.9;    % Blue group
                0.9 0.9 0.2;    % Yellow group
                0.9 0.2 0.9;    % Magenta group
                0.2 0.9 0.9;    % Cyan group
                ];
            obj.AutoLinkEnabled = false;
            obj.LinkingMode = 'nodes';
        end

        function showLinkingDialog(obj)
            % Main linking configuration dialog
            d = dialog('Name', 'Signal Linking System', 'Position', [200 200 600 400], 'Resize', 'on');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 360 560 25], ...
                'String', 'Signal Linking System', ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Current implementation - simple node linking
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 320 560 30], ...
                'String', 'Link CSV nodes: when you assign a signal from one CSV, the same signal from linked CSVs is automatically assigned.', ...
                'FontSize', 11, 'HorizontalAlignment', 'left');

            % Available nodes
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 280 150 20], ...
                'String', 'Available CSV Nodes:', 'FontWeight', 'bold');

            availableNodes = obj.getAvailableNodes();
            availableListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 180 200 90], 'String', availableNodes, 'Max', length(availableNodes));

            % Create link group
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Create Link Group', ...
                'Position', [240 220 120 30], 'Callback', @(~,~) obj.createLinkGroup(availableListbox, d));

            % Current groups
            uicontrol('Parent', d, 'Style', 'text', 'Position', [380 280 180 20], ...
                'String', 'Current Link Groups:', 'FontWeight', 'bold');

            groupsText = uicontrol('Parent', d, 'Style', 'edit', 'Position', [380 180 180 90], ...
                'String', obj.getLinkGroupsText(), 'Max', 10, 'Enable', 'off');

            % Auto-link checkbox
            uicontrol('Parent', d, 'Style', 'checkbox', 'Position', [20 140 300 20], ...
                'String', 'Enable automatic linking when assigning signals', 'Value', obj.AutoLinkEnabled, ...
                'Callback', @(src, ~) obj.setAutoLinkEnabled(src.Value));

            % Clear all links
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Clear All Links', ...
                'Position', [180 100 120 30], 'Callback', @(~,~) obj.clearAllLinks());

            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [500 20 80 30], 'Callback', @(~,~) close(d));
        end

        function delete(obj)
            % Enhanced cleanup to prevent memory leaks
            try
                % Clear all link groups
                obj.LinkedGroups = {};

                % Clear color array
                obj.LinkColors = [];

                % Reset flags
                obj.AutoLinkEnabled = false;
                obj.LinkingMode = '';

                % Break circular reference to App (CRITICAL)
                obj.App = [];

            catch ME
                fprintf('Warning during LinkingManager cleanup: %s\n', ME.message);
            end
        end

        function showComparisonDialog(obj)
            % Comparison tools dialog
            d = dialog('Name', 'Comparison Analysis', 'Position', [250 250 500 350]); % Made taller

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 310 460 25], ...
                'String', 'Comparison Analysis Tools', ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 280 460 20], ...
                'String', 'Generate comparison plots and analysis for linked signals.', ...
                'FontSize', 11);

            % Select linked group for comparison
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 240 120 20], ...
                'String', 'Select Link Group:', 'FontWeight', 'bold');

            groupNames = obj.getLinkGroupNames();
            groupDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 240 200 25], 'String', groupNames);

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 200 120 20], ...
                'String', 'Select Signal:', 'FontWeight', 'bold');

            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 200 200 25], ...
                'String', {'<All Shared Signals>'}, 'Enable', 'off');

            % Analysis type
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 160 120 20], ...
                'String', 'Analysis Type:', 'FontWeight', 'bold');

            analysisDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 160 200 25], ...
                'String', {'Overlay Plot', 'Difference Plot', 'Statistical Summary'});

            % Update signals when group changes
            groupDropdown.Callback = @(~,~) updateSignalDropdown();

            % Initialize signal dropdown
            updateSignalDropdown();

            % Generate button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Generate Analysis', ...
                'Position', [200 100 100 30], 'FontWeight', 'bold', ...
                'Callback', @(~,~) obj.generateComparison(groupDropdown, analysisDropdown, signalDropdown, d));

            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [400 20 80 30], 'Callback', @(~,~) close(d));

            function updateSignalDropdown()
                try
                    if isempty(obj.LinkedGroups)
                        signalDropdown.String = {'<No link groups>'};
                        signalDropdown.Enable = 'off';
                        return;
                    end

                    selectedGroupIdx = groupDropdown.Value;
                    if selectedGroupIdx < 1 || selectedGroupIdx > length(obj.LinkedGroups)
                        signalDropdown.String = {'<Invalid group>'};
                        signalDropdown.Enable = 'off';
                        return;
                    end

                    group = obj.LinkedGroups{selectedGroupIdx};
                    allSignals = [];

                    for i = 1:numel(group.CSVIndices)
                        idx = group.CSVIndices(i);
                        if idx > 0 && idx <= numel(obj.App.DataManager.DataTables)
                            T = obj.App.DataManager.DataTables{idx};
                            if ~isempty(T)
                                sigs = setdiff(T.Properties.VariableNames, {'Time'});
                                if isempty(allSignals)
                                    allSignals = sigs;
                                else
                                    allSignals = intersect(allSignals, sigs);
                                end
                            end
                        end
                    end

                    if isempty(allSignals)
                        signalDropdown.String = {'<No shared signals>'};
                        signalDropdown.Enable = 'off';
                    else
                        signalDropdown.String = [{'<All Shared Signals>'}, sort(allSignals)];
                        signalDropdown.Enable = 'on';
                    end

                catch ME
                    fprintf('Error updating signal dropdown: %s\n', ME.message);
                    signalDropdown.String = {'<Error>'};
                    signalDropdown.Enable = 'off';
                end
            end
        end
        function quickLinkSelected(obj)
            % Quick link currently selected nodes in tree
            selectedNodes = obj.App.SignalTree.SelectedNodes;

            if length(selectedNodes) < 2
                msgbox('Please select at least 2 CSV nodes to link.', 'Selection Required', 'warn');
                return;
            end

            % Extract CSV indices from selected nodes
            csvIndices = [];
            for i = 1:length(selectedNodes)
                node = selectedNodes(i);
                if isfield(node.NodeData, 'CSVIdx') && node.NodeData.CSVIdx > 0
                    csvIndices(end+1) = node.NodeData.CSVIdx;
                elseif contains(node.Text, '.csv')
                    % This is a CSV folder node, extract index
                    csvIdx = obj.getCSVIndexFromNodeText(node.Text);
                    if csvIdx > 0
                        csvIndices(end+1) = csvIdx;
                    end
                end
            end

            csvIndices = unique(csvIndices);

            if length(csvIndices) < 2
                msgbox('Please select CSV folder nodes, not individual signals.', 'Invalid Selection', 'warn');
                return;
            end

            % Create link group from selected CSVs
            newGroup = struct();
            newGroup.Type = 'nodes';
            newGroup.CSVIndices = csvIndices;
            % newGroup.Name = sprintf('Quick Link Group %d', length(obj.LinkedGroups) + 1);
            linkedNames = {};
            for i = 1:numel(csvIndices)
                [~, name, ~] = fileparts(obj.App.DataManager.CSVFilePaths{csvIndices(i)});
                linkedNames{end+1} = name;
            end
            newGroup.Name = ['Linked: ' strjoin(linkedNames, ', ')];
            newGroup.Color = obj.LinkColors(mod(length(obj.LinkedGroups), size(obj.LinkColors, 1)) + 1, :);

            obj.LinkedGroups{end+1} = newGroup;
            obj.App.StatusLabel.Text = sprintf('Created link group with %d CSVs', length(csvIndices));
            obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
            obj.AutoLinkEnabled = true;
        end

        function clearAllLinks(obj)
            % Enhanced clear with proper validation and modern UI
            try
                if isempty(obj.LinkedGroups)
                    uialert(obj.App.UIFigure, 'No link groups to clear.', 'No Links');
                    return;
                end

                % Use uiconfirm instead of questdlg for better App Designer compatibility
                answer = uiconfirm(obj.App.UIFigure, ...
                    sprintf('Clear all %d link groups?', length(obj.LinkedGroups)), ...
                    'Confirm Clear', ...
                    'Options', {'Clear All', 'Cancel'}, ...
                    'DefaultOption', 'Cancel', ...
                    'Icon', 'warning');

                if strcmp(answer, 'Clear All')
                    % Clear with proper memory management
                    obj.LinkedGroups = {};

                    % Reset auto-link if no groups remain
                    obj.AutoLinkEnabled = false;

                    obj.App.StatusLabel.Text = 'Cleared all link groups';
                    obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
                end

            catch ME
                % Fallback to simple clear if uiconfirm fails
                fprintf('Warning: UI dialog failed, clearing links anyway: %s\n', ME.message);
                obj.LinkedGroups = {};
                obj.AutoLinkEnabled = false;
                obj.App.StatusLabel.Text = 'Cleared all link groups (fallback)';
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
            end
        end
        function applyLinking(obj, signalInfo)
            % Apply linking when a signal is assigned
            if ~obj.AutoLinkEnabled || isempty(obj.LinkedGroups)
                return;
            end

            % Find which link group this signal belongs to
            signalCSVIdx = signalInfo.CSVIdx;
            if signalCSVIdx <= 0  % Skip derived signals for now
                return;
            end

            for i = 1:length(obj.LinkedGroups)
                group = obj.LinkedGroups{i};
                if strcmp(group.Type, 'nodes') && ismember(signalCSVIdx, group.CSVIndices)
                    % Found the group - now find matching signals in other CSVs
                    linkedSignals = obj.findMatchingSignalsInGroup(signalInfo, group);

                    if ~isempty(linkedSignals)
                        obj.addLinkedSignalsToCurrentSubplot(linkedSignals);
                        obj.App.StatusLabel.Text = sprintf('Auto-linked %d related signals', length(linkedSignals));
                        obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
                    end
                    break;
                end
            end
        end

        function availableNodes = getAvailableNodes(obj)
            availableNodes = {};

            % Validate DataManager and CSVFilePaths exist
            if ~isprop(obj.App, 'DataManager') || ...
                    isempty(obj.App.DataManager) || ...
                    ~isprop(obj.App.DataManager, 'CSVFilePaths')
                availableNodes = {'No CSV files loaded'};
                return;
            end

            csvPaths = obj.App.DataManager.CSVFilePaths;
            if isempty(csvPaths)
                availableNodes = {'No CSV files loaded'};
                return;
            end

            % BOUNDS CHECK: Validate each file path
            for i = 1:numel(csvPaths)
                if i <= length(csvPaths) && ~isempty(csvPaths{i})
                    try
                        [~, csvName, ext] = fileparts(csvPaths{i});
                        if ~isempty(csvName)
                            availableNodes{end+1} = sprintf('CSV %d: %s%s', i, csvName, ext);
                        end
                    catch ME
                        fprintf('Warning: Invalid file path at index %d: %s\n', i, ME.message);
                        availableNodes{end+1} = sprintf('CSV %d: <Invalid Path>', i);
                    end
                end
            end

            if isempty(availableNodes)
                availableNodes = {'No valid CSV files found'};
            end
        end

        function createLinkGroup(obj, listbox, dialog)
            try
                selectedIndices = listbox.Value;
                if length(selectedIndices) < 2
                    uialert(obj.App.UIFigure, 'Please select at least 2 CSV files to link.', 'Selection Required');
                    return;
                end

                % BOUNDS CHECK: Validate selected indices
                maxValidIndex = length(obj.getAvailableNodes());
                validIndices = selectedIndices(selectedIndices > 0 & selectedIndices <= maxValidIndex);

                if length(validIndices) < 2
                    uialert(obj.App.UIFigure, 'Selected indices are invalid.', 'Invalid Selection');
                    return;
                end

                csvIndices = validIndices;

                % Create new link group
                newGroup = struct();
                newGroup.Type = 'nodes';
                newGroup.CSVIndices = csvIndices;

                % SAFE COLOR ACCESS: Handle empty color array
                if isempty(obj.LinkColors)
                    % Fallback colors if LinkColors is empty
                    obj.LinkColors = [
                        0.9 0.2 0.2;    % Red
                        0.2 0.9 0.2;    % Green
                        0.2 0.2 0.9;    % Blue
                        0.9 0.9 0.2;    % Yellow
                        0.9 0.2 0.9;    % Magenta
                        0.2 0.9 0.9;    % Cyan
                        ];
                end

                colorIdx = mod(length(obj.LinkedGroups), size(obj.LinkColors, 1)) + 1;
                newGroup.Color = obj.LinkColors(colorIdx, :);

                % Safe filename construction
                linkedNames = {};
                for i = 1:numel(csvIndices)
                    if csvIndices(i) <= length(obj.App.DataManager.CSVFilePaths)
                        filePath = obj.App.DataManager.CSVFilePaths{csvIndices(i)};
                        if ~isempty(filePath)
                            [~, name, ~] = fileparts(filePath);
                            if ~isempty(name)
                                linkedNames{end+1} = name;
                            else
                                linkedNames{end+1} = sprintf('CSV_%d', csvIndices(i));
                            end
                        end
                    end
                end

                if isempty(linkedNames)
                    newGroup.Name = sprintf('Link Group %d', length(obj.LinkedGroups) + 1);
                else
                    newGroup.Name = ['Linked CSVs: ' strjoin(linkedNames, ', ')];
                end

                % Add to link groups
                obj.LinkedGroups{end+1} = newGroup;

                % Safe UI update
                obj.updateDialogGroupsText(dialog);

                obj.App.StatusLabel.Text = sprintf('Created link group with %d CSV files', length(csvIndices));
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                uialert(obj.App.UIFigure, sprintf('Failed to create link group: %s', ME.message), 'Error');
                fprintf('Error in createLinkGroup: %s\n', ME.message);
            end
        end

        function updateDialogGroupsText(obj, dialog)
            % Safe UI update helper
            try
                groupsText = findobj(dialog, 'Style', 'edit', 'Enable', 'off');
                if ~isempty(groupsText) && isvalid(groupsText(1))
                    groupsText(1).String = obj.getLinkGroupsText();
                end
            catch ME
                fprintf('Warning: Could not update dialog groups text: %s\n', ME.message);
            end
        end

        function groupsText = getLinkGroupsText(obj)
            if isempty(obj.LinkedGroups)
                groupsText = {'No link groups created'};
                return;
            end

            groupsText = {};
            for i = 1:length(obj.LinkedGroups)
                group = obj.LinkedGroups{i};
                if strcmp(group.Type, 'nodes')
                    csvNames = {};
                    for j = 1:length(group.CSVIndices)
                        csvIdx = group.CSVIndices(j);
                        if csvIdx <= length(obj.App.DataManager.CSVFilePaths)
                            [~, name, ext] = fileparts(obj.App.DataManager.CSVFilePaths{csvIdx});
                            csvNames{end+1} = [name ext];
                        end
                    end
                    groupsText{end+1} = sprintf('%s: %s', group.Name, strjoin(csvNames, ', '));
                end
            end
        end

        function groupNames = getLinkGroupNames(obj)
            if isempty(obj.LinkedGroups)
                groupNames = {'No link groups'};
                return;
            end

            groupNames = {};
            for i = 1:length(obj.LinkedGroups)
                groupNames{end+1} = obj.LinkedGroups{i}.Name;
            end
        end

        function linkedSignals = findMatchingSignalsInGroup(obj, signalInfo, group)
            linkedSignals = {};

            % Input validation
            if ~isstruct(signalInfo) || ~isfield(signalInfo, 'Signal') || ~isfield(signalInfo, 'CSVIdx')
                return;
            end

            signalName = signalInfo.Signal;

            % Validate group structure
            if ~isstruct(group) || ~isfield(group, 'CSVIndices')
                return;
            end

            % Look for the same signal name in other CSVs in the group
            for i = 1:length(group.CSVIndices)
                csvIdx = group.CSVIndices(i);

                % BOUNDS CHECK: Validate CSV index
                if csvIdx ~= signalInfo.CSVIdx && ...
                        csvIdx > 0 && ...
                        csvIdx <= length(obj.App.DataManager.DataTables)

                    T = obj.App.DataManager.DataTables{csvIdx};
                    if ~isempty(T) && istable(T) && ismember(signalName, T.Properties.VariableNames)
                        linkedSignals{end+1} = struct('CSVIdx', csvIdx, 'Signal', signalName);
                    end
                end
            end
        end


        function addLinkedSignalsToCurrentSubplot(obj, linkedSignals)
            currentTab = obj.App.PlotManager.CurrentTabIdx;
            currentSubplot = obj.App.PlotManager.SelectedSubplotIdx;

            % Get current assignments
            currentAssignments = obj.App.PlotManager.AssignedSignals{currentTab}{currentSubplot};

            % Add linked signals that aren't already assigned
            for i = 1:length(linkedSignals)
                alreadyAssigned = false;
                for j = 1:length(currentAssignments)
                    if isequal(currentAssignments{j}, linkedSignals{i})
                        alreadyAssigned = true;
                        break;
                    end
                end

                if ~alreadyAssigned
                    currentAssignments{end+1} = linkedSignals{i};
                end
            end

            % Update assignments and refresh
            obj.App.PlotManager.AssignedSignals{currentTab}{currentSubplot} = currentAssignments;
            obj.App.PlotManager.refreshPlots(currentTab);
            obj.App.buildSignalTree();
        end


        function linkedSignals = getLinkedSignals(obj, signalStruct)
            linkedSignals = {};
            signalName = signalStruct.Signal;
            csvIdx = signalStruct.CSVIdx;

            for i = 1:numel(obj.LinkedGroups)
                group = obj.LinkedGroups{i};
                if strcmp(group.Type, 'nodes') && ismember(csvIdx, group.CSVIndices)
                    for j = 1:numel(group.CSVIndices)
                        otherIdx = group.CSVIndices(j);
                        if otherIdx == csvIdx
                            continue;  % Skip self
                        end
                        T = obj.App.DataManager.DataTables{otherIdx};
                        if isempty(T), continue; end
                        if ismember(signalName, T.Properties.VariableNames)
                            linkedSignals{end+1} = struct('CSVIdx', otherIdx, 'Signal', signalName);
                        end
                    end
                    return;  % Found the group, no need to check further
                end
            end
        end

        function setAutoLinkEnabled(obj, enabled)
            obj.AutoLinkEnabled = enabled;
        end

        function generateComparison(obj, groupDropdown, analysisDropdown, signalDropdown, ~)
            % Enhanced input validation and bounds checking
            try
                if isempty(obj.LinkedGroups)
                    uialert(obj.App.UIFigure, 'No link groups available for comparison.', 'No Links');
                    return;
                end

                % BOUNDS CHECK: Validate dropdown selections
                selectedGroupIdx = groupDropdown.Value;
                if selectedGroupIdx < 1 || selectedGroupIdx > length(obj.LinkedGroups)
                    uialert(obj.App.UIFigure, 'Invalid group selection.', 'Selection Error');
                    return;
                end

                selectedSignalIdx = signalDropdown.Value;
                if selectedSignalIdx < 1 || selectedSignalIdx > length(signalDropdown.String)
                    uialert(obj.App.UIFigure, 'Invalid signal selection.', 'Selection Error');
                    return;
                end

                selectedAnalysisIdx = analysisDropdown.Value;
                if selectedAnalysisIdx < 1 || selectedAnalysisIdx > length(analysisDropdown.String)
                    uialert(obj.App.UIFigure, 'Invalid analysis type selection.', 'Selection Error');
                    return;
                end

                group = obj.LinkedGroups{selectedGroupIdx};
                selectedSignal = signalDropdown.String{selectedSignalIdx};
                analysisType = analysisDropdown.String{selectedAnalysisIdx};

                % Validate group structure
                if ~isfield(group, 'CSVIndices') || isempty(group.CSVIndices)
                    uialert(obj.App.UIFigure, 'Selected group has no CSV indices.', 'Invalid Group');
                    return;
                end

                % Continue with rest of function with proper error handling...
                obj.performComparisonAnalysis(group, selectedSignal, analysisType);

            catch ME
                uialert(obj.App.UIFigure, sprintf('Comparison failed: %s', ME.message), 'Error');
                fprintf('Error in generateComparison: %s\n', ME.message);
            end
        end

        function performComparisonAnalysis(obj, group, selectedSignal, analysisType)
            % Complete comparison analysis with all missing logic
            try
                fprintf('Starting performComparisonAnalysis...\n');

                % Validate CSV indices in group
                validCSVIndices = [];
                for i = 1:numel(group.CSVIndices)
                    idx = group.CSVIndices(i);
                    if idx > 0 && idx <= numel(obj.App.DataManager.DataTables)
                        if ~isempty(obj.App.DataManager.DataTables{idx})
                            validCSVIndices(end+1) = idx;
                        end
                    end
                end

                if length(validCSVIndices) < 2
                    uialert(obj.App.UIFigure, 'Need at least 2 valid CSV files for comparison.', 'Insufficient Data');
                    return;
                end

                fprintf('Found %d valid CSV indices: %s\n', length(validCSVIndices), mat2str(validCSVIndices));

                % Collect shared signals across all valid CSVs
                allSignalSets = {};
                for i = 1:length(validCSVIndices)
                    idx = validCSVIndices(i);
                    T = obj.App.DataManager.DataTables{idx};
                    signals = setdiff(T.Properties.VariableNames, {'Time'});
                    allSignalSets{end+1} = signals;
                end

                % Find intersection of all signal sets (shared signals)
                sharedSignals = allSignalSets{1};
                for i = 2:length(allSignalSets)
                    sharedSignals = intersect(sharedSignals, allSignalSets{i});
                end

                fprintf('Found %d shared signals: %s\n', length(sharedSignals), strjoin(sharedSignals, ', '));

                if isempty(sharedSignals)
                    uialert(obj.App.UIFigure, 'No shared signals found across the linked CSV files.', 'No Common Signals');
                    return;
                end

                % Determine target signals for analysis
                if strcmp(selectedSignal, '<All Shared Signals>')
                    targetSignals = sharedSignals;
                    fprintf('Analyzing all %d shared signals\n', length(targetSignals));
                else
                    if ~ismember(selectedSignal, sharedSignals)
                        uialert(obj.App.UIFigure, sprintf('Selected signal "%s" is not available in all linked CSVs.', selectedSignal), 'Signal Not Available');
                        return;
                    end
                    targetSignals = {selectedSignal};
                    fprintf('Analyzing single signal: %s\n', selectedSignal);
                end

                % Create main comparison figure
                mainFig = figure('Name', sprintf('Comparison Analysis: %s', group.Name), ...
                    'NumberTitle', 'off', 'Position', [100, 100, 1200, 800]);

                % Setup subplot layout for multiple signals
                if length(targetSignals) > 1
                    numCols = min(3, length(targetSignals));
                    numRows = ceil(length(targetSignals) / numCols);
                    tiledlayout(numRows, numCols, 'TileSpacing', 'compact', 'Padding', 'compact');
                end

                % Store results for summary analysis
                signalResults = {};
                maxErrorPerSignal = [];
                tableData = {};

                % Process each target signal
                for s = 1:length(targetSignals)
                    signal = targetSignals{s};
                    fprintf('Processing signal %d/%d: %s\n', s, length(targetSignals), signal);

                    % Collect data from all valid CSVs for this signal
                    timeList = {};
                    valueList = {};
                    labels = {};

                    for i = 1:length(validCSVIndices)
                        csvIdx = validCSVIndices(i);
                        T = obj.App.DataManager.DataTables{csvIdx};

                        if ismember(signal, T.Properties.VariableNames)
                            % Get valid (non-NaN) data
                            timeCol = T.Time;
                            signalCol = T.(signal);
                            validIdx = ~isnan(signalCol) & ~isnan(timeCol) & isfinite(signalCol) & isfinite(timeCol);

                            if sum(validIdx) > 10  % Need at least 10 points for meaningful analysis
                                timeList{end+1} = timeCol(validIdx);
                                valueList{end+1} = signalCol(validIdx);

                                % Create descriptive label from CSV filename
                                if csvIdx <= length(obj.App.DataManager.CSVFilePaths) && ~isempty(obj.App.DataManager.CSVFilePaths{csvIdx})
                                    [~, name, ~] = fileparts(obj.App.DataManager.CSVFilePaths{csvIdx});
                                    labels{end+1} = name;
                                else
                                    labels{end+1} = sprintf('CSV_%d', csvIdx);
                                end
                            else
                                fprintf('  Warning: CSV %d has insufficient valid data for signal %s\n', csvIdx, signal);
                            end
                        end
                    end

                    fprintf('  Found valid data in %d CSVs for signal %s\n', length(valueList), signal);

                    if length(valueList) < 2
                        fprintf('  Skipping signal %s - need at least 2 CSV files with data\n', signal);
                        continue;
                    end

                    % Align all signals to a common time base
                    [commonTime, alignedData] = obj.alignSignalsToCommonTime(timeList, valueList);

                    if isempty(commonTime) || size(alignedData, 2) < 10
                        fprintf('  Skipping signal %s - time alignment failed or insufficient data\n', signal);
                        continue;
                    end

                    fprintf('  Aligned data: %d time points, %d signals\n', length(commonTime), size(alignedData, 1));

                    % Calculate statistical metrics and errors
                    meanSignal = mean(alignedData, 1);
                    stdSignal = std(alignedData, 0, 1);

                    % Calculate percentage error for each CSV relative to mean
                    errors = zeros(size(alignedData, 1), 1);
                    for i = 1:size(alignedData, 1)
                        diff = alignedData(i, :) - meanSignal;
                        meanAbs = mean(abs(meanSignal));
                        if meanAbs > eps
                            errors(i) = mean(abs(diff)) / meanAbs * 100;
                        else
                            errors(i) = 0;
                        end
                    end

                    % Store results for this signal
                    signalResults{end+1} = struct(...
                        'signal', signal, ...
                        'labels', {labels}, ...
                        'errors', errors, ...
                        'commonTime', commonTime, ...
                        'alignedData', alignedData, ...
                        'meanSignal', meanSignal, ...
                        'stdSignal', stdSignal);

                    maxErrorPerSignal(end+1) = max(errors);

                    % Add to summary table data
                    for i = 1:length(labels)
                        tableData(end+1, :) = {signal, labels{i}, errors(i)};
                    end

                    % Create subplot for this signal
                    if length(targetSignals) > 1
                        nexttile;
                    end

                    % Generate the actual plot
                    obj.createSignalComparisonPlot(signal, commonTime, alignedData, meanSignal, stdSignal, labels, errors, analysisType);
                end

                % Create summary table if we have results
                if ~isempty(signalResults)
                    obj.createAnalysisSummaryTable(tableData, maxErrorPerSignal, group.Name);

                    % Update status with success message
                    obj.App.StatusLabel.Text = sprintf('✅ Generated %s analysis for %d signal(s)', analysisType, length(signalResults));
                    obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

                    fprintf('Analysis completed successfully for %d signals\n', length(signalResults));
                else
                    uialert(obj.App.UIFigure, 'No valid signals could be analyzed. Check that your CSV files contain valid numerical data.', 'Analysis Failed');
                    obj.App.StatusLabel.Text = '❌ Analysis failed - no valid data';
                    obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
                end

            catch ME
                fprintf('Error in performComparisonAnalysis: %s\n', ME.message);
                fprintf('Stack trace:\n');
                for i = 1:length(ME.stack)
                    fprintf('  %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
                end

                uialert(obj.App.UIFigure, sprintf('Analysis failed: %s', ME.message), 'Error');
                obj.App.StatusLabel.Text = '❌ Analysis error';
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
                rethrow(ME);
            end
        end

        function [commonTime, alignedData] = alignSignalsToCommonTime(obj, timeList, valueList)
            % Align multiple signals to a common time base using interpolation
            try
                % Find the overlapping time range across all signals
                minStartTime = max(cellfun(@min, timeList));
                maxEndTime = min(cellfun(@max, timeList));

                if minStartTime >= maxEndTime
                    fprintf('Warning: No overlapping time range found\n');
                    fprintf('  Time ranges: ');
                    for i = 1:length(timeList)
                        fprintf('[%.2f, %.2f] ', min(timeList{i}), max(timeList{i}));
                    end
                    fprintf('\n');
                    commonTime = [];
                    alignedData = [];
                    return;
                end

                % Determine appropriate time resolution
                % Use the finest resolution among all signals, but limit to reasonable number of points
                allDt = [];
                for i = 1:length(timeList)
                    if length(timeList{i}) > 1
                        dt = mean(diff(sort(timeList{i})));
                        allDt(end+1) = dt;
                    end
                end

                if isempty(allDt)
                    commonTime = [];
                    alignedData = [];
                    return;
                end

                targetDt = min(allDt);
                maxPoints = 1000;  % Limit to prevent memory issues
                numPoints = min(maxPoints, ceil((maxEndTime - minStartTime) / targetDt));

                % Create common time vector
                commonTime = linspace(minStartTime, maxEndTime, numPoints)';

                fprintf('  Aligning to common time: %.2f to %.2f (%d points)\n', minStartTime, maxEndTime, numPoints);

                % Interpolate all signals to the common time base
                alignedData = zeros(length(valueList), length(commonTime));

                for i = 1:length(valueList)
                    try
                        % Sort time and values to ensure monotonic time for interpolation
                        [sortedTime, sortIdx] = sort(timeList{i});
                        sortedValues = valueList{i}(sortIdx);

                        % Remove duplicate time points (keep first occurrence)
                        [uniqueTime, uniqueIdx] = unique(sortedTime, 'first');
                        uniqueValues = sortedValues(uniqueIdx);

                        if length(uniqueTime) < 2
                            fprintf('    Warning: Signal %d has insufficient unique time points\n', i);
                            alignedData(i, :) = NaN;
                            continue;
                        end

                        % Interpolate to common time base
                        alignedData(i, :) = interp1(uniqueTime, uniqueValues, commonTime, 'linear', NaN);

                        % Check interpolation quality
                        nanCount = sum(isnan(alignedData(i, :)));
                        if nanCount > length(commonTime) * 0.5
                            fprintf('    Warning: Signal %d has >50%% NaN values after interpolation\n', i);
                        end

                    catch interpError
                        fprintf('    Warning: Interpolation failed for signal %d: %s\n', i, interpError.message);
                        alignedData(i, :) = NaN;
                    end
                end

                % Remove time points where any signal has NaN (for fair comparison)
                validCols = all(isfinite(alignedData), 1);
                validDataRatio = sum(validCols) / length(validCols);

                fprintf('  Valid data ratio after alignment: %.1f%%\n', validDataRatio * 100);

                if validDataRatio < 0.1  % Less than 10% valid data
                    fprintf('  Warning: Less than 10%% of aligned data is valid\n');
                    commonTime = [];
                    alignedData = [];
                    return;
                end

                commonTime = commonTime(validCols);
                alignedData = alignedData(:, validCols);

            catch ME
                fprintf('Error in alignSignalsToCommonTime: %s\n', ME.message);
                commonTime = [];
                alignedData = [];
            end
        end

        function createSignalComparisonPlot(obj, signal, commonTime, alignedData, meanSignal, stdSignal, labels, errors, analysisType)
            % Create the actual comparison plot for a single signal
            try
                hold on;

                switch analysisType
                    case 'Overlay Plot'
                        % Plot each signal with error in legend
                        colors = lines(size(alignedData, 1));
                        for i = 1:size(alignedData, 1)
                            plot(commonTime, alignedData(i, :), ...
                                'Color', colors(i, :), ...
                                'DisplayName', sprintf('%s (%.1f%% err)', labels{i}, errors(i)), ...
                                'LineWidth', 1.5);
                        end
                        title(sprintf('Overlay: %s (Max Error: %.2f%%)', signal, max(errors)), 'Interpreter', 'none');
                        ylabel(signal, 'Interpreter', 'none');

                    case 'Difference Plot'
                        % Plot differences from first signal
                        if size(alignedData, 1) >= 2
                            baseSignal = alignedData(1, :);
                            colors = lines(size(alignedData, 1) - 1);
                            for i = 2:size(alignedData, 1)
                                diff = alignedData(i, :) - baseSignal;
                                plot(commonTime, diff, ...
                                    'Color', colors(i-1, :), ...
                                    'DisplayName', sprintf('%s - %s', labels{i}, labels{1}), ...
                                    'LineWidth', 1.5);
                            end
                            title(sprintf('Differences from %s: %s', labels{1}, signal), 'Interpreter', 'none');
                            ylabel(sprintf('Δ %s', signal), 'Interpreter', 'none');
                        else
                            text(0.5, 0.5, 'Need at least 2 signals for difference plot', ...
                                'Units', 'normalized', 'HorizontalAlignment', 'center');
                        end

                    case 'Statistical Summary'
                        % Plot mean with confidence bands
                        upperBound = meanSignal + stdSignal;
                        lowerBound = meanSignal - stdSignal;

                        % Create filled area for standard deviation
                        fill([commonTime; flipud(commonTime)], ...
                            [upperBound'; flipud(lowerBound')], ...
                            [0.8 0.8 1], 'EdgeColor', 'none', ...
                            'DisplayName', 'Mean ± 1σ', 'FaceAlpha', 0.3);

                        % Plot mean line
                        plot(commonTime, meanSignal, 'b-', 'LineWidth', 2, 'DisplayName', 'Mean');

                        % Plot individual signals as thin lines
                        colors = lines(size(alignedData, 1));
                        for i = 1:size(alignedData, 1)
                            plot(commonTime, alignedData(i, :), '--', ...
                                'Color', colors(i, :), 'LineWidth', 0.8, ...
                                'DisplayName', labels{i});
                        end

                        title(sprintf('Statistics: %s (Max Error: %.2f%%)', signal, max(errors)), 'Interpreter', 'none');
                        ylabel(signal, 'Interpreter', 'none');
                end

                xlabel('Time');
                legend('Location', 'best', 'Interpreter', 'none');
                grid on;
                hold off;

            catch ME
                fprintf('Error creating plot for signal %s: %s\n', signal, ME.message);
                text(0.5, 0.5, sprintf('Plot error: %s', ME.message), ...
                    'Units', 'normalized', 'HorizontalAlignment', 'center', 'Color', 'red');
            end
        end

        function createAnalysisSummaryTable(obj, tableData, maxErrorPerSignal, groupName)
            % Create a summary table with results sorted by error
            try
                if isempty(tableData)
                    return;
                end

                % Sort table data by error (descending)
                errorCol = cell2mat(tableData(:, 3));
                [~, sortIdx] = sort(errorCol, 'descend');
                sortedTableData = tableData(sortIdx, :);

                % Create summary figure
                summaryFig = figure('Name', sprintf('Analysis Summary: %s', groupName), ...
                    'NumberTitle', 'off', 'Position', [200, 50, 700, 500]);

                % Add title and description
                annotation(summaryFig, 'textbox', [0.1, 0.92, 0.8, 0.06], ...
                    'String', sprintf('Comparison Summary: %s', groupName), ...
                    'FontWeight', 'bold', 'FontSize', 12, ...
                    'HorizontalAlignment', 'center', 'EdgeColor', 'none');

                annotation(summaryFig, 'textbox', [0.1, 0.87, 0.8, 0.04], ...
                    'String', 'Signals and CSV sources sorted by error (highest first)', ...
                    'FontSize', 10, 'HorizontalAlignment', 'center', 'EdgeColor', 'none');

                % Create the data table
                summaryTable = uitable(summaryFig, 'Data', sortedTableData, ...
                    'ColumnName', {'Signal', 'CSV Source', 'Error (%)'}, ...
                    'ColumnWidth', {200, 250, 120}, ...
                    'RowName', [], ...
                    'Units', 'normalized', ...
                    'Position', [0.05, 0.05, 0.9, 0.8]);

                % Color-code rows by error level
                try
                    numRows = size(sortedTableData, 1);
                    bgColors = ones(numRows, 3) * 0.95; % Default light gray

                    for i = 1:numRows
                        error = sortedTableData{i, 3};
                        if error > 10
                            bgColors(i, :) = [1, 0.8, 0.8]; % Light red for high error
                        elseif error > 5
                            bgColors(i, :) = [1, 1, 0.8];   % Light yellow for medium error
                        else
                            bgColors(i, :) = [0.8, 1, 0.8]; % Light green for low error
                        end
                    end

                    summaryTable.BackgroundColor = bgColors;
                catch
                    % If coloring fails, continue without it
                end

                fprintf('Created summary table with %d entries\n', size(sortedTableData, 1));

            catch ME
                fprintf('Error creating summary table: %s\n', ME.message);
            end
        end

        function csvIdx = getCSVIndexFromNodeText(obj, nodeText)
            csvIdx = 0;

            % Input validation
            if ~ischar(nodeText) && ~isstring(nodeText)
                return;
            end

            % Convert to char for consistent handling
            nodeText = char(nodeText);

            % Validate DataManager exists
            if ~isprop(obj.App, 'DataManager') || ...
                    isempty(obj.App.DataManager) || ...
                    ~isprop(obj.App.DataManager, 'CSVFilePaths')
                return;
            end

            csvPaths = obj.App.DataManager.CSVFilePaths;
            if isempty(csvPaths)
                return;
            end

            % BOUNDS CHECK: Find matching CSV file safely
            for i = 1:length(csvPaths)
                if i <= length(csvPaths) && ~isempty(csvPaths{i})
                    try
                        [~, name, ext] = fileparts(csvPaths{i});
                        if strcmp(nodeText, [name ext])
                            csvIdx = i;
                            return;
                        end
                    catch ME
                        fprintf('Warning: Error processing CSV path at index %d: %s\n', i, ME.message);
                        continue;
                    end
                end
            end
        end
    end
end