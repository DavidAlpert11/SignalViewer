classdef UIController < handle
    properties
        App
    end

    methods
        function obj = UIController(app)
            obj.App = app;
        end

        function setupCallbacks(obj)
            app = obj.App;

            % Spinner value change callbacks
            app.RowsSpinner.ValueChangedFcn = @(src, event) obj.onLayoutChanged();
            app.ColsSpinner.ValueChangedFcn = @(src, event) obj.onLayoutChanged();
            app.SubplotDropdown.ValueChangedFcn = @(src, event) obj.onSubplotSelected();
            app.SaveConfigButton.ButtonPushedFcn = @(src, event) app.ConfigManager.saveConfig();
            app.LoadConfigButton.ButtonPushedFcn = @(src, event) app.ConfigManager.loadConfig();

            % Signal table edit
            app.SignalTable.CellEditCallback = @(src, event) obj.onSignalTableEdit(event);

            % Button callbacks
            app.StartButton.ButtonPushedFcn = @(src, event) app.DataManager.startStreaming();
            app.StopButton.ButtonPushedFcn = @(src, event) app.DataManager.stopStreaming();
            app.ClearButton.ButtonPushedFcn = @(src, event) obj.clearAll();

            app.ExportButton.ButtonPushedFcn = @(src, event) obj.exportCSV();
            app.ExportPDFButton.ButtonPushedFcn = @(src, event) app.PlotManager.exportToPDF();
            app.StatsButton.ButtonPushedFcn = @(src, event) obj.showStatsDialog();
            app.ResetZoomButton.ButtonPushedFcn = @(src, event) app.PlotManager.resetZoom();

            % Keyboard shortcuts
            obj.setupKeyboardShortcuts();
        end

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
                obj.updateSignalCheckboxes();
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
                    obj.updateSignalTableVisualFeedback();

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
                    obj.updateSignalCheckboxes();
            end
        end

        function part = getLastPart(obj, s)
            parts = split(s, ':');
            part = strtrim(parts{end});
        end

        function updateSignalCheckboxes(obj)
            app = obj.App;
            if isempty(app.DataManager.SignalNames)
                app.SignalTable.Data = table({'(none)'}, {''}, {false}, {1.0}, {false}, ...
                    'VariableNames', {'Signal','Info','Plot','Scale','State'});
                return;
            end

            % Make sure subplot dropdown is updated
            obj.updateSubplotDropdown();

            shortNames = cellfun(@(s) strtrim(obj.getLastPart(s)), app.DataManager.SignalNames, 'UniformOutput', false);
            [sortedShort, sortIdx] = sort(shortNames);
            sortedFull = app.DataManager.SignalNames(sortIdx);

            n = numel(sortedFull);
            
            % Initialize all arrays with correct size
            Signal = cell(n, 1);      % Will be filled with visual indicators
            Info = cell(n, 1);        % Initialize as cell array
            Plot = false(n, 1);       % Changed from 'Selected' to 'Plot' to match table
            Scale = ones(n, 1);       % Numeric array
            State = false(n, 1);      % Logical array

            % Fill in the data
            for i = 1:n
                fullName = sortedFull{i};
                
                % Start with clean signal name
                Signal{i} = sortedShort{i};
                
                if ismember(fullName, app.DataManager.DataBuffer.Properties.VariableNames)
                    Info{i} = sprintf('(%dx1)', sum(~isnan(app.DataManager.DataBuffer.(fullName))));
                else
                    Info{i} = '';
                end
                if app.DataManager.SignalScaling.isKey(fullName)
                    Scale(i) = app.DataManager.SignalScaling(fullName);
                end
                if app.DataManager.StateSignals.isKey(fullName)
                    State(i) = app.DataManager.StateSignals(fullName);
                end
            end

            % Update Plot based on current subplot assignments
            currentTabIdx = app.PlotManager.CurrentTabIdx;
            selectedSubplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Check if indices are valid and update Plot accordingly
            if currentTabIdx <= numel(app.PlotManager.AssignedSignals) && ...
                    ~isempty(app.PlotManager.AssignedSignals{currentTabIdx}) && ...
                    selectedSubplotIdx <= numel(app.PlotManager.AssignedSignals{currentTabIdx})

                subplotSigs = app.PlotManager.AssignedSignals{currentTabIdx}{selectedSubplotIdx};

                % Ensure subplotSigs is a cell array
                if isempty(subplotSigs)
                    subplotSigs = {};
                elseif ~iscell(subplotSigs)
                    subplotSigs = {subplotSigs};
                end

                % Update Plot based on assigned signals - ensure column vector
                Plot = ismember(sortedFull, subplotSigs);
                Plot = Plot(:);  % Force column vector
            end

            % Add visual indicators to signal names
            for i = 1:n
                if Plot(i)
                    Signal{i} = sprintf('● %s', sortedShort{i});
                else
                    Signal{i} = sprintf('○ %s', sortedShort{i});
                end
            end

            % Create the table with consistent data types
            app.SignalTable.Data = table(Signal, Info, Plot, Scale, State, ...
                'VariableNames', {'Signal','Info','Plot','Scale','State'});
        end

        function updateSignalTableVisualFeedback(obj)
            % Update visual feedback in the signal table
            obj.updateSignalCheckboxes();
        end

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

            app.DataManager.DataBuffer = table();
            app.DataManager.SignalNames = {};
            app.DataManager.SignalScaling = containers.Map();
            app.DataManager.StateSignals = containers.Map();
            obj.updateSignalCheckboxes();

            app.StatusLabel.Text = 'Cleared';
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';
            app.DataManager.DataCount = 0;
            app.DataManager.UpdateCounter = 0;

            app.PlotManager.SelectedSubplotIdx = 1;
            app.PlotManager.refreshPlots();
        end

        function exportCSV(obj)
            app = obj.App;
            if isempty(app.DataManager.DataBuffer)
                uialert(app.UIFigure, 'No data to export.', 'Info');
                return;
            end
            [file, path] = uiputfile('*.csv', 'Export Data');
            if isequal(file, 0), return; end
            try
                writetable(app.DataManager.DataBuffer, fullfile(path, file));
                uialert(app.UIFigure, 'Data exported successfully.', 'Success');
            catch ME
                uialert(app.UIFigure, ['Export failed: ' ME.message], 'Error');
            end
        end

        function showStatsDialog(obj)
            app = obj.App;
            if isempty(app.DataManager.DataBuffer)
                return;
            end

            fig = uifigure('Name', 'Signal Statistics', 'Position', [200 200 400 300]);
            tbl = uitable(fig, 'Position', [10 10 380 280]);

            names = app.DataManager.SignalNames;
            stats = cell(numel(names), 6);

            for i = 1:numel(names)
                s = names{i};
                stats{i, 1} = s;
                if ismember(s, app.DataManager.DataBuffer.Properties.VariableNames)
                    d = app.DataManager.DataBuffer.(s);
                    d = d(~isnan(d));
                    stats{i, 2} = numel(d);
                    stats{i, 3} = sprintf('%.3f', mean(d));
                    stats{i, 4} = sprintf('%.3f', std(d));
                    stats{i, 5} = sprintf('%.3f', min(d));
                    stats{i, 6} = sprintf('%.3f', max(d));
                else
                    stats(i, 2:end) = {'-', '-', '-', '-', '-'};
                end
            end

            tbl.Data = stats;
            tbl.ColumnName = {'Signal', 'Count', 'Mean', 'Std', 'Min', 'Max'};
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