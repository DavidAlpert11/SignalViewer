classdef SignalViewer < matlab.apps.AppBase

    properties (Access = public)
        UIFigure             matlab.ui.Figure
        MainTabGroup         matlab.ui.container.TabGroup
        ControlPanel         matlab.ui.container.Panel
        StartButton          matlab.ui.control.Button
        StopButton           matlab.ui.control.Button
        ClearButton          matlab.ui.control.Button
        StatusLabel          matlab.ui.control.Label
        DataRateLabel        matlab.ui.control.Label
        CSVLabel             matlab.ui.control.Label
        CSVPathField         matlab.ui.control.EditField
        BrowseButton         matlab.ui.control.Button
        SignalTable          matlab.ui.control.Table
        RowsSpinner          matlab.ui.control.Spinner
        ColsSpinner          matlab.ui.control.Spinner
        ExportButton         matlab.ui.control.Button
        SaveConfigButton     matlab.ui.control.Button
        LoadConfigButton     matlab.ui.control.Button
        AutoScaleCheckbox    matlab.ui.control.CheckBox
        RowsLabel            matlab.ui.control.Label
        ColsLabel            matlab.ui.control.Label
        ExportPDFButton      matlab.ui.control.Button  % <<== ADD THIS LINE
        StatsButton          matlab.ui.control.Button  % <<== if you also added StatsButton
        ResetZoomButton      matlab.ui.control.Button  % <<== if you also added ResetZoomButton
        SaveTemplateButton   matlab.ui.control.Button
        LoadTemplateButton   matlab.ui.control.Button
    end


    properties (Access = private)
        PlotTabs             cell           % Array of tab handles
        GridLayouts          cell           % Array of grid layouts for each tab
        AxesArrays           cell           % Cell array of axes arrays for each tab
        Timer
        IsRunning            logical = false
        Colors               double
        NumColumns           double
        FID                  double = -1
        LastDataTimestamp    uint64
        SignalNames          cell
        AssignedSignals      cell           % Cell array for each tab
        DataBuffer           table
        SelectedSubplotIdx   double = 1
        CurrentTabIdx        double = 1
        DataRate             double = 0
        LastUpdateTime       datetime
        DataCount            double = 0
        UpdateCounter        double = 0
        ConfigFile           char = 'signal_viewer_config.mat'
        SignalScaling        containers.Map  % Map for signal scaling factors
        ScalingDialog        matlab.ui.Figure
        TabCounter           double = 1
        LinkedAxes           matlab.graphics.axis.Axes  % For linking axes
        TabLayouts    cell  % Store [rows, cols] for each tab
        StateSignals         containers.Map  % Map to track which signals are state type
        CSVFiles   struct   % Store metadata about multiple CSV files
    end

    methods (Access = private)

        function startupFcn(app)
            app.StatusLabel.Text = 'Ready';
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';
            app.StopButton.Enable = false;
            app.Colors = lines(20);
            app.LastUpdateTime = datetime('now');
            app.SignalScaling = containers.Map();
            app.StateSignals = containers.Map();  % ADD THIS LINE
            app.TabLayouts = {};
            app.createFirstTab();
            app.setupKeyboardShortcuts();
            app.LinkedAxes = matlab.graphics.axis.Axes.empty;
            app.createPlusTab();
            app.loadLastCSVPath();
            app.createSignalFilter();
        end

        function createPlusTab(app)
            plusTab = uitab(app.MainTabGroup, 'Title', '+');
            app.PlotTabs{end+1} = plusTab;

            % Force + tab to be at the end (rightmost position)
            app.MainTabGroup.Children = [app.MainTabGroup.Children(1:end-1); plusTab];
        end

        function createFirstTab(app)
            % Create the first tab
            tab = uitab(app.MainTabGroup, 'Title', 'Tab 1');
            app.PlotTabs{1} = tab;
            app.GridLayouts{1} = uigridlayout(tab, [2, 1]);
            app.AxesArrays{1} = matlab.ui.control.UIAxes.empty;
            app.AssignedSignals{1} = cell(2,1);
            app.createSubplotsForTab(1, 2, 1);
            app.CurrentTabIdx = 1;
        end

        function createSubplotsForTab(app, tabIdx, rows, cols)
            % Ensure TabLayouts cell array is large enough
            while numel(app.TabLayouts) < tabIdx
                app.TabLayouts{end+1} = [];
            end

            tabMenu = uicontextmenu(app.UIFigure);
            uimenu(tabMenu, 'Text', 'Close Tab', 'MenuSelectedFcn', @(~,~)app.closeTab(tabIdx));
            app.PlotTabs{tabIdx}.ContextMenu = tabMenu;

            % Keep the previous assignments
            prevAssignments = {};
            if numel(app.AssignedSignals) >= tabIdx && ~isempty(app.AssignedSignals{tabIdx})
                prevAssignments = app.AssignedSignals{tabIdx};
            end

            % Clear existing axes
            if ~isempty(app.AxesArrays{tabIdx})
                % Remove from linked axes before deleting
                for ax = app.AxesArrays{tabIdx}
                    if isvalid(ax)
                        app.LinkedAxes(app.LinkedAxes == ax) = [];
                    end
                end
                delete(app.AxesArrays{tabIdx});
            end

            % Store new layout
            app.TabLayouts{tabIdx} = [rows, cols];

            % Create new grid
            delete(app.GridLayouts{tabIdx});
            app.GridLayouts{tabIdx} = uigridlayout(app.PlotTabs{tabIdx}, [rows, cols]);
            app.AxesArrays{tabIdx} = matlab.ui.control.UIAxes.empty;

            nPlots = rows * cols;

            % Initialize empty assignments
            app.AssignedSignals{tabIdx} = cell(nPlots, 1);

            % Restore previous assignments as much as possible
            nCopy = min(nPlots, numel(prevAssignments));
            for i = 1:nCopy
                app.AssignedSignals{tabIdx}{i} = prevAssignments{i};
            end

            % Create new axes
            for i = 1:nPlots
                ax = uiaxes(app.GridLayouts{tabIdx});
                ax.Title.String = sprintf('Plot %d', i);
                ax.XLabel.String = 'Time';
                ax.YLabel.String = 'Value';
                grid(ax, 'on');
                hold(ax, 'on');
                ax.ButtonDownFcn = @(~,~)app.selectSubplot(i);
                app.AxesArrays{tabIdx}(i) = ax;

                % Add to linked axes
                app.LinkedAxes(end+1) = ax;

                % Context menu for each subplot
                plotMenu = uicontextmenu(app.UIFigure);
                uimenu(plotMenu, 'Text', 'Auto Scale', 'MenuSelectedFcn', @(~,~)app.autoScaleSubplot(i));
                uimenu(plotMenu, 'Text', 'Clear This Plot', 'MenuSelectedFcn', @(~,~)app.clearSubplot(i));
                ax.ContextMenu = plotMenu;
            end

            % Link axes
            if numel(app.LinkedAxes) > 1
                linkaxes(app.LinkedAxes, 'x');
            end

            app.SelectedSubplotIdx = 1;
            app.highlightSelected();

            % Update spinners to reflect the new layout
            if tabIdx == app.CurrentTabIdx
                app.updateSpinnersForCurrentTab();
            end
        end

        function validateDataIntegrity(app)
            if isempty(app.DataBuffer)
                return;
            end

            % Check for data corruption
            try
                % Verify all expected columns exist
                expectedCols = [{'Time'}, app.SignalNames];
                actualCols = app.DataBuffer.Properties.VariableNames;

                missingCols = setdiff(expectedCols, actualCols);
                if ~isempty(missingCols)
                    warning('Missing columns detected: %s', strjoin(missingCols, ', '));
                end

                % Check for infinite values
                for i = 1:numel(app.SignalNames)
                    signalName = app.SignalNames{i};
                    if ismember(signalName, actualCols)
                        data = app.DataBuffer.(signalName);
                        if any(isinf(data))
                            warning('Infinite values detected in signal: %s', signalName);
                        end
                    end
                end

            catch ME
                warning('Data validation failed: %s', ME.message);
            end
        end
        function RowsSpinnerValueChanged(app, event)
            rows = max(1, min(10, round(app.RowsSpinner.Value)));
            cols = max(1, min(10, round(app.ColsSpinner.Value)));

            % Update the layout for the current tab
            app.createSubplotsForTab(app.CurrentTabIdx, rows, cols);
            app.refreshPlots(app.CurrentTabIdx);
        end

        % Replace your existing ColsSpinnerValueChanged method:
        function ColsSpinnerValueChanged(app, event)
            rows = max(1, min(10, round(app.RowsSpinner.Value)));
            cols = max(1, min(10, round(app.ColsSpinner.Value)));

            % Update the layout for the current tab
            app.createSubplotsForTab(app.CurrentTabIdx, rows, cols);
            app.refreshPlots(app.CurrentTabIdx);
        end

        function closeTab(app, tabIdx)
            if strcmp(app.PlotTabs{tabIdx}.Title, '+')
                return;
            end

            % Count data tabs
            titlesAll = cellfun(@(t) t.Title, app.PlotTabs, 'UniformOutput', false);
            dataTabsCount = sum(~strcmp(titlesAll, '+'));
            if dataTabsCount <= 1
                return;
            end

            % Remove axes from linked axes
            if ~isempty(app.AxesArrays{tabIdx})
                for ax = app.AxesArrays{tabIdx}
                    if isvalid(ax)
                        app.LinkedAxes(app.LinkedAxes == ax) = [];
                    end
                end
            end

            % Delete
            delete(app.PlotTabs{tabIdx});
            app.PlotTabs(tabIdx) = [];
            app.GridLayouts(tabIdx) = [];
            app.AxesArrays(tabIdx) = [];
            app.AssignedSignals(tabIdx) = [];

            if app.CurrentTabIdx >= tabIdx
                app.CurrentTabIdx = max(1, app.CurrentTabIdx - 1);
            end

            % Reorder tabs: data tabs first, then + tab at the end
            allTabs = app.MainTabGroup.Children;
            plusTab = allTabs(strcmp({allTabs.Title}, '+'));
            dataTabs = allTabs(~strcmp({allTabs.Title}, '+'));

            % Put + tab at the end
            app.MainTabGroup.Children = [dataTabs; plusTab];

            app.SelectedSubplotIdx = 1;
            app.highlightSelected();
            app.updateSignalCheckboxes();
            app.updateSpinnersForCurrentTab();
        end
        % Add this new method to update spinners when tab changes
        function updateSpinnersForCurrentTab(app)
            if app.CurrentTabIdx <= numel(app.TabLayouts) && ~isempty(app.TabLayouts{app.CurrentTabIdx})
                layout = app.TabLayouts{app.CurrentTabIdx};
                app.RowsSpinner.Value = layout(1);
                app.ColsSpinner.Value = layout(2);
            else
                % Default values if no layout stored
                app.RowsSpinner.Value = 2;
                app.ColsSpinner.Value = 1;
            end
        end

        function tabChanged(app, event)
            selectedTab = event.NewValue;

            if strcmp(selectedTab.Title, '+')
                % User clicked "+"
                app.TabCounter = app.TabCounter + 1;

                % Create new tab
                newTab = uitab(app.MainTabGroup, 'Title', sprintf('Tab %d', app.TabCounter));

                % Add to tracking arrays (insert before the + tab)
                tabIdx = numel(app.PlotTabs);
                app.PlotTabs{tabIdx} = newTab;
                app.GridLayouts{tabIdx} = uigridlayout(newTab, [2, 1]);
                app.AxesArrays{tabIdx} = matlab.ui.control.UIAxes.empty;
                app.AssignedSignals{tabIdx} = cell(2, 1);
                app.createSubplotsForTab(tabIdx, 2, 1);

                % Reorder tabs: data tabs first, then + tab at the end
                allTabs = app.MainTabGroup.Children;
                plusTab = allTabs(strcmp({allTabs.Title}, '+'));
                dataTabs = allTabs(~strcmp({allTabs.Title}, '+'));

                % Put + tab at the end
                app.MainTabGroup.Children = [dataTabs; plusTab];

                % Select the new tab
                app.MainTabGroup.SelectedTab = newTab;
                app.CurrentTabIdx = tabIdx;
                app.SelectedSubplotIdx = 1;
                app.updateSignalCheckboxes();

            else
                % Normal tab selection
                for i = 1:numel(app.PlotTabs)
                    if app.PlotTabs{i} == selectedTab
                        app.CurrentTabIdx = i;
                        break;
                    end
                end
                app.SelectedSubplotIdx = 1;
                app.highlightSelected();
                app.updateSignalCheckboxes();
            end

            app.updateSpinnersForCurrentTab();
        end


        function setupKeyboardShortcuts(app)
            app.UIFigure.KeyPressFcn = @(src, event) app.keyPressCallback(event);
        end

        function keyPressCallback(app, event)
            if isempty(event.Modifier)
                return;
            end

            if ismember('control', event.Modifier)
                switch event.Key
                    case 's'
                        if ~app.IsRunning
                            app.StartButtonPushed();
                        end
                    case 'x'
                        if app.IsRunning
                            app.StopButtonPushed();
                        end
                    case 'c'
                        app.ClearButtonPushed();
                    case 'e'
                        app.ExportButtonPushed();
                    case 'p'  % PDF Export
                        app.ExportToPDFButtonPushed();
                    case 'r'  % Reset Zoom
                        app.resetZoom();
                    case 't'  % Show Statistics
                        app.showSignalStats();
                    case 'f'  % Focus on search (if implemented)
                        % Focus search field

                end
            end
        end

        function selectSubplot(app, idx)
            app.SelectedSubplotIdx = idx;
            app.highlightSelected();
            app.updateSignalCheckboxes();
        end

        function highlightSelected(app)
            if app.CurrentTabIdx > numel(app.AxesArrays) || isempty(app.AxesArrays{app.CurrentTabIdx})
                return;
            end

            axes = app.AxesArrays{app.CurrentTabIdx};
            for k = 1:numel(axes)
                if k == app.SelectedSubplotIdx
                    axes(k).Box = 'on';
                    axes(k).LineWidth = 2;
                    axes(k).BoxStyle = 'full';
                else
                    axes(k).Box = 'off';
                    axes(k).LineWidth = 0.5;
                end
            end
        end

        function autoScaleSubplot(app, idx)
            if app.CurrentTabIdx <= numel(app.AxesArrays) && ...
                    idx <= numel(app.AxesArrays{app.CurrentTabIdx})
                axis(app.AxesArrays{app.CurrentTabIdx}(idx), 'tight');
            end
        end

        function clearSubplot(app, idx)
            if app.CurrentTabIdx <= numel(app.AxesArrays) && ...
                    idx <= numel(app.AxesArrays{app.CurrentTabIdx})
                cla(app.AxesArrays{app.CurrentTabIdx}(idx));
                legend(app.AxesArrays{app.CurrentTabIdx}(idx), 'off');
                app.AssignedSignals{app.CurrentTabIdx}{idx} = {};
                if idx == app.SelectedSubplotIdx
                    app.updateSignalCheckboxes();
                end
            end
        end
        function updateSignalCheckboxes(app)
            if isempty(app.SignalNames)
                app.SignalTable.Data = table({'(none)'}, {''}, {false}, {1.0}, {false}, ...
                    'VariableNames', {'Signal','Info','Selected','Scale','State'});
                return;
            end

            % Sort names alphabetically (based on short names)
            allShortNames = cellfun(@(s) split(s, ':'), app.SignalNames, 'UniformOutput', false);
            shortNames = cellfun(@(c) strtrim(c{end}), allShortNames, 'UniformOutput', false);
            [sortedShort, sortIdx] = sort(shortNames);
            sortedFull = app.SignalNames(sortIdx);

            n = numel(sortedFull);
            Signal = sortedShort(:);
            Info = strings(n,1);
            Selected = false(n,1);
            Scale = ones(n,1);
            State = false(n,1);

            for i = 1:n
                fullName = sortedFull{i};

                count = 0;
                if ~isempty(app.DataBuffer) && ismember(fullName, app.DataBuffer.Properties.VariableNames)
                    count = sum(~isnan(app.DataBuffer.(fullName)));
                end
                Info(i) = sprintf('(%dx1)', count);

                if app.SignalScaling.isKey(fullName)
                    Scale(i) = app.SignalScaling(fullName);
                else
                    app.SignalScaling(fullName) = 1.0;
                    Scale(i) = 1.0;
                end

                if app.StateSignals.isKey(fullName)
                    State(i) = app.StateSignals(fullName);
                else
                    app.StateSignals(fullName) = false;
                    State(i) = false;
                end
            end

            if app.CurrentTabIdx <= numel(app.AssignedSignals) && ...
                    app.SelectedSubplotIdx <= numel(app.AssignedSignals{app.CurrentTabIdx}) && ...
                    ~isempty(app.AssignedSignals{app.CurrentTabIdx}{app.SelectedSubplotIdx})
                sel = app.AssignedSignals{app.CurrentTabIdx}{app.SelectedSubplotIdx};
                Selected = ismember(sortedFull, sel);
            end

            app.SignalTable.Data = table(Signal, Info, Selected, Scale, State, ...
                'VariableNames', {'Signal','Info','Selected','Scale','State'});

            % Debug
            fprintf('Signal list updated with %d signals.\n', n);
        end

        function isValid = validateCSVFile(app, csvFile)
            isValid = false;

            if ~isfile(csvFile)
                uialert(app.UIFigure, 'CSV file not found.', 'Error');
                return;
            end

            try
                fid = fopen(csvFile, 'r');
                if fid == -1
                    uialert(app.UIFigure, 'Cannot open CSV file.', 'Error');
                    return;
                end

                headerLine = fgetl(fid);
                fclose(fid);

                if isempty(headerLine) || ~contains(headerLine, ',')
                    uialert(app.UIFigure, 'Invalid CSV format. File must contain comma-separated headers.', 'Error');
                    return;
                end

                isValid = true;
            catch ME
                uialert(app.UIFigure, ['Error reading CSV file: ' ME.message], 'Error');
            end
        end

        function BrowseButtonPushed(app,event)
            [files, path] = uigetfile('*.csv', 'Select CSV Files', 'MultiSelect', 'on');
            if isequal(files,0)
                return;
            end
            if ~iscell(files)
                files = {files};
            end

            csvPaths = fullfile(path, files);

            % Store as semicolon-separated list
            app.CSVPathField.Value = strjoin(csvPaths, ';');

            % Auto-save
            app.autoSaveCSVPath();
        end


        function StartButtonPushed(app, event)
            if app.IsRunning
                return;
            end

            csvPaths = strsplit(app.CSVPathField.Value, ';');
            csvPaths = strtrim(csvPaths);

            % Validate all CSVs
            for k = 1:numel(csvPaths)
                if ~app.validateCSVFile(csvPaths{k})
                    return;
                end
            end

            app.SignalNames = {};
            mergedT = table();

            % Load all CSVs
            for k = 1:numel(csvPaths)
                fid = fopen(csvPaths{k}, 'r');
                if fid == -1
                    uialert(app.UIFigure, ['Cannot open file: ' csvPaths{k}], 'Error');
                    return;
                end

                headerLine = fgetl(fid);
                headers = strsplit(strtrim(headerLine), ',');
                signalNames = headers(2:end);

                block = textscan(fid, repmat('%f',1,numel(headers)), 'Delimiter', ',', 'CollectOutput', true);
                fclose(fid);

                if ~isempty(block{1})
                    T = array2table(block{1}, 'VariableNames', [{'Time'}, signalNames]);
                else
                    T = table();
                end

                % Prefix signal names with file index
                prefixedNames = strcat("f", string(k), ":", signalNames);

                if ~isempty(T)
                    T.Properties.VariableNames = [{'Time'}, prefixedNames];
                end

                % Append signal names
                app.SignalNames = [app.SignalNames, cellstr(prefixedNames)];

                % Merge into mergedT
                if isempty(mergedT)
                    mergedT = T;
                else
                    mergedT = outerjoin(mergedT, T, 'Keys', 'Time', 'MergeKeys', true);
                end
            end

            % Save merged table
            app.DataBuffer = mergedT;

            % Initialize scaling and state
            for i = 1:numel(app.SignalNames)
                if ~app.SignalScaling.isKey(app.SignalNames{i})
                    app.SignalScaling(app.SignalNames{i}) = 1.0;
                end
                if ~app.StateSignals.isKey(app.SignalNames{i})
                    app.StateSignals(app.SignalNames{i}) = false;
                end
            end

            app.updateSignalCheckboxes();

            % Start streaming
            app.IsRunning = true;
            app.StartButton.Enable = false;
            app.StopButton.Enable = true;
            app.StatusLabel.Text = 'Loaded.';
            app.DataRateLabel.Text = 'Data Rate: N/A';
            app.DataCount = height(app.DataBuffer);
            app.UpdateCounter = 0;

            app.refreshPlots();
        end


        function StopButtonPushed(app,event)
            if ~app.IsRunning, return; end

            app.IsRunning = false;
            app.StartButton.Enable = true;
            app.StopButton.Enable = false;
            app.StatusLabel.Text = 'Stopped';
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';

            if ~isempty(app.Timer) && isvalid(app.Timer)
                stop(app.Timer);
                delete(app.Timer);
                app.Timer = [];
            end

            if app.FID ~= -1
                fclose(app.FID);
                app.FID = -1;
            end
        end

        function ClearButtonPushed(app,event)
            % Clear all plots in all tabs
            for tabIdx = 1:numel(app.AxesArrays)
                if ~isempty(app.AxesArrays{tabIdx})
                    for ax = app.AxesArrays{tabIdx}
                        cla(ax);
                        legend(ax,'off');
                    end
                    % Properly reset assignments for each subplot
                    app.AssignedSignals{tabIdx} = cell(numel(app.AxesArrays{tabIdx}), 1);
                end
            end

            % Reset data
            app.DataBuffer = table();
            app.SignalNames = {};
            app.SignalScaling = containers.Map();
            app.SignalTable.Data = table({'(none)'}, {''}, {false}, {1.0}, {false}, ...
                'VariableNames', {'Signal','Info','Selected','Scale','State'});
            app.StatusLabel.Text = 'Cleared';
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';
            app.DataCount = 0;
            app.UpdateCounter = 0;

            % Reset selection state and highlight
            app.SelectedSubplotIdx = 1;
            app.highlightSelected();
        end

        function timerCallback(app)
            if ~app.IsRunning || app.FID == -1
                return;
            end

            % Read new data
            block = textscan(app.FID, repmat('%f',1,app.NumColumns),'Delimiter',',','CollectOutput',true);

            if ~isempty(block{1})
                % Add new data to buffer
                newRows = array2table(block{1},'VariableNames',[{'Time'},app.SignalNames]);
                app.DataBuffer = [app.DataBuffer; newRows];

                % Update statistics
                app.DataCount = app.DataCount + height(newRows);
                app.UpdateCounter = app.UpdateCounter + 1;
                app.LastDataTimestamp = tic;

                % Calculate data rate every 10 updates
                if mod(app.UpdateCounter, 10) == 0
                    currentTime = datetime('now');
                    timeDiff = seconds(currentTime - app.LastUpdateTime);
                    if timeDiff > 0
                        app.DataRate = 10 / timeDiff;
                        app.DataRateLabel.Text = sprintf('Data Rate: %.1f Hz', app.DataRate);
                        app.LastUpdateTime = currentTime;
                    end
                end

                % Update displays
                app.updateSignalCheckboxes();
                app.refreshPlots();

            else
                % No new data - check for timeout
                if isempty(app.LastDataTimestamp)
                    app.LastDataTimestamp = tic;
                elseif toc(app.LastDataTimestamp) > 2
                    app.StatusLabel.Text = 'No new data - stopping...';
                    app.StopButtonPushed();
                end
            end
        end

        function createComponents(app)
            % Create UIFigure
            app.UIFigure = uifigure('Visible', 'off');
            app.UIFigure.AutoResizeChildren = 'off';
            app.UIFigure.Position = [100 100 1200 800];
            app.UIFigure.Name = 'Signal Viewer';
            app.UIFigure.Resize = 'off';

            % Create MainTabGroup
            app.MainTabGroup = uitabgroup(app.UIFigure);
            app.MainTabGroup.Position = [320 1 880 799];
            app.MainTabGroup.SelectionChangedFcn = createCallbackFcn(app, @tabChanged, true);

            % Create ControlPanel
            app.ControlPanel = uipanel(app.UIFigure);
            app.ControlPanel.Position = [1 1 318 799];
            app.ControlPanel.Title = 'Control Panel';

            % Replace your existing button creation with this:

            app.StartButton = uibutton(app.ControlPanel, 'push');
            app.StartButton.ButtonPushedFcn = createCallbackFcn(app, @StartButtonPushed, true);
            app.StartButton.Position = [20 740 80 30];
            app.StartButton.Text = 'Start';
            app.StartButton.BackgroundColor = [0.2 0.8 0.2]; % Green
            app.StartButton.FontColor = [1 1 1]; % White text

            app.StopButton = uibutton(app.ControlPanel, 'push');
            app.StopButton.ButtonPushedFcn = createCallbackFcn(app, @StopButtonPushed, true);
            app.StopButton.Position = [110 740 80 30];
            app.StopButton.Text = 'Stop';
            app.StopButton.BackgroundColor = [0.8 0.2 0.2]; % Red
            app.StopButton.FontColor = [1 1 1]; % White text

            app.ClearButton = uibutton(app.ControlPanel, 'push');
            app.ClearButton.ButtonPushedFcn = createCallbackFcn(app, @ClearButtonPushed, true);
            app.ClearButton.Position = [200 740 80 30];
            app.ClearButton.Text = 'Clear';
            app.ClearButton.BackgroundColor = [0.8 0.6 0.2]; % Orange
            app.ClearButton.FontColor = [1 1 1]; % White text

            % Status labels
            app.StatusLabel = uilabel(app.ControlPanel);
            app.StatusLabel.Position = [20 720 260 20];
            app.StatusLabel.Text = 'Ready';

            app.DataRateLabel = uilabel(app.ControlPanel);
            app.DataRateLabel.Position = [20 700 260 20];
            app.DataRateLabel.Text = 'Data Rate: 0 Hz';

            % CSV file selection
            app.CSVLabel = uilabel(app.ControlPanel);
            app.CSVLabel.Position = [20 670 100 20];
            app.CSVLabel.Text = 'CSV File:';

            app.CSVPathField = uieditfield(app.ControlPanel, 'text');
            app.CSVPathField.Position = [20 650 200 20];
            app.CSVPathField.Value = '';
            % ADD THIS LINE - auto-save when user types in the field
            app.CSVPathField.ValueChangedFcn = createCallbackFcn(app, @CSVPathFieldValueChanged, true);

            app.BrowseButton = uibutton(app.ControlPanel, 'push');
            app.BrowseButton.ButtonPushedFcn = createCallbackFcn(app, @BrowseButtonPushed, true);
            app.BrowseButton.Position = [230 650 60 20];
            app.BrowseButton.Text = 'Browse';

            % Layout controls
            app.RowsLabel = uilabel(app.ControlPanel);
            app.RowsLabel.Position = [20 620 40 20];
            app.RowsLabel.Text = 'Rows:';

            app.RowsSpinner = uispinner(app.ControlPanel);
            app.RowsSpinner.ValueChangedFcn = createCallbackFcn(app, @RowsSpinnerValueChanged, true);
            app.RowsSpinner.Position = [70 620 60 20];
            app.RowsSpinner.Limits = [1 10];
            app.RowsSpinner.Value = 2;

            app.ColsLabel = uilabel(app.ControlPanel);
            app.ColsLabel.Position = [150 620 40 20];
            app.ColsLabel.Text = 'Cols:';

            app.ColsSpinner = uispinner(app.ControlPanel);
            app.ColsSpinner.ValueChangedFcn = createCallbackFcn(app, @ColsSpinnerValueChanged, true);
            app.ColsSpinner.Position = [200 620 60 20];
            app.ColsSpinner.Limits = [1 10];
            app.ColsSpinner.Value = 1;

            % Signal table
            app.SignalTable = uitable(app.ControlPanel);
            app.SignalTable.Position = [20 200 280 350];
            app.SignalTable.ColumnName = {'Signal'; 'Info'; 'Selected'; 'Scale'; 'State'};  % ADD 'State'
            app.SignalTable.ColumnEditable = [false false true true true];  % ADD true for State
            app.SignalTable.ColumnWidth = {70, 50, 50, 50, 50};  % ADJUST widths
            app.SignalTable.CellEditCallback = createCallbackFcn(app, @CellEdit, true);

            % Additional controls
            app.AutoScaleCheckbox = uicheckbox(app.ControlPanel);
            app.AutoScaleCheckbox.Position = [20 170 100 20];
            app.AutoScaleCheckbox.Text = 'Auto Scale';
            app.AutoScaleCheckbox.Value = true;

            app.ExportButton = uibutton(app.ControlPanel, 'push');
            app.ExportButton.ButtonPushedFcn = createCallbackFcn(app, @ExportButtonPushed, true);
            app.ExportButton.Position = [20 130 80 25];
            app.ExportButton.Text = 'Export';

            app.SaveConfigButton = uibutton(app.ControlPanel, 'push');
            app.SaveConfigButton.ButtonPushedFcn = createCallbackFcn(app, @SaveConfigButtonPushed, true);
            app.SaveConfigButton.Position = [110 130 80 25];
            app.SaveConfigButton.Text = 'Save Config';

            app.LoadConfigButton = uibutton(app.ControlPanel, 'push');
            app.LoadConfigButton.ButtonPushedFcn = createCallbackFcn(app, @LoadConfigButtonPushed, true);
            app.LoadConfigButton.Position = [200 130 80 25];
            app.LoadConfigButton.Text = 'Load Config';

            % % Save Template Button
            % app.SaveTemplateButton = uibutton(app.ControlPanel, 'push');
            % app.SaveTemplateButton.ButtonPushedFcn = @(~,~)app.saveSignalTemplate('');
            % app.SaveTemplateButton.Position = [20 70 120 25];
            % app.SaveTemplateButton.Text = 'Save Template';
            % 
            % % Load Template Button
            % app.LoadTemplateButton = uibutton(app.ControlPanel, 'push');
            % app.LoadTemplateButton.ButtonPushedFcn = @(~,~)app.loadSignalTemplate();
            % app.LoadTemplateButton.Position = [150 70 120 25];
            % app.LoadTemplateButton.Text = 'Load Template';


            % PDF Export Button
            app.ExportPDFButton = uibutton(app.ControlPanel, 'push');
            app.ExportPDFButton.ButtonPushedFcn = createCallbackFcn(app, @ExportToPDFButtonPushed, true);
            app.ExportPDFButton.Position = [20 100 80 25];
            app.ExportPDFButton.Text = 'Export PDF';
            app.ExportPDFButton.BackgroundColor = [0.2 0.6 0.8];
            app.ExportPDFButton.FontColor = [1 1 1];

            % Statistics Button
            app.StatsButton = uibutton(app.ControlPanel, 'push');
            app.StatsButton.ButtonPushedFcn = createCallbackFcn(app, @showSignalStats, true);
            app.StatsButton.Position = [110 100 80 25];
            app.StatsButton.Text = 'Statistics';

            % Reset Zoom Button
            app.ResetZoomButton = uibutton(app.ControlPanel, 'push');
            app.ResetZoomButton.ButtonPushedFcn = createCallbackFcn(app, @resetZoom, true);
            app.ResetZoomButton.Position = [200 100 80 25];
            app.ResetZoomButton.Text = 'Reset Zoom';


            % Show the figure after all components are created
            app.UIFigure.Visible = 'on';
        end

        function refreshPlots(app, tabIndices)
            if nargin < 2
                tabIndices = 1:numel(app.AxesArrays);
            end

            if isempty(app.DataBuffer)
                return;
            end

            for tabIdx = tabIndices
                if tabIdx > numel(app.AxesArrays) || isempty(app.AxesArrays{tabIdx})
                    continue;
                end

                axes = app.AxesArrays{tabIdx};
                assignments = app.AssignedSignals{tabIdx};

                for k = 1:numel(axes)
                    ax = axes(k);
                    sigs = assignments{k};

                    cla(ax);
                    hold(ax, 'on');

                    if isempty(sigs)
                        continue;
                    end

                    for j = 1:numel(sigs)
                        s = sigs{j};

                        if ~ismember(s, app.DataBuffer.Properties.VariableNames)
                            continue;
                        end

                        validData = ~isnan(app.DataBuffer.(s));
                        if ~any(validData)
                            continue;
                        end

                        % Get time and scaled values
                        timeData = app.DataBuffer.Time(validData);
                        scaleFactor = 1.0;
                        if app.SignalScaling.isKey(s)
                            scaleFactor = app.SignalScaling(s);
                        end
                        scaledData = app.DataBuffer.(s)(validData) * scaleFactor;

                        % Check if state signal
                        isStateSignal = false;
                        if app.StateSignals.isKey(s)
                            isStateSignal = app.StateSignals(s);
                        end

                        % Prepare label for legend
                        if scaleFactor ~= 1.0
                            legendLabel = sprintf('%s (×%.2f)', s, scaleFactor);
                        else
                            legendLabel = s;
                        end
                        if isStateSignal
                            legendLabel = sprintf('%s [STATE]', legendLabel);
                        end

                        color = app.Colors(mod(j-1, size(app.Colors,1)) + 1, :);

                        if isStateSignal
                            % Plot vertical lines for transitions
                            app.plotStateSignal(ax, timeData, scaledData, color, legendLabel);
                        else
                            % Plot continuous line
                            plot(ax, timeData, scaledData, ...
                                'LineWidth', 1.5, ...
                                'Color', color, ...
                                'DisplayName', legendLabel);
                        end
                    end

                    % Show legend if anything plotted
                    if ~isempty(ax.Children)
                        legend(ax, 'show', 'Location', 'best');
                    end

                    % Auto-scale
                    if app.AutoScaleCheckbox.Value
                        axis(ax, 'tight');
                    end

                    grid(ax, 'on');
                    ax.XLabel.String = 'Time';
                    ax.YLabel.String = 'Value';
                end
            end
        end

        function loadSignalTemplate(app)
            [file, path] = uigetfile('*.mat', 'Load Template');
            if isequal(file,0)
                return;
            end

            templateFile = fullfile(path,file);
            data = load(templateFile);
            template = data.template;

            % Apply template assignments
            app.AssignedSignals = template.AssignedSignals;
            app.SignalScaling = template.SignalScaling;
            app.StateSignals = template.StateSignals;
            app.TabLayouts = template.TabLayouts;

            % Recreate tabs
            while numel(app.PlotTabs) > 1
                app.closeTab(2);
            end

            % First tab
            if ~isempty(app.TabLayouts{1})
                app.createSubplotsForTab(1, app.TabLayouts{1}(1), app.TabLayouts{1}(2));
            end

            % Additional tabs
            for i = 2:numel(app.TabLayouts)
                if ~isempty(app.TabLayouts{i})
                    tabIdx = numel(app.PlotTabs)+1;
                    tab = uitab(app.MainTabGroup, 'Title', sprintf('Tab %d',tabIdx));
                    app.PlotTabs{tabIdx} = tab;
                    app.GridLayouts{tabIdx} = uigridlayout(tab,[2,1]);
                    app.AxesArrays{tabIdx} = matlab.ui.control.UIAxes.empty;
                    app.AssignedSignals{tabIdx} = cell(2,1);
                    app.createSubplotsForTab(tabIdx, app.TabLayouts{i}(1), app.TabLayouts{i}(2));
                end
            end

            app.updateSignalCheckboxes();
            app.refreshPlots();
        end


        function plotStateSignal(app, ax, timeData, valueData, color, displayName)
            % Plot vertical lines for all transitions in valueData
            % spanning the Y-limits of the axes

            if length(timeData) < 2
                return;
            end

            % Find all transition indices (first point and any value change)
            changeIdx = find([true; diff(valueData) ~= 0]);

            % If no changes, return
            if isempty(changeIdx)
                return;
            end

            % Get current Y limits after other plots
            yLimits = ylim(ax);

            % For each transition, plot a vertical line
            for k = 1:numel(changeIdx)
                t = timeData(changeIdx(k));
                % Only add legend to the first line
                if k == 1 && nargin >=5 && ~isempty(displayName)
                    plot(ax, [t t], yLimits, ...
                        'Color', color, 'LineWidth', 1.5, ...
                        'DisplayName', displayName);
                else
                    plot(ax, [t t], yLimits, ...
                        'Color', color, 'LineWidth', 1.5);
                end
            end
        end




        function CellEdit(app, event)
            data = app.SignalTable.Data;
            indices = event.Indices;

            if size(indices,1) == 1
                row = indices(1);
                col = indices(2);

                % Map back to the full signal name
                shortName = data.Signal{row};

                % Extract short names
                allShortNames = cell(size(app.SignalNames));
                for i = 1:numel(app.SignalNames)
                    parts = split(app.SignalNames{i}, ':');
                    allShortNames{i} = strtrim(parts{end});
                end

                idx = find(strcmp(allShortNames, shortName),1);
                if isempty(idx)
                    warning('Signal mapping failed.');
                    return;
                end
                fullName = app.SignalNames{idx};

                if col == 3  % Selected
                    selectedIdx = find(data.Selected);
                    selectedShort = data.Signal(selectedIdx);
                    selFull = {};
                    for s = selectedShort'
                        i2 = find(strcmp(allShortNames, s{1}),1);
                        if ~isempty(i2)
                            selFull{end+1} = app.SignalNames{i2};
                        end
                    end
                    app.AssignedSignals{app.CurrentTabIdx}{app.SelectedSubplotIdx} = selFull;
                    app.refreshPlots(app.CurrentTabIdx);

                elseif col == 4  % Scale
                    scaleFactor = data.Scale(row);
                    if isnumeric(scaleFactor) && isfinite(scaleFactor) && scaleFactor ~= 0
                        app.SignalScaling(fullName) = scaleFactor;
                    else
                        app.SignalScaling(fullName) = 1.0;
                        data.Scale(row) = 1.0;
                        app.SignalTable.Data = data;
                    end
                    app.refreshPlots();

                elseif col == 5  % State
                    isState = data.State(row);
                    app.StateSignals(fullName) = isState;
                    app.refreshPlots();
                    app.updateSignalCheckboxes();
                end
            end
        end


        function showSignalStats(app, event)
            if isempty(app.DataBuffer)
                return;
            end

            % Create statistics dialog
            statsDialog = uifigure('Name', 'Signal Statistics', 'Position', [200 200 400 300]);

            % Create table for statistics
            statsTable = uitable(statsDialog, 'Position', [10 10 380 280]);

            % Calculate statistics for each signal
            signalNames = app.SignalNames;
            stats = cell(numel(signalNames), 6);

            for i = 1:numel(signalNames)
                signalName = signalNames{i};
                if ismember(signalName, app.DataBuffer.Properties.VariableNames)
                    data = app.DataBuffer.(signalName);
                    validData = data(~isnan(data));

                    if ~isempty(validData)
                        stats{i, 1} = signalName;
                        stats{i, 2} = numel(validData);
                        stats{i, 3} = sprintf('%.3f', mean(validData));
                        stats{i, 4} = sprintf('%.3f', std(validData));
                        stats{i, 5} = sprintf('%.3f', min(validData));
                        stats{i, 6} = sprintf('%.3f', max(validData));
                    else
                        stats{i, 1} = signalName;
                        stats{i, 2} = 0;
                        stats{i, 3} = 'N/A';
                        stats{i, 4} = 'N/A';
                        stats{i, 5} = 'N/A';
                        stats{i, 6} = 'N/A';
                    end
                end
            end

            statsTable.Data = stats;
            statsTable.ColumnName = {'Signal', 'Count', 'Mean', 'Std', 'Min', 'Max'};
            statsTable.ColumnWidth = {80, 50, 60, 60, 60, 60};
        end


        function updatePerformanceMetrics(app)
            persistent lastMemCheck;
            if isempty(lastMemCheck)
                lastMemCheck = tic;
            end

            % Check memory usage every 30 seconds
            if toc(lastMemCheck) > 30
                memInfo = memory;
                app.StatusLabel.Text = sprintf('Memory: %.1fMB used', memInfo.MemUsedMATLAB/1024/1024);
                lastMemCheck = tic;
            end
        end

        function manageDataBuffer(app)
            % Limit buffer size to prevent memory issues
            maxBufferSize = 10000; % Maximum number of rows

            if height(app.DataBuffer) > maxBufferSize
                % Keep only the latest data
                app.DataBuffer = app.DataBuffer(end-maxBufferSize+1:end, :);

                % Update status
                app.StatusLabel.Text = sprintf('Buffer trimmed to %d rows', maxBufferSize);
            end
        end

        function createSignalFilter(app)
            % Add search field above signal table
            searchField = uieditfield(app.ControlPanel, 'text');
            searchField.Position = [20 560 260 22];
            searchField.Placeholder = 'Search signals...';

            % Filter as you type
            searchField.ValueChangingFcn = @(src,event) app.filterSignals(event.Value);
        end



        function saveSignalTemplate(app, templateName)
            if isempty(templateName)
                templateName = inputdlg('Enter template name:', 'Save Template');
                if isempty(templateName)
                    return;
                end
                templateName = templateName{1};
            end

            template = struct();
            template.AssignedSignals = app.AssignedSignals;
            template.SignalScaling = app.SignalScaling;
            template.StateSignals = app.StateSignals;
            template.TabLayouts = app.TabLayouts;

            templateFile = fullfile(pwd, 'templates', [templateName '.mat']);
            if ~exist(fileparts(templateFile), 'dir')
                mkdir(fileparts(templateFile));
            end

            save(templateFile, 'template');
            uialert(app.UIFigure, sprintf('Template "%s" saved successfully.', templateName), 'Success');
        end


        function filterSignals(app, searchText)
            if isempty(app.SignalNames) || isempty(searchText)
                app.updateSignalCheckboxes();
                return;
            end

            % Filter signals based on search text
            filteredSignals = app.SignalNames(contains(app.SignalNames, searchText, 'IgnoreCase', true));

            % Update table with filtered signals
            if isempty(filteredSignals)
                app.SignalTable.Data = table({'No matches'}, {''}, {false}, {1.0}, {false}, ...
                    'VariableNames', {'Signal','Info','Selected','Scale','State'});
            else
                % Create filtered table data
                n = numel(filteredSignals);
                Signal = filteredSignals(:);
                Info = strings(n,1);
                Selected = false(n,1);
                Scale = ones(n,1);
                State = false(n,1);

                for i = 1:n
                    signalName = Signal{i};

                    % Get info
                    count = 0;
                    if ~isempty(app.DataBuffer) && ismember(signalName, app.DataBuffer.Properties.VariableNames)
                        count = sum(~isnan(app.DataBuffer.(signalName)));
                    end
                    Info(i) = sprintf('(%dx1)', count);

                    % Get scaling and state
                    if app.SignalScaling.isKey(signalName)
                        Scale(i) = app.SignalScaling(signalName);
                    end
                    if app.StateSignals.isKey(signalName)
                        State(i) = app.StateSignals(signalName);
                    end
                end

                % Mark selected signals
                if app.CurrentTabIdx <= numel(app.AssignedSignals) && ...
                        app.SelectedSubplotIdx <= numel(app.AssignedSignals{app.CurrentTabIdx}) && ...
                        ~isempty(app.AssignedSignals{app.CurrentTabIdx}{app.SelectedSubplotIdx})
                    sel = app.AssignedSignals{app.CurrentTabIdx}{app.SelectedSubplotIdx};
                    Selected = ismember(Signal, sel);
                end

                app.SignalTable.Data = table(Signal, Info, Selected, Scale, State, ...
                    'VariableNames', {'Signal','Info','Selected','Scale','State'});
            end
        end


        function enableZoomPan(app)
            % Enable zoom and pan for all axes
            for tabIdx = 1:numel(app.AxesArrays)
                if ~isempty(app.AxesArrays{tabIdx})
                    for ax = app.AxesArrays{tabIdx}
                        zoom(ax, 'on');
                        pan(ax, 'on');
                    end
                end
            end
        end

        function resetZoom(app, event)
            % Reset zoom for all axes in current tab
            if app.CurrentTabIdx <= numel(app.AxesArrays) && ~isempty(app.AxesArrays{app.CurrentTabIdx})
                for ax = app.AxesArrays{app.CurrentTabIdx}
                    axis(ax, 'auto');
                end
            end
        end

        % Add this method to automatically save CSV path when it changes
        function CSVPathFieldValueChanged(app, event)
            % Auto-save CSV path when it changes
            app.autoSaveCSVPath();
        end

        % Add this method to automatically save the CSV path
        function autoSaveCSVPath(app)
            try
                csvPath = app.CSVPathField.Value;
                if ~isempty(csvPath)
                    % Save to a simple config file
                    configFile = fullfile(pwd, 'last_csv_path.mat');
                    save(configFile, 'csvPath');
                end
            catch
                % Silently ignore errors in auto-save
            end
        end

        function ExportToPDFButtonPushed(app, event)
            if isempty(app.DataBuffer)
                uialert(app.UIFigure, 'No data to export.', 'Info');
                return;
            end

            [file, path] = uiputfile('*.pdf', 'Export Plots to PDF');
            if isequal(file, 0)
                return;
            end

            try
                % Create temporary figure for PDF export
                tempFig = figure('Visible', 'off', 'Units', 'normalized', 'Position', [0 0 1 1]);

                % Get selected signals from current tab
                selectedSignals = {};
                assignments = app.AssignedSignals{app.CurrentTabIdx};
                for i = 1:numel(assignments)
                    if ~isempty(assignments{i})
                        selectedSignals = [selectedSignals, assignments{i}];
                    end
                end

                if isempty(selectedSignals)
                    uialert(app.UIFigure, 'No signals selected for export.', 'Info');
                    close(tempFig);
                    return;
                end

                % Calculate subplot layout
                numSignals = numel(selectedSignals);
                rows = ceil(sqrt(numSignals));
                cols = ceil(numSignals / rows);

                % Create subplots for each selected signal
                for i = 1:numSignals
                    subplot(rows, cols, i);

                    signalName = selectedSignals{i};
                    if ~ismember(signalName, app.DataBuffer.Properties.VariableNames)
                        continue;
                    end

                    validData = ~isnan(app.DataBuffer.(signalName));
                    if ~any(validData)
                        continue;
                    end

                    timeData = app.DataBuffer.Time(validData);
                    scaleFactor = 1.0;
                    if app.SignalScaling.isKey(signalName)
                        scaleFactor = app.SignalScaling(signalName);
                    end
                    scaledData = app.DataBuffer.(signalName)(validData) * scaleFactor;

                    % Check if state signal
                    isStateSignal = false;
                    if app.StateSignals.isKey(signalName)
                        isStateSignal = app.StateSignals(signalName);
                    end

                    if isStateSignal
                        % Plot state signal as stem plot
                        stem(timeData, scaledData, 'LineWidth', 1.5);
                        title(sprintf('%s [STATE] (×%.2f)', signalName, scaleFactor));
                    else
                        % Plot continuous signal
                        plot(timeData, scaledData, 'LineWidth', 1.5);
                        title(sprintf('%s (×%.2f)', signalName, scaleFactor));
                    end

                    xlabel('Time');
                    ylabel('Value');
                    grid on;
                end

                % Add main title
                sgtitle(sprintf('Signal Viewer Export - %s', datestr(now)));

                % Export to PDF
                exportgraphics(tempFig, fullfile(path, file), 'ContentType', 'vector');

                close(tempFig);
                uialert(app.UIFigure, 'PDF exported successfully.', 'Success');

            catch ME
                if exist('tempFig', 'var') && ishandle(tempFig)
                    close(tempFig);
                end
                uialert(app.UIFigure, ['PDF export failed: ' ME.message], 'Error');
            end
        end

        % Add this method to load the last CSV path
        function loadLastCSVPath(app)
            try
                configFile = fullfile(pwd, 'last_csv_path.mat');
                if isfile(configFile)
                    data = load(configFile);
                    if isfield(data, 'csvPath') && ~isempty(data.csvPath)
                        app.CSVPathField.Value = data.csvPath;
                    end
                end
            catch
                % Silently ignore errors in auto-load
            end
        end
        function ExportButtonPushed(app, event)
            if isempty(app.DataBuffer)
                uialert(app.UIFigure, 'No data to export.', 'Info');
                return;
            end

            [file, path] = uiputfile('*.csv', 'Export Data');
            if isequal(file, 0)
                return;
            end

            try
                writetable(app.DataBuffer, fullfile(path, file));
                uialert(app.UIFigure, 'Data exported successfully.', 'Success');
            catch ME
                uialert(app.UIFigure, ['Export failed: ' ME.message], 'Error');
            end
        end

        function SaveConfigButtonPushed(app, event)
            % Ask user for save location
            [filename, pathname] = uiputfile('*.mat', 'Save Configuration As...', 'signal_viewer_config.mat');
            if isequal(filename, 0) || isequal(pathname, 0)
                return; % User cancelled
            end

            configFile = fullfile(pathname, filename);

            try
                % Save complete app state
                config = struct();

                % Plot configuration and assignments
                config.PlotConfiguration = app.AssignedSignals;
                config.SignalScaling = app.SignalScaling;

                % UI Settings
                config.CSVPath = app.CSVPathField.Value;
                config.AutoScale = app.AutoScaleCheckbox.Value;
                config.CurrentTabIdx = app.CurrentTabIdx;
                config.SelectedSubplotIdx = app.SelectedSubplotIdx;
                config.TabCounter = app.TabCounter;

                % Spinner values
                config.RowsSpinnerValue = app.RowsSpinner.Value;
                config.ColsSpinnerValue = app.ColsSpinner.Value;

                % Tab layouts and titles
                config.TabLayouts = cell(numel(app.AxesArrays), 1);
                config.TabTitles = cell(numel(app.PlotTabs), 1);

                for i = 1:numel(app.AxesArrays)
                    if ~isempty(app.AxesArrays{i})
                        % Get actual grid size from TabLayouts if available
                        if i <= numel(app.TabLayouts) && ~isempty(app.TabLayouts{i})
                            config.TabLayouts{i} = app.TabLayouts{i};
                        else
                            % Fallback: calculate from number of axes
                            numAxes = numel(app.AxesArrays{i});
                            rows = app.RowsSpinner.Value;
                            cols = app.ColsSpinner.Value;
                            config.TabLayouts{i} = [rows, cols];
                        end
                    end
                end

                % Store tab titles
                for i = 1:numel(app.PlotTabs)
                    config.TabTitles{i} = app.PlotTabs{i}.Title;
                end

                % Save signal table state (the tree field and checked/unchecked states)
                if ~isempty(app.SignalTable.Data)
                    tableData = app.SignalTable.Data;

                    % Save complete table data
                    config.SignalTableData = struct();
                    config.SignalTableData.Signal = tableData.Signal;
                    config.SignalTableData.Info = tableData.Info;
                    config.SignalTableData.Selected = tableData.Selected;
                    config.SignalTableData.Scale = tableData.Scale;
                    config.SignalTableData.State = tableData.State;
                end

                % Save signal names
                config.SignalNames = app.SignalNames;

                % Save data buffer structure (without actual data to keep file size small)
                if ~isempty(app.DataBuffer)
                    config.DataBufferColumns = app.DataBuffer.Properties.VariableNames;
                else
                    config.DataBufferColumns = {};
                end

                % Save additional app state
                config.NumColumns = app.NumColumns;
                config.DataCount = app.DataCount;
                config.UpdateCounter = app.UpdateCounter;
                config.IsRunning = false; % Always save as not running

                % Save timestamp
                config.SaveTimestamp = datetime('now');
                config.DataBuffer = app.DataBuffer;
                config.StateSignals = app.StateSignals;

                save(configFile, 'config');
                uialert(app.UIFigure, sprintf('Configuration saved successfully to:\n%s', configFile), 'Success');

            catch ME
                uialert(app.UIFigure, ['Save failed: ' ME.message], 'Error');
            end
        end

        function LoadConfigButtonPushed(app, event)
            % Ask user for config file to load
            [filename, pathname] = uigetfile('*.mat', 'Load Configuration From...');
            if isequal(filename, 0) || isequal(pathname, 0)
                return; % User cancelled
            end

            configFile = fullfile(pathname, filename);

            if ~isfile(configFile)
                uialert(app.UIFigure, 'Configuration file not found.', 'Error');
                return;
            end

            try
                data = load(configFile);
                config = data.config;

                % Stop streaming if running
                if app.IsRunning
                    app.StopButtonPushed();
                end

                % Clear existing tabs (except first one)
                while numel(app.PlotTabs) > 1
                    app.closeTab(2);
                end

                % Restore basic settings
                if isfield(config, 'CSVPath')
                    app.CSVPathField.Value = config.CSVPath;
                end

                if isfield(config, 'AutoScale')
                    app.AutoScaleCheckbox.Value = config.AutoScale;
                end

                if isfield(config, 'SignalScaling')
                    app.SignalScaling = config.SignalScaling;
                else
                    app.SignalScaling = containers.Map();
                end

                if isfield(config, 'TabCounter')
                    app.TabCounter = config.TabCounter;
                end

                % Restore spinner values
                if isfield(config, 'RowsSpinnerValue')
                    app.RowsSpinner.Value = config.RowsSpinnerValue;
                end

                if isfield(config, 'ColsSpinnerValue')
                    app.ColsSpinner.Value = config.ColsSpinnerValue;
                end

                % Restore signal names
                if isfield(config, 'SignalNames')
                    app.SignalNames = config.SignalNames;
                end

                % Restore additional app state
                if isfield(config, 'NumColumns')
                    app.NumColumns = config.NumColumns;
                end

                if isfield(config, 'DataCount')
                    app.DataCount = config.DataCount;
                end

                if isfield(config, 'UpdateCounter')
                    app.UpdateCounter = config.UpdateCounter;
                end

                % Restore tabs and their layouts
                if isfield(config, 'TabLayouts') && isfield(config, 'TabTitles')
                    % Update first tab
                    if ~isempty(config.TabLayouts{1})
                        layout = config.TabLayouts{1};
                        app.createSubplotsForTab(1, layout(1), layout(2));
                        if ~isempty(config.TabTitles{1})
                            app.PlotTabs{1}.Title = config.TabTitles{1};
                        end
                    end

                    % Create additional tabs
                    for i = 2:numel(config.TabLayouts)
                        if ~isempty(config.TabLayouts{i})
                            % Add new tab
                            tabIdx = numel(app.PlotTabs) + 1;
                            tab = uitab(app.MainTabGroup, 'Title', config.TabTitles{i});
                            app.PlotTabs{tabIdx} = tab;
                            app.GridLayouts{tabIdx} = uigridlayout(tab, [2, 1]);
                            app.AxesArrays{tabIdx} = matlab.ui.control.UIAxes.empty;
                            app.AssignedSignals{tabIdx} = cell(2, 1);

                            % Create subplots with saved layout
                            layout = config.TabLayouts{i};
                            app.createSubplotsForTab(tabIdx, layout(1), layout(2));
                        end
                    end
                end
                if isfield(config, 'DataBuffer')
                    app.DataBuffer = config.DataBuffer;
                else
                    app.DataBuffer = table();
                end
                if isfield(config, 'StateSignals')
                    app.StateSignals = config.StateSignals;
                else
                    app.StateSignals = containers.Map();
                end
                % Restore plot assignments
                if isfield(config, 'PlotConfiguration')
                    app.AssignedSignals = config.PlotConfiguration;
                end

                % Restore selection state
                if isfield(config, 'CurrentTabIdx')
                    app.CurrentTabIdx = min(config.CurrentTabIdx, numel(app.PlotTabs));
                    app.MainTabGroup.SelectedTab = app.PlotTabs{app.CurrentTabIdx};
                end

                if isfield(config, 'SelectedSubplotIdx')
                    maxSubplots = numel(app.AxesArrays{app.CurrentTabIdx});
                    app.SelectedSubplotIdx = min(config.SelectedSubplotIdx, maxSubplots);
                end

                % Restore signal table state (tree field and checked/unchecked states)
                if isfield(config, 'SignalTableData')
                    tableData = config.SignalTableData;

                    % Reconstruct table data
                    restoredTable = table(tableData.Signal, tableData.Info, ...
                        tableData.Selected, tableData.Scale, tableData.State, ...
                        'VariableNames', {'Signal', 'Info', 'Selected', 'Scale', 'State'});


                    app.SignalTable.Data = restoredTable;
                else
                    % Fallback: update signal checkboxes normally
                    app.updateSignalCheckboxes();
                end

                % Update displays
                app.highlightSelected();

                % Only refresh plots if we have signal data
                if ~isempty(app.SignalNames)
                    app.refreshPlots();
                end

                % Show success message with timestamp if available
                successMsg = sprintf('Configuration loaded successfully from:\n%s', configFile);
                if isfield(config, 'SaveTimestamp')
                    successMsg = sprintf('%s\n\nSaved on: %s', successMsg, datestr(config.SaveTimestamp));
                end

                uialert(app.UIFigure, successMsg, 'Success');

            catch ME
                uialert(app.UIFigure, ['Load failed: ' ME.message], 'Error');
            end
        end
    end

    methods (Access = public)
        function app = SignalViewer
            % Create UIFigure and components
            createComponents(app)

            % Register the app with App Designer
            registerApp(app, app.UIFigure)

            % Execute the startup function
            runStartupFcn(app, @startupFcn)

            if nargout == 0
                clear app
            end
        end

        function delete(app)
            % Delete UIFigure when app is deleted
            if app.IsRunning
                app.StopButtonPushed();
            end

            if isvalid(app.ScalingDialog)
                delete(app.ScalingDialog);
            end

            delete(app.UIFigure)
        end
    end
end