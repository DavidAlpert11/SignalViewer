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
            app.RowsSpinner.ValueChangedFcn = @(src, event) obj.onLayoutChanged();
            app.ColsSpinner.ValueChangedFcn = @(src, event) obj.onLayoutChanged();
            app.SubplotDropdown.ValueChangedFcn = @(src, event) obj.onSubplotSelected();
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

        % Clear all data, plots, and signal assignments in the app
        function clearAll(obj)
            app = obj.App;
            % Clear all subplot highlights
            for tabIdx = 1:numel(app.PlotManager.AxesArrays)
                app.clearSubplotHighlights(tabIdx);
            end
            for i = 1:numel(app.PlotManager.AxesArrays)
                if ~isempty(app.PlotManager.AxesArrays{i})
                    for ax = app.PlotManager.AxesArrays{i}
                        if isvalid(ax)
                            cla(ax);
                            legend(ax, 'off');
                        end
                    end
                    % Initialize AssignedSignals properly
                    nPlots = numel(app.PlotManager.AxesArrays{i});
                    app.PlotManager.AssignedSignals{i} = cell(nPlots, 1);
                    for j = 1:nPlots
                        app.PlotManager.AssignedSignals{i}{j} = {};
                    end
                end
            end
            % Clear all multi-CSV data
            app.DataManager.DataTables = {};
            app.DataManager.CSVFilePaths = {};
            app.DataManager.SignalNames = {};
            app.DataManager.SignalScaling = containers.Map();
            app.DataManager.StateSignals = containers.Map();
            app.StatusLabel.Text = 'Cleared';
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';
            app.DataManager.DataCount = 0;
            app.DataManager.UpdateCounter = 0;
            app.PlotManager.SelectedSubplotIdx = 1;
            app.PlotManager.refreshPlots();
        end

        % Export the current data buffer to a CSV file
        function exportCSV(obj)
            app = obj.App;
            if isempty(app.DataManager.DataTables) || all(cellfun(@isempty, app.DataManager.DataTables))
                uialert(app.UIFigure, 'No data to export.', 'Info');
                return;
            end
            [file, path] = uiputfile('*.csv', 'Export Data');
            if isequal(file, 0), return; end
            try
                % Export the first non-empty table
                for i = 1:numel(app.DataManager.DataTables)
                    if ~isempty(app.DataManager.DataTables{i})
                        writetable(app.DataManager.DataTables{i}, fullfile(path, file));
                        break;
                    end
                end
                uialert(app.UIFigure, 'Data exported successfully.', 'Success');
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
                    case 'r'
                        app.PlotManager.resetZoom();
                    case 't'
                        obj.showStatsDialog();
                end
            end
        end
    end
end