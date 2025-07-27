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

        % Set up all UI callbacks for the app controls
        function setupCallbacks(obj)
            app = obj.App;
            % Spinner value change callbacks
            app.SaveConfigButton.ButtonPushedFcn = @(src, event) app.ConfigManager.saveConfig();
            app.LoadConfigButton.ButtonPushedFcn = @(src, event) app.ConfigManager.loadConfig();

            % (No longer set ValueChangedFcn for CSVPathField)

            % Keyboard shortcuts
            obj.setupKeyboardShortcuts();
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
            [files, path] = uigetfile('*.csv', 'Add More CSV Files', 'MultiSelect', 'on');
            if isequal(files,0)
                return;
            end
            if ischar(files)
                files = {files};
            end

            % Get new file paths
            newCSVPaths = cellfun(@(f) fullfile(path, f), files, 'UniformOutput', false);

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

            % Start streaming for the new CSVs only
            for i = 1:numNewCSVs
                csvIdx = existingCount + i;
                app.DataManager.startStreamingForCSV(csvIdx);
            end

            % Update signal tree to include new signals
            app.buildSignalTree();

            % Update status
            app.StatusLabel.Text = sprintf('➕ Added %d new CSV(s). Total: %d', numNewCSVs, numel(app.DataManager.CSVFilePaths));
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
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

        function part = getLastPart(obj, s)
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

            % Reset selected subplot
            app.PlotManager.SelectedSubplotIdx = 1;

            % Update status
            app.StatusLabel.Text = '🗑️ Plots cleared (CSVs still loaded)';
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
            app.StatusLabel.Text = '🗑️ Everything cleared';
            app.StatusLabel.FontColor = [0.5 0.5 0.5];
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';
            app.StreamingInfoLabel.Text = '';

            % Refresh to show empty state
            app.PlotManager.refreshPlots();

            % Highlight the first subplot
            app.highlightSelectedSubplot(app.PlotManager.CurrentTabIdx, 1);
        end

        % Export the current data buffer to a CSV file
        function exportCSV(obj)
            app = obj.App;
            if isempty(app.DataManager.DataTables) || all(cellfun(@isempty, app.DataManager.DataTables))
                uialert(app.UIFigure, 'No data to export.', 'Info');
                return;
            end

            % Ask user to select export folder
            exportFolder = uigetdir(pwd, 'Select Folder to Export All CSVs');
            if isequal(exportFolder, 0)
                return;
            end

            try
                exportedCount = 0;
                exportedFiles = {};

                % Export each non-empty CSV table
                for i = 1:numel(app.DataManager.DataTables)
                    if ~isempty(app.DataManager.DataTables{i})
                        % Generate filename
                        if i <= numel(app.DataManager.CSVFilePaths) && ~isempty(app.DataManager.CSVFilePaths{i})
                            % Use original filename if available
                            [~, originalName, ~] = fileparts(app.DataManager.CSVFilePaths{i});
                            fileName = sprintf('%s.csv', originalName);
                        else
                            % Generate generic name
                            fileName = sprintf('CSV_%d.csv', i);
                        end

                        fullPath = fullfile(exportFolder, fileName);

                        % Export the table
                        writetable(app.DataManager.DataTables{i}, fullPath);

                        exportedCount = exportedCount + 1;
                        exportedFiles{end+1} = fileName;
                    end
                end

                % Show success message with details
                if exportedCount > 0
                    fileList = strjoin(exportedFiles, '\n• ');
                    successMsg = sprintf('Successfully exported %d CSV files to:\n%s\n\nFiles:\n• %s', ...
                        exportedCount, exportFolder, fileList);

                    uialert(app.UIFigure, successMsg, 'Export Complete', 'Icon', 'success');

                    % Update status
                    app.StatusLabel.Text = sprintf('📁 Exported %d CSVs to folder', exportedCount);
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];

                    % Ask if user wants to open the folder
                    answer = uiconfirm(app.UIFigure, ...
                        'Would you like to open the export folder?', ...
                        'Open Folder?', ...
                        'Options', {'Yes', 'No'}, ...
                        'DefaultOption', 'Yes');
                    figure(app.UIFigure); % Force focus back to main window

                    if strcmp(answer, 'Yes')
                        try
                            if ispc
                                winopen(exportFolder);
                            elseif ismac
                                system(['open "' exportFolder '"']);
                            else
                                system(['xdg-open "' exportFolder '"']);
                            end
                        catch
                            % If opening fails, just continue
                        end
                    end
                else
                    uialert(app.UIFigure, 'No data tables found to export.', 'No Data');
                end

            catch ME
                uialert(app.UIFigure, ['Export failed: ' ME.message], 'Error');
            end
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
            app.DataManager.startStreamingAll();
            app.buildSignalTree();
        end

        function setupKeyboardShortcuts(obj)
            app = obj.App;
            app.UIFigure.KeyPressFcn = @(src, event) obj.keyPressHandler(event);
        end

        function keyPressHandler(obj, event)
            app = obj.App;
            if isempty(event.Modifier), return; end
            if ismember('control', event.Modifier)
                switch event.Key
                    case 's'
                        if ~app.DataManager.IsRunning
                            app.DataManager.startStreaming();
                        end
                    case 'x'
                        if app.DataManager.IsRunning
                            app.DataManager.stopStreaming();
                        end
                    case 'c'
                        obj.clearAll();
                    case 'e'
                        obj.exportCSV();
                    case 'p'
                        app.PlotManager.exportToPDF();
                    case 't'
                        obj.showStatsDialog();
                    case 'd'  % NEW: Ctrl+D for cursor mode
                        app.menuToggleCursor();
                end
            end
        end
    end
end