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

            % Test linking
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Test Current Links', ...
                'Position', [20 100 150 30], 'Callback', @(~,~) obj.testCurrentLinks());

            % Clear all links
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Clear All Links', ...
                'Position', [180 100 120 30], 'Callback', @(~,~) obj.clearAllLinks());

            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [500 20 80 30], 'Callback', @(~,~) close(d));
        end

        function showComparisonDialog(obj)
            % Comparison tools dialog
            d = dialog('Name', 'Comparison Analysis', 'Position', [250 250 500 300]);
            % Shared signals dropdown (added after groupDropdown)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 110 120 20], ...
                'String', 'Select Signal:', 'FontWeight', 'bold');

            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 110 200 25], ...
                'String', {'<All Shared Signals>'}, 'Enable', 'off');  % Will populate later




            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 460 25], ...
                'String', 'Comparison Analysis Tools', ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 230 460 20], ...
                'String', 'Generate comparison plots and analysis for linked signals.', ...
                'FontSize', 11);

            % Select linked group for comparison
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 190 120 20], ...
                'String', 'Select Link Group:', 'FontWeight', 'bold');

            groupNames = obj.getLinkGroupNames();
            groupDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 190 200 25], 'String', groupNames);

            % Find shared signals immediately
            group = obj.LinkedGroups{groupDropdown.Value};
            allSignals = [];
            for i = 1:numel(group.CSVIndices)
                idx = group.CSVIndices(i);
                if idx > numel(obj.App.DataManager.DataTables), continue; end
                T = obj.App.DataManager.DataTables{idx};
                if isempty(T), continue; end
                sigs = setdiff(T.Properties.VariableNames, {'Time'});
                if isempty(allSignals)
                    allSignals = sigs;
                else
                    allSignals = intersect(allSignals, sigs);
                end
            end

            if isempty(allSignals)
                signalDropdown.String = {'<No shared signals>'};
                signalDropdown.Enable = 'off';
            else
                signalDropdown.String = ['<All Shared Signals>', sort(allSignals)];
                signalDropdown.Enable = 'on';
            end

            % Analysis type
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Analysis Type:', 'FontWeight', 'bold');

            analysisDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 200 25], ...
                'String', {'Overlay Plot', 'Difference Plot', 'Statistical Summary'});

            % Generate button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Generate Analysis', ...
                'Position', [200 50 100 30], 'FontWeight', 'bold', ...
                'Callback', @(~,~) obj.generateComparison(groupDropdown, analysisDropdown, signalDropdown, d));


            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [400 20 80 30], 'Callback', @(~,~) close(d));
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
            % Clear all linking relationships
            if isempty(obj.LinkedGroups)
                msgbox('No link groups to clear.', 'No Links', 'help');
                return;
            end

            % Use questdlg instead of uiconfirm for traditional figure compatibility
            answer = questdlg(sprintf('Clear all %d link groups?', length(obj.LinkedGroups)), ...
                'Confirm Clear', 'Clear All', 'Cancel', 'Cancel');

            if strcmp(answer, 'Clear All')
                obj.LinkedGroups = {};
                obj.App.StatusLabel.Text = 'Cleared all link groups';
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
            for i = 1:numel(obj.App.DataManager.CSVFilePaths)
                [~, csvName, ext] = fileparts(obj.App.DataManager.CSVFilePaths{i});
                availableNodes{end+1} = sprintf('CSV %d: %s%s', i, csvName, ext);
            end
            if isempty(availableNodes)
                availableNodes = {'No CSV files loaded'};
            end
        end

        function createLinkGroup(obj, listbox, dialog)
            selectedIndices = listbox.Value;
            if length(selectedIndices) < 2
                msgbox('Please select at least 2 CSV files to link.', 'Selection Required', 'warn');
                return;
            end

            % Selected CSV indices are listbox.Value directly
            csvIndices = selectedIndices;

            % Create new link group
            newGroup = struct();
            newGroup.Type = 'nodes';
            newGroup.CSVIndices = csvIndices;

            % Construct a meaningful name using filenames
            linkedNames = {};
            for i = 1:numel(csvIndices)
                [~, name, ~] = fileparts(obj.App.DataManager.CSVFilePaths{csvIndices(i)});
                linkedNames{end+1} = name;
            end
            newGroup.Name = ['Linked CSVs: ' strjoin(linkedNames, ', ')];

            % Assign group color
            newGroup.Color = obj.LinkColors(mod(length(obj.LinkedGroups), size(obj.LinkColors, 1)) + 1, :);

            % Add to link groups
            obj.LinkedGroups{end+1} = newGroup;

            % Update UI dialog with new group info
            groupsText = findobj(dialog, 'Style', 'edit', 'Enable', 'off');
            if ~isempty(groupsText)
                groupsText.String = obj.getLinkGroupsText();
            end

            msgbox(sprintf('Created link group with %d CSV files.', length(csvIndices)), ...
                'Link Group Created', 'help');
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
            signalName = signalInfo.Signal;

            % Look for the same signal name in other CSVs in the group
            for i = 1:length(group.CSVIndices)
                csvIdx = group.CSVIndices(i);
                if csvIdx ~= signalInfo.CSVIdx && csvIdx <= length(obj.App.DataManager.DataTables)
                    T = obj.App.DataManager.DataTables{csvIdx};
                    if ~isempty(T) && ismember(signalName, T.Properties.VariableNames)
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

        function testCurrentLinks(obj)
            if isempty(obj.LinkedGroups)
                msgbox('No link groups to test.', 'No Links', 'help');
                return;
            end

            % Simple test - show what signals would be linked
            msg = 'Link Groups:';
            msg = [msg newline newline];
            for i = 1:length(obj.LinkedGroups)
                group = obj.LinkedGroups{i};
                msg = [msg sprintf('%s:', group.Name)];
                msg = [msg newline];

                if strcmp(group.Type, 'nodes')
                    for j = 1:length(group.CSVIndices)
                        csvIdx = group.CSVIndices(j);
                        if csvIdx <= length(obj.App.DataManager.CSVFilePaths)
                            [~, name, ext] = fileparts(obj.App.DataManager.CSVFilePaths{csvIdx});
                            T = obj.App.DataManager.DataTables{csvIdx};
                            if ~isempty(T)
                                signals = setdiff(T.Properties.VariableNames, {'Time'});
                                msg = [msg sprintf('  CSV %d (%s%s): %d signals', csvIdx, name, ext, length(signals))];
                                msg = [msg newline];
                            end
                        end
                    end
                end
                msg = [msg newline];
            end

            msgbox(msg, 'Link Groups Test', 'help');
        end

        function generateComparison(obj, groupDropdown, analysisDropdown, signalDropdown, ~)
            if isempty(obj.LinkedGroups)
                msgbox('No link groups available for comparison.', 'No Links', 'warn');
                return;
            end

            selectedGroupIdx = groupDropdown.Value;
            selectedSignalIdx = signalDropdown.Value;
            selectedAnalysis = analysisDropdown.Value;

            group = obj.LinkedGroups{selectedGroupIdx};
            selectedSignal = signalDropdown.String{selectedSignalIdx};
            analysisType = analysisDropdown.String{selectedAnalysis};

            % Collect shared signals again
            sharedSignals = [];
            for i = 1:numel(group.CSVIndices)
                idx = group.CSVIndices(i);
                T = obj.App.DataManager.DataTables{idx};
                if isempty(T), continue; end
                sigs = setdiff(T.Properties.VariableNames, {'Time'});
                if isempty(sharedSignals)
                    sharedSignals = sigs;
                else
                    sharedSignals = intersect(sharedSignals, sigs);
                end
            end

            if isempty(sharedSignals)
                msgbox('No shared signals found in this group.', 'No Common Signals', 'warn');
                return;
            end

            % Determine target signals
            if strcmp(selectedSignal, '<All Shared Signals>')
                targetSignals = sharedSignals;
            else
                targetSignals = {selectedSignal};
            end

            % Plot and compare
            figure('Name', ['Comparison: ' group.Name], 'NumberTitle', 'off');
            tiledlayout('flow');
            reportLines = {};

            for s = 1:numel(targetSignals)
                sig = targetSignals{s};
                timeList = {}; valueList = {}; labels = {};

                for i = 1:numel(group.CSVIndices)
                    idx = group.CSVIndices(i);
                    T = obj.App.DataManager.DataTables{idx};
                    if isempty(T) || ~ismember(sig, T.Properties.VariableNames), continue; end

                    valid = ~isnan(T.(sig));
                    timeList{end+1} = T.Time(valid);
                    valueList{end+1} = T.(sig)(valid);

                    [~, label, ~] = fileparts(obj.App.DataManager.CSVFilePaths{idx});
                    labels{end+1} = label;
                end

                if numel(valueList) < 2, continue; end

                % Interpolate to common time
                tMin = max(cellfun(@(t) min(t), timeList));
                tMax = min(cellfun(@(t) max(t), timeList));
                commonTime = linspace(tMin, tMax, 200);

                aligned = nan(numel(valueList), numel(commonTime));
                for i = 1:numel(valueList)
                    aligned(i,:) = interp1(timeList{i}, valueList{i}, commonTime, 'linear', NaN);
                end

                % Reference = mean
                ref = mean(aligned, 1);
                errors = mean(abs((aligned - ref) ./ max(abs(ref), eps)), 2) * 100;

                % Append to report
                reportLines{end+1} = sprintf('Signal: %s', sig);
                for i = 1:numel(labels)
                    reportLines{end+1} = sprintf('  %s: %.2f%% error', labels{i}, errors(i));
                end

                % === Plot Depending on Analysis ===
                nexttile;
                switch analysisType
                    case 'Overlay Plot'
                        hold on;
                        for i = 1:numel(valueList)
                            plot(commonTime, aligned(i,:), 'DisplayName', labels{i}, 'LineWidth', 1.5);
                        end
                        title(['Overlay: ' sig], 'Interpreter', 'none');

                    case 'Difference Plot'
                        hold on;
                        base = aligned(1,:);
                        for i = 2:numel(valueList)
                            diff = base - aligned(i,:);
                            plot(commonTime, diff, 'DisplayName', [labels{1} ' - ' labels{i}], 'LineWidth', 1.5);
                        end
                        title(['Difference: ' sig], 'Interpreter', 'none');

                    case 'Statistical Summary'
                        meanVals = mean(aligned, 1);
                        stdVals = std(aligned, 0, 1);
                        fill([commonTime fliplr(commonTime)], ...
                            [meanVals+stdVals fliplr(meanVals-stdVals)], ...
                            [0.8 0.8 1], 'EdgeColor', 'none');
                        hold on;
                        plot(commonTime, meanVals, 'b-', 'LineWidth', 2);
                        title(['Mean ± STD: ' sig], 'Interpreter', 'none');
                end

                legend({'Mean ± STD'}, 'Location', 'best');
                xlabel('Time'); ylabel(sig); grid on;
            end

            if ~isempty(reportLines)
                % Parse reportLines into signal names and rows
                tableData = {};
                currentSignal = '';
                for i = 1:numel(reportLines)
                    line = strtrim(reportLines{i});
                    if startsWith(line, 'Signal:')
                        currentSignal = extractAfter(line, 'Signal: ');
                    else
                        parts = split(line, ':');
                        if numel(parts) == 2
                            tableData(end+1, :) = {currentSignal, strtrim(parts{1}), str2double(erase(parts{2}, '% error'))}; %#ok<AGROW>
                        end
                    end
                end

                % Create new figure with uitable
                f = figure('Name', 'Comparison Report', 'NumberTitle', 'off', 'Position', [100, 100, 600, 400]);
                t = uitable(f, 'Data', tableData, ...
                    'ColumnName', {'Signal', 'Label', 'Error (%)'}, ...
                    'ColumnWidth', {150, 200, 100}, ...
                    'RowName', [], ...
                    'Units', 'normalized', ...
                    'Position', [0 0 1 1]);
            else
                msgbox('No signals available for comparison.', 'Empty', 'warn');
            end


        end

        function csvIdx = getCSVIndexFromNodeText(obj, nodeText)
            csvIdx = 0;
            % Try to find matching CSV file
            for i = 1:length(obj.App.DataManager.CSVFilePaths)
                [~, name, ext] = fileparts(obj.App.DataManager.CSVFilePaths{i});
                if strcmp(nodeText, [name ext])
                    csvIdx = i;
                    return;
                end
            end
        end
    end
end