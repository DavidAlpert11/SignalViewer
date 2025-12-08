classdef UIController < handle
    properties
        App
    end

    methods
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        % UIController Methods
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

        % Constructor
        function obj = UIController(app)
            % Create a UIController for the given app
            obj.App = app;
        end


        function setupCallbacks(obj)
            % Setup UI callbacks for the controller
            app = obj.App;

            try
                % Layout change callbacks
                if isprop(app, 'RowsSpinner') && ~isempty(app.RowsSpinner)
                    app.RowsSpinner.ValueChangedFcn = @(~,~) obj.onLayoutChanged();
                end

                if isprop(app, 'ColsSpinner') && ~isempty(app.ColsSpinner)
                    app.ColsSpinner.ValueChangedFcn = @(~,~) obj.onLayoutChanged();
                end

                % Subplot selection callback
                if isprop(app, 'SubplotDropdown') && ~isempty(app.SubplotDropdown)
                    app.SubplotDropdown.ValueChangedFcn = @(~,~) obj.onSubplotSelected();
                end

                % Signal table callback
                if isprop(app, 'SignalTable') && ~isempty(app.SignalTable)
                    app.SignalTable.CellEditCallback = @(src, event) obj.onSignalTableEdit(event);
                end

                fprintf('UIController callbacks setup complete\n');

            catch ME
                fprintf('Warning: Error setting up UIController callbacks: %s\n', ME.message);
            end
        end
        % Callback for when the subplot layout spinners are changed
        function onLayoutChanged(obj)
            app = obj.App;
            rows = max(1, min(10, round(app.RowsSpinner.Value)));
            cols = max(1, min(10, round(app.ColsSpinner.Value)));
            tabIdx = app.PlotManager.CurrentTabIdx;
            app.PlotManager.createSubplotsForTab(tabIdx, rows, cols);
            % Update subplot dropdown
            obj.updateSubplotDropdown();
            app.PlotManager.refreshPlots(tabIdx);
        end

        function addMoreCSVs(obj)
            app = obj.App;

            try
                [files, path] = uigetfile('*.csv', 'Add More CSV Files', 'MultiSelect', 'on');
                if isequal(files,0)
                    return;
                end
                if ischar(files)
                    files = {files};
                end

                % Validate input
                if isempty(files)
                    return;
                end

                % Get new file paths
                newCSVPaths = cellfun(@(f) fullfile(path, f), files, 'UniformOutput', false);

                % BOUNDS CHECK: Ensure DataManager arrays exist
                if isempty(app.DataManager.CSVFilePaths)
                    app.DataManager.CSVFilePaths = {};
                end
                if isempty(app.DataManager.DataTables)
                    app.DataManager.DataTables = {};
                end
                if isempty(app.DataManager.LastFileModTimes)
                    app.DataManager.LastFileModTimes = {};
                end
                if isempty(app.DataManager.LastReadRows)
                    app.DataManager.LastReadRows = {};
                end
                if isempty(app.DataManager.StreamingTimers)
                    app.DataManager.StreamingTimers = {};
                end
                if isempty(app.DataManager.LatestDataRates)
                    app.DataManager.LatestDataRates = {};
                end

                % Append to existing CSVs
                existingCount = numel(app.DataManager.CSVFilePaths);
                app.DataManager.CSVFilePaths = [app.DataManager.CSVFilePaths, newCSVPaths];

                % Extend arrays to accommodate new CSVs
                numNewCSVs = numel(newCSVPaths);
                app.DataManager.DataTables = [app.DataManager.DataTables, cell(1, numNewCSVs)];
                app.DataManager.LastFileModTimes = [app.DataManager.LastFileModTimes, cell(1, numNewCSVs)];
                app.DataManager.LastReadRows = [app.DataManager.LastReadRows, cell(1, numNewCSVs)];
                app.DataManager.StreamingTimers = [app.DataManager.StreamingTimers, cell(1, numNewCSVs)];
                app.DataManager.LatestDataRates = [app.DataManager.LatestDataRates, cell(1, numNewCSVs)];

                % Load new CSVs based on streaming mode
                if app.DataManager.StreamingEnabled
                    % Start streaming for the new CSVs only
                    for i = 1:numNewCSVs
                        csvIdx = existingCount + i;
                        app.DataManager.startStreamingForCSV(csvIdx);
                    end
                else
                    % Load data once for new CSVs
                    for i = 1:numNewCSVs
                        csvIdx = existingCount + i;
                        app.DataManager.readInitialData(csvIdx);
                    end
                end

                % Update signal tree to include new signals
                app.buildSignalTree();
                app.PlotManager.refreshPlots();

                % Update status
                if app.DataManager.StreamingEnabled
                    modeStr = 'streaming';
                else
                    modeStr = 'loaded';
                end
                app.StatusLabel.Text = sprintf('➕ Added %d new CSV(s). Total: %d (%s)', numNewCSVs, numel(app.DataManager.CSVFilePaths), modeStr);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                app.StatusLabel.Text = sprintf('❌ Failed to add CSVs: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                fprintf('Error in addMoreCSVs: %s\n', ME.message);
            end
        end
        % Update the items in the subplot dropdown based on the current tab layout
        function updateSubplotDropdown(obj)
            app = obj.App;
            tabIdx = app.PlotManager.CurrentTabIdx;
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ~isempty(app.PlotManager.AxesArrays{tabIdx})
                nPlots = numel(app.PlotManager.AxesArrays{tabIdx});
                plotNames = cell(nPlots, 1);
                for i = 1:nPlots
                    plotNames{i} = sprintf('Plot %d', i);
                end
                app.SubplotDropdown.Items = plotNames;
                % Ensure selected subplot is within bounds
                if app.PlotManager.SelectedSubplotIdx > nPlots
                    app.PlotManager.SelectedSubplotIdx = 1;
                end
                app.SubplotDropdown.Value = sprintf('Plot %d', app.PlotManager.SelectedSubplotIdx);
            else
                app.SubplotDropdown.Items = {'Plot 1'};
                app.SubplotDropdown.Value = 'Plot 1';
                app.PlotManager.SelectedSubplotIdx = 1;
            end
        end

        % Callback for when a subplot is selected from the dropdown
        function onSubplotSelected(obj)
            app = obj.App;
            selectedItem = app.SubplotDropdown.Value;
            % Extract plot number from selection
            plotNum = str2double(regexp(selectedItem, '\d+', 'match', 'once'));
            if ~isempty(plotNum) && plotNum > 0
                app.PlotManager.SelectedSubplotIdx = plotNum;
                % Update visual feedback
                app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, plotNum);
                % Update signal table to reflect current subplot
                % obj.updateSignalCheckboxes(); % Removed as per edit hint
            end
        end

        function onSignalTableEdit(obj, event)
            app = obj.App;
            data = app.SignalTable.Data;
            row = event.Indices(1);
            col = event.Indices(2);

            % Extract clean signal name (remove visual indicators)
            originalSignal = data.Signal{row};
            cleanSignal = strrep(strrep(originalSignal, '● ', ''), '○ ', '');

            fullNames = app.DataManager.SignalNames;
            shortNames = cellfun(@(s) strtrim(obj.getLastPart(s)), fullNames, 'UniformOutput', false);
            idx = find(strcmp(shortNames, cleanSignal), 1);
            if isempty(idx), return; end
            fullName = fullNames{idx};

            switch col
                case 3  % Plot (Selected)
                    % Update the assigned signals for current subplot
                    currentTabIdx = app.PlotManager.CurrentTabIdx;
                    selectedSubplotIdx = app.PlotManager.SelectedSubplotIdx;

                    % Get currently selected signals from the table
                    selectedRows = find(data.Plot);
                    selectedSignals = cell(length(selectedRows), 1);
                    for i = 1:length(selectedRows)
                        cleanName = strrep(strrep(data.Signal{selectedRows(i)}, '● ', ''), '○ ', '');
                        shortIdx = find(strcmp(shortNames, cleanName), 1);
                        if ~isempty(shortIdx)
                            selectedSignals{i} = fullNames{shortIdx};
                        end
                    end

                    % Update the assigned signals
                    app.PlotManager.AssignedSignals{currentTabIdx}{selectedSubplotIdx} = selectedSignals;

                    % Refresh plots and update visual feedback
                    app.PlotManager.refreshPlots(currentTabIdx);
                    % obj.updateSignalTableVisualFeedback(); % Removed as per edit hint

                case 4  % Scale
                    scale = data.Scale(row);
                    if isnumeric(scale) && isfinite(scale) && scale ~= 0
                        app.DataManager.SignalScaling(fullName) = scale;
                    else
                        app.DataManager.SignalScaling(fullName) = 1.0;
                        data.Scale(row) = 1.0;
                        app.SignalTable.Data = data;
                    end
                    app.PlotManager.refreshPlots();

                case 5  % State
                    app.DataManager.StateSignals(fullName) = data.State(row);
                    app.PlotManager.refreshPlots();
                    % obj.updateSignalCheckboxes(); % Removed as per edit hint
            end
        end

        function part = getLastPart(~, s)
            parts = split(s, ':');
            part = strtrim(parts{end});
        end

        function clearPlotsOnly(obj)
            app = obj.App;

            % Clear all subplot highlights
            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                app.clearSubplotHighlights(tabIdx);
            end

            % Clear all plots but keep the axes
            for i = 1:numel(app.PlotManager.AxesArrays)
                if ~isempty(app.PlotManager.AxesArrays{i})
                    for ax = app.PlotManager.AxesArrays{i}
                        if isvalid(ax)
                            cla(ax);
                            legend(ax, 'off');
                            % Reset to default empty plot appearance
                            ax.XLim = [0 10];
                            ax.YLim = [-1 1];
                        end
                    end
                    % Clear signal assignments but keep subplot structure
                    nPlots = numel(app.PlotManager.AxesArrays{i});
                    app.PlotManager.AssignedSignals{i} = cell(nPlots, 1);
                    for j = 1:nPlots
                        app.PlotManager.AssignedSignals{i}{j} = {};
                    end
                end
            end

            % Clear signal tree selection (but keep the tree structure since CSVs are still loaded)
            if ~isempty(app.SignalTree) && isvalid(app.SignalTree)
                app.SignalTree.SelectedNodes = [];
                % Update tree to remove checkmarks
                app.PlotManager.updateSignalTreeVisualIndicators({});
            end

            % FIXED: Don't clear derived signals in clearPlotsOnly - only clear plot assignments
            % Derived signals should remain available for future use

            % Reset selected subplot
            app.PlotManager.SelectedSubplotIdx = 1;

            % Update status
            app.StatusLabel.Text = '🗑️ Plots cleared (CSVs and derived signals still loaded)';
            app.StatusLabel.FontColor = [0.2 0.6 0.9];

            % Refresh to show empty plots
            app.PlotManager.refreshPlots();

            % Highlight the first subplot
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, 1);
        end
        function clearAll(obj)
            app = obj.App;
            % Disable cursor first
            if app.CursorState
                app.PlotManager.disableCursorMode();
                app.CursorState = false;
                if ~isempty(app.CursorMenuItem)
                    app.CursorMenuItem.Text = '🎯 Enable Crosshair Cursor';
                end
            end
            % Stop all streaming first
            app.DataManager.stopStreamingAll();

            % Clear all subplot highlights
            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                app.clearSubplotHighlights(tabIdx);
            end

            % Clear all plots
            for i = 1:numel(app.PlotManager.AxesArrays)
                if ~isempty(app.PlotManager.AxesArrays{i})
                    for ax = app.PlotManager.AxesArrays{i}
                        if isvalid(ax)
                            cla(ax);
                            legend(ax, 'off');
                            % Reset to default empty plot appearance
                            ax.XLim = [0 10];
                            ax.YLim = [-1 1];
                        end
                    end
                    % Clear signal assignments
                    nPlots = numel(app.PlotManager.AxesArrays{i});
                    app.PlotManager.AssignedSignals{i} = cell(nPlots, 1);
                    for j = 1:nPlots
                        app.PlotManager.AssignedSignals{i}{j} = {};
                    end
                end
            end

            % Clear ALL CSV data and related structures
            app.DataManager.DataTables = {};
            app.DataManager.CSVFilePaths = {};
            app.DataManager.SignalNames = {};
            app.DataManager.LastFileModTimes = {};
            app.DataManager.LastReadRows = {};
            app.DataManager.StreamingTimers = {};
            app.DataManager.LatestDataRates = {};
            app.DataManager.SignalScaling = containers.Map();
            app.DataManager.StateSignals = containers.Map();
            app.DataManager.DataCount = 0;
            app.DataManager.UpdateCounter = 0;

            % FIXED: Clear ALL derived signals when doing clearAll
            if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations)
                app.SignalOperations.clearAllDerivedSignals();
            end

            % Clear signal tree completely
            if ~isempty(app.SignalTree) && isvalid(app.SignalTree)
                delete(app.SignalTree.Children);
            end

            % Clear app-level data
            if isprop(app, 'SubplotMetadata')
                app.SubplotMetadata = {};
            end
            if isprop(app, 'SignalStyles')
                app.SignalStyles = struct();
            end

            % Reset UI state
            app.PlotManager.SelectedSubplotIdx = 1;

            % Update status labels
            app.StatusLabel.Text = '🗑️ Everything cleared (including derived signals)';
            app.StatusLabel.FontColor = [0.5 0.5 0.5];
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';
            app.StreamingInfoLabel.Text = '';

            % Refresh to show empty state
            app.PlotManager.refreshPlots();

            % Highlight the first subplot
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, 1);
        end

        function exportCurrentSubplot(obj)
            app = obj.App;
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Get signals assigned to current subplot
            if tabIdx <= numel(app.PlotManager.AssignedSignals) && ...
                    subplotIdx <= numel(app.PlotManager.AssignedSignals{tabIdx})
                assignedSignals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            else
                assignedSignals = {};
            end

            if isempty(assignedSignals)
                app.StatusLabel.Text = '⚠️ No signals in current subplot';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            obj.exportSignalsToFolder(assignedSignals, sprintf('Tab%d_Plot%d', tabIdx, subplotIdx));
        end

        function delete(obj)
            % Cleanup when UIController is destroyed
            try
                % Break circular reference to App (CRITICAL)
                obj.App = [];

            catch ME
                fprintf('Warning during UIController cleanup: %s\n', ME.message);
            end
        end
        function exportCurrentTabActiveSubplots(obj)
            app = obj.App;
            tabIdx = app.PlotManager.CurrentTabIdx;

            % Collect all signals from subplots that have signals
            allSignals = {};
            activeSubplots = [];

            if tabIdx <= numel(app.PlotManager.AssignedSignals)
                for subplotIdx = 1:numel(app.PlotManager.AssignedSignals{tabIdx})
                    signals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                    if ~isempty(signals)
                        allSignals = [allSignals, signals];
                        activeSubplots(end+1) = subplotIdx;
                    end
                end
            end

            if isempty(allSignals)
                app.StatusLabel.Text = '⚠️ No active subplots in current tab';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            obj.exportSignalsToFolder(allSignals, sprintf('Tab%d_ActiveSubplots', tabIdx));
        end

        function exportCurrentTabAllSignals(obj)
            app = obj.App;

            % Export all signals from all CSVs (not filtered by subplot assignment)
            allSignals = {};
            for i = 1:numel(app.DataManager.DataTables)
                if ~isempty(app.DataManager.DataTables{i})
                    signals = setdiff(app.DataManager.DataTables{i}.Properties.VariableNames, {'Time'});
                    for j = 1:numel(signals)
                        sigInfo = struct('CSVIdx', i, 'Signal', signals{j});
                        allSignals{end+1} = sigInfo;
                    end
                end
            end

            if isempty(allSignals)
                app.StatusLabel.Text = '⚠️ No signals available';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            tabIdx = app.PlotManager.CurrentTabIdx;
            obj.exportSignalsToFolder(allSignals, sprintf('Tab%d_AllSignals', tabIdx));
        end

        function exportAllTabsActiveSubplots(obj)
            app = obj.App;

            % Collect signals from all active subplots across all tabs
            allSignals = {};

            for tabIdx = 1:numel(app.PlotManager.AssignedSignals)
                for subplotIdx = 1:numel(app.PlotManager.AssignedSignals{tabIdx})
                    signals = app.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
                    if ~isempty(signals)
                        allSignals = [allSignals, signals];
                    end
                end
            end

            if isempty(allSignals)
                app.StatusLabel.Text = '⚠️ No active subplots found';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            obj.exportSignalsToFolder(allSignals, 'AllTabs_ActiveSubplots');
        end

        function exportSignalsToFolder(obj, signalList, folderSuffix)
            app = obj.App;

            % Input validation
            if isempty(signalList)
                app.StatusLabel.Text = '⚠️ No signals to export';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Ask user to select export folder
            exportFolder = uigetdir(pwd, 'Select Folder to Export CSVs');
            if isequal(exportFolder, 0)
                app.restoreFocus();
                return;
            end

            try
                % Create subfolder with timestamp
                timestamp = datestr(now, 'yyyymmdd_HHMMSS');
                exportSubfolder = fullfile(exportFolder, sprintf('CSV_Export_%s_%s', folderSuffix, timestamp));

                if ~exist(exportSubfolder, 'dir')
                    mkdir(exportSubfolder);
                end

                % Group signals by CSV AND handle derived signals separately
                csvGroups = containers.Map('KeyType', 'int32', 'ValueType', 'any');
                derivedSignals = {};

                for i = 1:numel(signalList)
                    if i <= numel(signalList) % BOUNDS CHECK
                        sigInfo = signalList{i};

                        % Validate signal info structure
                        if ~isstruct(sigInfo) || ~isfield(sigInfo, 'CSVIdx') || ~isfield(sigInfo, 'Signal')
                            continue;
                        end

                        csvIdx = sigInfo.CSVIdx;

                        if csvIdx == -1
                            % Derived signal
                            derivedSignals{end+1} = sigInfo;
                        else
                            % BOUNDS CHECK: Validate CSV index
                            if csvIdx > 0 && csvIdx <= numel(app.DataManager.DataTables)
                                % Regular CSV signal
                                if csvGroups.isKey(csvIdx)
                                    csvGroups(csvIdx) = [csvGroups(csvIdx), {sigInfo.Signal}];
                                else
                                    csvGroups(csvIdx) = {sigInfo.Signal};
                                end
                            end
                        end
                    end
                end

                exportedCount = 0;

                % Export CSV groups (regular signals) with bounds checking
                if ~isempty(csvGroups.keys)
                    csvIndices = cell2mat(csvGroups.keys);
                    for csvIdx = csvIndices
                        if csvIdx <= numel(app.DataManager.DataTables) && ~isempty(app.DataManager.DataTables{csvIdx})
                            T = app.DataManager.DataTables{csvIdx};
                            signalsToExport = csvGroups(csvIdx);

                            % Create export table with Time and selected signals
                            exportTable = table();
                            exportTable.Time = T.Time;

                            for j = 1:numel(signalsToExport)
                                sigName = signalsToExport{j};
                                if ismember(sigName, T.Properties.VariableNames)
                                    exportTable.(sigName) = T.(sigName);
                                end
                            end

                            % Generate filename with bounds checking
                            if csvIdx <= numel(app.DataManager.CSVFilePaths) && ~isempty(app.DataManager.CSVFilePaths{csvIdx})
                                [~, originalName, ~] = fileparts(app.DataManager.CSVFilePaths{csvIdx});
                                fileName = sprintf('%s_filtered.csv', originalName);
                            else
                                fileName = sprintf('CSV_%d_filtered.csv', csvIdx);
                            end

                            fullPath = fullfile(exportSubfolder, fileName);
                            writetable(exportTable, fullPath);
                            exportedCount = exportedCount + 1;
                        end
                    end
                end

                % Export derived signals separately
                if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations)
                    for i = 1:numel(derivedSignals)
                        if i <= numel(derivedSignals) % BOUNDS CHECK
                            sigInfo = derivedSignals{i};
                            signalName = sigInfo.Signal;

                            % Get derived signal data
                            [timeData, signalData] = app.SignalOperations.getSignalData(signalName);

                            if ~isempty(timeData) && ~isempty(signalData)
                                % Create export table
                                exportTable = table(timeData, signalData, 'VariableNames', {'Time', signalName});

                                % Generate filename
                                fileName = sprintf('Derived_%s.csv', signalName);
                                fullPath = fullfile(exportSubfolder, fileName);
                                writetable(exportTable, fullPath);
                                exportedCount = exportedCount + 1;
                            end
                        end
                    end
                end

                % Update status
                if exportedCount > 0
                    app.StatusLabel.Text = sprintf('✅ Exported %d CSVs to %s', exportedCount, folderSuffix);
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];
                else
                    app.StatusLabel.Text = '⚠️ No valid signals to export';
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                end

            catch ME
                app.StatusLabel.Text = sprintf('❌ Export failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                fprintf('Error in exportSignalsToFolder: %s\n', ME.message);
            end

            app.restoreFocus();
        end

        function exportAllTabsAllSignals(obj)
            app = obj.App;

            % Export all signals from all CSVs
            allSignals = {};
            for i = 1:numel(app.DataManager.DataTables)
                if ~isempty(app.DataManager.DataTables{i})
                    signals = setdiff(app.DataManager.DataTables{i}.Properties.VariableNames, {'Time'});
                    for j = 1:numel(signals)
                        sigInfo = struct('CSVIdx', i, 'Signal', signals{j});
                        allSignals{end+1} = sigInfo;
                    end
                end
            end

            if isempty(allSignals)
                app.StatusLabel.Text = '⚠️ No signals available';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            obj.exportSignalsToFolder(allSignals, 'AllTabs_AllSignals');
        end

        % REMOVE THE DUPLICATE METHOD - Keep only the one inside exportAndClose nested function
        % The standalone exportAllCSVsAsIs method at line ~300 should be deleted as it's unreachable

        function showExportCSVDialog(obj)
            app = obj.App;

            % Check if there's any data to export
            if isempty(app.DataManager.DataTables) || all(cellfun(@isempty, app.DataManager.DataTables))
                app.StatusLabel.Text = '⚠️ No data to export';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Create export options dialog using traditional controls
            d = dialog('Name', 'CSV Export Options', 'Position', [300 300 450 480]);

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 440 410 25], ...
                'String', 'Select Export Scope:', 'FontSize', 12, 'FontWeight', 'bold');

            % Current selection info
            tabIdx = app.PlotManager.CurrentTabIdx;
            subplotIdx = app.PlotManager.SelectedSubplotIdx;
            infoText = sprintf('Current: Tab %d, Subplot %d', tabIdx, subplotIdx);
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 415 410 20], ...
                'String', infoText, 'FontSize', 10, 'HorizontalAlignment', 'center', ...
                'ForegroundColor', [0.2 0.6 0.9]);

            % Export option buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 360 410 35], ...
                'String', '📊 Current Subplot Only (signals in selected subplot)', ...
                'Callback', @(~,~) exportAndClose(1));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 320 410 35], ...
                'String', '📋 Current Tab - Active Subplots (subplots with signals)', ...
                'Callback', @(~,~) exportAndClose(2));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 280 410 35], ...
                'String', '📑 Current Tab - All Signals', ...
                'Callback', @(~,~) exportAndClose(3));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 240 410 35], ...
                'String', '📚 All Tabs - Active Subplots (subplots with signals)', ...
                'Callback', @(~,~) exportAndClose(4));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 200 410 35], ...
                'String', '🗂️ All Tabs - All Signals', ...
                'Callback', @(~,~) exportAndClose(5));

            % Save CSVs As-Is option
            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 160 410 35], ...
                'String', '💾 Save All CSVs As-Is (original loaded data)', ...
                'Callback', @(~,~) exportAndClose(6), ...
                'BackgroundColor', [0.9 0.95 1]);

            % Info text
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 125 410 25], ...
                'String', 'Filtered exports create new CSVs. "As-Is" saves original loaded data.', ...
                'FontSize', 10, 'HorizontalAlignment', 'center');

            % Cancel button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [350 20 80 30], 'Callback', @(~,~) close(d));

            % KEEP ONLY THIS VERSION - INSIDE THE NESTED FUNCTION
            function exportAllCSVsAsIs()
                % Ask user to select export folder
                exportFolder = uigetdir(pwd, 'Select Folder to Save All CSVs As-Is');
                if isequal(exportFolder, 0)
                    app.restoreFocus();
                    return;
                end

                try
                    % Create subfolder with timestamp
                    timestamp = datestr(now, 'yyyymmdd_HHMMSS');
                    exportSubfolder = fullfile(exportFolder, sprintf('CSV_AsIs_%s', timestamp));

                    if ~exist(exportSubfolder, 'dir')
                        mkdir(exportSubfolder);
                    end

                    exportedCount = 0;

                    % BOUNDS CHECK: Validate DataTables before access
                    if ~isempty(app.DataManager.DataTables)
                        for i = 1:numel(app.DataManager.DataTables)
                            if i <= numel(app.DataManager.DataTables) && ~isempty(app.DataManager.DataTables{i})
                                % Generate filename from original or generic
                                if i <= numel(app.DataManager.CSVFilePaths) && ~isempty(app.DataManager.CSVFilePaths{i})
                                    [~, originalName, ~] = fileparts(app.DataManager.CSVFilePaths{i});
                                    fileName = sprintf('%s.csv', originalName);
                                else
                                    fileName = sprintf('CSV_%d.csv', i);
                                end

                                fullPath = fullfile(exportSubfolder, fileName);

                                % Save the complete table as-is
                                writetable(app.DataManager.DataTables{i}, fullPath);
                                exportedCount = exportedCount + 1;
                            end
                        end
                    end

                    % Update status
                    if exportedCount > 0
                        app.StatusLabel.Text = sprintf('✅ Saved %d CSVs as-is', exportedCount);
                        app.StatusLabel.FontColor = [0.2 0.6 0.9];
                    else
                        app.StatusLabel.Text = '⚠️ No CSVs to save';
                        app.StatusLabel.FontColor = [0.9 0.6 0.2];
                    end

                catch ME
                    app.StatusLabel.Text = ['❌ Save failed: ' ME.message];
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                end

                app.restoreFocus();
            end

            function exportAndClose(option)
                try
                    % Call appropriate export function and close dialog
                    switch option
                        case 1
                            obj.exportCurrentSubplot();
                        case 2
                            obj.exportCurrentTabActiveSubplots();
                        case 3
                            obj.exportCurrentTabAllSignals();
                        case 4
                            obj.exportAllTabsActiveSubplots();
                        case 5
                            obj.exportAllTabsAllSignals();
                        case 6
                            exportAllCSVsAsIs();  % Call nested function
                    end
                    close(d);
                    app.restoreFocus();
                catch ME
                    fprintf('Error in exportAndClose: %s\n', ME.message);
                    app.StatusLabel.Text = sprintf('❌ Export failed: %s', ME.message);
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                end
            end
        end
        % Export the current data buffer to a CSV file
        function exportCSV(obj)
            % Show export options dialog instead of direct export
            obj.showExportCSVDialog();
        end

        % Show a dialog with statistics for all loaded signals
        function showStatsDialog(obj)
            app = obj.App;
            if isempty(app.DataManager.DataTables) || all(cellfun(@isempty, app.DataManager.DataTables))
                return;
            end
            fig = uifigure('Name', 'Signal Statistics', 'Position', [200 200 500 300]);
            tbl = uitable(fig, 'Position', [10 10 480 280]);
            stats = {};
            for i = 1:numel(app.DataManager.DataTables)
                T = app.DataManager.DataTables{i};
                if isempty(T), continue; end
                signals = setdiff(T.Properties.VariableNames, {'Time'});
                for j = 1:numel(signals)
                    s = signals{j};
                    d = T.(s);
                    d = d(~isnan(d));
                    stats{end+1, 1} = sprintf('%s (CSV %d)', s, i);
                    stats{end, 2} = numel(d);
                    stats{end, 3} = sprintf('%.3f', mean(d));
                    stats{end, 4} = sprintf('%.3f', std(d));
                    stats{end, 5} = sprintf('%.3f', min(d));
                    stats{end, 6} = sprintf('%.3f', max(d));
                end
            end
            tbl.Data = stats;
            tbl.ColumnName = {'Signal', 'Count', 'Mean', 'Std', 'Min', 'Max'};
        end

        function loadMultipleCSVs(obj)
            app = obj.App;
            [files, path] = uigetfile('*.csv', 'Select CSV Files', 'MultiSelect', 'on');
            if isequal(files,0)
                return;
            end
            if ischar(files)
                files = {files};
            end
            app.DataManager.CSVFilePaths = cellfun(@(f) fullfile(path, f), files, 'UniformOutput', false);
            app.DataManager.DataTables = cell(1, numel(files));
            app.DataManager.LastFileModTimes = cell(1, numel(files));
            app.DataManager.LastReadRows = cell(1, numel(files));
            app.DataManager.StreamingTimers = cell(1, numel(files));
            app.DataManager.LatestDataRates = cell(1, numel(files));
            
            % Check streaming mode and load accordingly
            if app.DataManager.StreamingEnabled
                app.DataManager.startStreamingAll();
            else
                app.DataManager.loadDataOnce();
            end
            
            app.buildSignalTree();
            app.PlotManager.refreshPlots();
        end
        function signalNames = getAllSignalsIncludingDerived(obj)
            % Get all available signals including derived ones
            signalNames = obj.App.DataManager.SignalNames;
            if isprop(obj.App, 'SignalOperations') && ~isempty(obj.App.SignalOperations.DerivedSignals)
                derivedNames = keys(obj.App.SignalOperations.DerivedSignals);
                signalNames = [signalNames, derivedNames];
            end
        end


    end
end