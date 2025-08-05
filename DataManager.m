% Updated DataManager.m - Fixed streaming with file monitoring and timeout - REMOVED REDUNDANT DRAWNOW
classdef DataManager < handle
    properties
        App
        SignalNames      cell
        DataTables       cell   % Cell array of tables, one per CSV
        SignalScaling    containers.Map
        StateSignals     containers.Map
        IsRunning        logical = false
        DataCount        double = 0
        UpdateCounter    double = 0
        LastUpdateTime   datetime
        % Multi-CSV streaming properties
        CSVFilePaths     cell   % Cell array of file paths
        LastFileModTimes cell   % Cell array of datetimes
        LastReadRows     cell   % Cell array of doubles
        StreamingTimers  cell   % Cell array of timers
        TimeoutDuration  double = 1.0  % 1 second timeout
        UpdateRate       double = 0.1  % Check every 100ms
        LatestDataRates  cell   % Cell array of doubles, one per CSV
    end

    methods
        function obj = DataManager(app)
            obj.App = app;
            obj.SignalNames = {};
            obj.DataTables = {};
            obj.SignalScaling = containers.Map();
            obj.StateSignals = containers.Map();
            obj.LastUpdateTime = datetime('now');
            obj.CSVFilePaths = {};
            obj.LastFileModTimes = {};
            obj.LastReadRows = {};
            obj.StreamingTimers = {};
            obj.LatestDataRates = {};
        end

        function startStreamingAll(obj)
            app = obj.App;
            % Stop all existing timers before starting new streaming
            obj.stopStreamingAll();
            for i = 1:numel(obj.CSVFilePaths)
                obj.startStreamingForCSV(i);
            end
            obj.IsRunning = true;
            app.StatusLabel.Text = '🔄 Streaming...';
            app.StatusLabel.FontColor = [0.2 0.6 0.9];
            app.StreamingInfoLabel.Text = sprintf('Streaming %d CSV(s): %s', numel(obj.CSVFilePaths), strjoin(obj.CSVFilePaths, ', '));
            % REMOVED: drawnow; - not needed here
        end

        function sigInfo = getSignalInfoByFullName(obj, fullName)
            sigInfo = [];

            for csvIdx = 1:numel(obj.DataTables)
                T = obj.DataTables{csvIdx};
                varNames = T.Properties.VariableNames;
                for v = 1:numel(varNames)
                    if contains(fullName, varNames{v})
                        sigInfo.Reader = @(~) deal(T.Time, T.(varNames{v}));
                        sigInfo.BaseSignalName = varNames{v};
                        sigInfo.CSVIdx = csvIdx;
                        return;
                    end
                end
            end
        end


        function startStreamingForCSV(obj, idx)
            % Initialize file monitoring for this CSV
            if ~obj.initializeFileMonitoring(idx)
                return;
            end
            % Read initial data for this CSV
            obj.readInitialData(idx);
            % Start streaming timer for this CSV
            obj.startStreamingTimer(idx);
        end

        function tf = initializeFileMonitoring(obj, idx)
            tf = false;
            filePath = obj.CSVFilePaths{idx};
            if ~isfile(filePath)
                return;
            end
            try
                fileInfo = dir(filePath);
                obj.LastFileModTimes{idx} = datetime(fileInfo.datenum, 'ConvertFrom', 'datenum');
                obj.LastReadRows{idx} = 0;
                tf = true;
            catch ME
                % uialert(obj.App.UIFigure, ['Error initializing file monitoring: ' ME.message], 'Error');
            end
        end

        function readInitialData(obj, idx)
            filePath = obj.CSVFilePaths{idx};
            if ~isfile(filePath)
                obj.DataTables{idx} = [];
                return;
            end
            fileInfo = dir(filePath);
            if ~isstruct(fileInfo) || isempty(fileInfo)
                obj.DataTables{idx} = [];
                return;
            end
            if fileInfo(1).bytes == 0
                obj.DataTables{idx} = [];
                return;
            end
            opts = detectImportOptions(filePath);
            if isempty(opts.VariableNames)
                obj.DataTables{idx} = [];
                return;
            end
            opts = setvartype(opts, 'double');
            T = readtable(filePath, opts);
            if ~istable(T)
                obj.DataTables{idx} = [];
                return;
            end
            if isempty(T)
                obj.DataTables{idx} = [];
                return;
            end
            if ~ismember('Time', T.Properties.VariableNames)
                if ~isempty(T.Properties.VariableNames)
                    T.Properties.VariableNames{1} = 'Time';
                else
                    obj.DataTables{idx} = [];
                    return;
                end
            end
            if ~any(strcmp('Time', T.Properties.VariableNames))
                obj.DataTables{idx} = [];
                return;
            end
            obj.DataTables{idx} = T;
            obj.LastReadRows{idx} = height(T);
            % Update signal names (union of all signals)
            allSignals = {};
            for k = 1:numel(obj.DataTables)
                if ~isempty(obj.DataTables{k})
                    allSignals = union(allSignals, setdiff(obj.DataTables{k}.Properties.VariableNames, {'Time'}));
                end
            end
            obj.SignalNames = allSignals;
            obj.initializeSignalMaps();
            obj.App.buildSignalTree();
            obj.App.PlotManager.refreshPlots();
            obj.App.StatusLabel.Text = sprintf('📁 Loaded %d rows, %d signals (CSV %d)', ...
                height(T), numel(obj.SignalNames), idx);
            obj.App.DataRateLabel.Text = sprintf('📊 Initial load: %d samples (CSV %d)', height(T), idx);
            obj.LastUpdateTime = datetime('now');
        end

        function startStreamingTimer(obj, idx)
            % Create and start the streaming timer for a specific CSV
            if numel(obj.StreamingTimers) >= idx && ~isempty(obj.StreamingTimers{idx}) && isvalid(obj.StreamingTimers{idx})
                stop(obj.StreamingTimers{idx});
                delete(obj.StreamingTimers{idx});
            end
            obj.StreamingTimers{idx} = timer(...
                'ExecutionMode', 'fixedRate', ...
                'Period', 0.01, ...
                'TimerFcn', @(~,~) obj.checkForUpdates(idx));
            start(obj.StreamingTimers{idx});
            obj.LastUpdateTime = datetime('now');
        end


        % Add this method to better integrate with derived signals:
        function updateDerivedSignalsAfterStream(obj)
            % This could be called after new data arrives to update derived signals
            % if they depend on streaming data
            if isprop(obj.App, 'SignalOperations') && ~isempty(obj.App.SignalOperations)
                % Could implement automatic recalculation of derived signals here
                % if desired for real-time derived signal updates
            end
        end
        function checkForUpdates(obj, idx)
            if ~isprop(obj.App, 'DataManager') || isempty(obj.App.DataManager) || ~isvalid(obj.App.DataManager)
                return;
            end
            try
                % Check if file has been modified
                if ~obj.hasFileChanged(idx)
                    % Check for timeout
                    if datetime('now') - obj.LastUpdateTime > seconds(obj.TimeoutDuration)
                        obj.handleTimeout(idx);
                        % REMOVED: drawnow; - not needed in timer callback
                        return;
                    end
                    % REMOVED: drawnow; - not needed in timer callback
                    return;
                end
                % File has changed - read new data
                obj.readNewData(idx);
                obj.LastUpdateTime = datetime('now');
                % REMOVED: drawnow; - not needed in timer callback
            catch
                obj.stopStreamingForCSV(idx);
                % REMOVED: drawnow; - not needed in timer callback
            end
        end

        function tf = hasFileChanged(obj, idx)
            tf = false;
            filePath = obj.CSVFilePaths{idx};
            if ~isfile(filePath)
                return;
            end
            try
                fileInfo = dir(filePath);
                currentModTime = datetime(fileInfo.datenum, 'ConvertFrom', 'datenum');
                if obj.LastReadRows{idx} == 0
                    tf = true;
                else
                    tf = currentModTime > obj.LastFileModTimes{idx};
                end
                if tf
                    obj.LastFileModTimes{idx} = currentModTime;
                end
            catch
                tf = false;
            end
        end

        function readNewData(obj, idx)
            try
                filePath = obj.CSVFilePaths{idx};
                if ~isfile(filePath)
                    return;
                end
                fileInfo = dir(filePath);
                if ~isstruct(fileInfo) || isempty(fileInfo)
                    return;
                end
                if fileInfo(1).bytes == 0
                    return;
                end
                opts = detectImportOptions(filePath);
                if isempty(opts.VariableNames)
                    return;
                end
                opts = setvartype(opts, 'double');
                T = readtable(filePath, opts);
                if ~istable(T)
                    return;
                end
                if isempty(T)
                    return;
                end
                if ~ismember('Time', T.Properties.VariableNames)
                    if ~isempty(T.Properties.VariableNames)
                        T.Properties.VariableNames{1} = 'Time';
                    else
                        return;
                    end
                end
                if ~any(strcmp('Time', T.Properties.VariableNames))
                    return;
                end
                T = sortrows(T, 'Time');
                currentRows = height(T);
                if currentRows > obj.LastReadRows{idx}
                    newRows = T((obj.LastReadRows{idx} + 1):end, :);
                    % Append new data to existing buffer
                    if isempty(obj.DataTables{idx})
                        obj.DataTables{idx} = newRows;
                    else
                        obj.DataTables{idx} = obj.mergeNewData(obj.DataTables{idx}, newRows);
                    end
                    % Update signal names if new columns appeared
                    allSignals = {};
                    for k = 1:numel(obj.DataTables)
                        if ~isempty(obj.DataTables{k})
                            allSignals = union(allSignals, setdiff(obj.DataTables{k}.Properties.VariableNames, {'Time'}));
                        end
                    end
                    obj.SignalNames = allSignals;
                    obj.initializeSignalMaps();
                    % Update tracking
                    obj.LastReadRows{idx} = currentRows;
                    % Update streaming status
                    obj.updateStreamingStatus(idx, currentRows);
                    % Update plots for streaming
                    obj.App.PlotManager.updateAllPlotsForStreaming();
                    obj.updateDerivedSignalsAfterStream(idx);
                    % Update status label
                    obj.App.StatusLabel.Text = '🔄 Streaming...';
                    obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
                    % Update streaming info label
                    obj.App.StreamingInfoLabel.Text = sprintf('Streaming %d CSV(s): %s', numel(obj.CSVFilePaths), strjoin(obj.CSVFilePaths, ', '));
                end
            catch
                % Ignore errors
            end
        end

        function tf = validateSessionData(obj)
            % More lenient validation that allows saving in most cases
            tf = true; % Start optimistic

            try
                % Only check critical failures, not empty data

                % Check if DataManager object itself is valid
                if ~isvalid(obj)
                    tf = false;
                    return;
                end

                % Check if essential properties exist (don't worry if they're empty)
                requiredProps = {'SignalNames', 'DataTables', 'CSVFilePaths', 'SignalScaling', 'StateSignals'};
                for i = 1:length(requiredProps)
                    if ~isprop(obj, requiredProps{i})
                        tf = false;
                        return;
                    end
                end

                % Check if containers.Map properties are the right type (can be empty)
                if ~isa(obj.SignalScaling, 'containers.Map')
                    tf = false;
                    return;
                end

                if ~isa(obj.StateSignals, 'containers.Map')
                    tf = false;
                    return;
                end

                % Check if cell array properties are the right type (can be empty)
                if ~iscell(obj.SignalNames)
                    tf = false;
                    return;
                end

                if ~iscell(obj.DataTables)
                    tf = false;
                    return;
                end

                if ~iscell(obj.CSVFilePaths)
                    tf = false;
                    return;
                end

                % If we get here, all essential checks passed
                tf = true;

            catch
                % If any error occurs during validation, assume it's OK to save
                tf = true;
            end
        end

        function mergedData = mergeNewData(obj, existingData, newData)
            try
                % Simple concatenation if column structures are identical
                if isequal(existingData.Properties.VariableNames, newData.Properties.VariableNames)
                    mergedData = [existingData; newData];
                else
                    % Use outerjoin for different column structures
                    mergedData = outerjoin(existingData, newData, ...
                        'Keys', 'Time', 'MergeKeys', true, 'Type', 'full');

                    % Clean up duplicate columns from outerjoin
                    mergedData = obj.cleanupJoinedData(mergedData);
                end

                % Sort by time
                mergedData = sortrows(mergedData, 'Time');

            catch ME
                % Fallback: just append new data
                fprintf('Merge error, using simple append: %s\n', ME.message);
                mergedData = [existingData; newData];
            end
        end

        function cleanedData = cleanupJoinedData(~, joinedData)
            % Clean up outerjoin results by handling _left/_right suffixes
            cleanedData = joinedData;
            if ~istable(cleanedData)
                warning('cleanupJoinedData: cleanedData is not a table');
                return;
            end
            vars = cleanedData.Properties.VariableNames;

            leftCols = contains(vars, '_left');
            rightCols = contains(vars, '_right');

            for i = find(leftCols)
                leftName = vars{i};
                baseName = erase(leftName, '_left');
                rightName = strcat(baseName, '_right');

                if ismember(rightName, vars)
                    % Combine left and right columns (right takes precedence for non-NaN)
                    leftData = cleanedData.(leftName);
                    rightData = cleanedData.(rightName);

                    % Use right data where available, left data otherwise
                    combinedData = leftData;
                    validRight = ~isnan(rightData);
                    combinedData(validRight) = rightData(validRight);

                    cleanedData.(baseName) = combinedData;
                    cleanedData.(leftName) = [];
                    cleanedData.(rightName) = [];
                end
            end
        end

        function updateStreamingStatus(obj, idx, ~)
            % Update status labels with streaming information for a specific CSV
            app = obj.App;
            % Calculate data rate using Time column if possible
            dataRate = 0;
            if height(obj.DataTables{idx}) > 1 && ismember('Time', obj.DataTables{idx}.Properties.VariableNames)
                T = obj.DataTables{idx};
                timeSpan = T.Time(end) - T.Time(1);
                if timeSpan > 0
                    dataRate = (height(T)-1) / timeSpan;
                end
            end
            obj.LatestDataRates{idx} = dataRate;
            app.DataRateLabel.Text = sprintf('📊 Rate: %.1f Hz | Total: %d samples (CSV %d)', dataRate, height(obj.DataTables{idx}), idx);
        end

        function handleTimeout(obj, idx)
            fileName = obj.CSVFilePaths{idx};
            obj.App.StatusLabel.Text = sprintf('⏰ Stopped (timeout): %s', fileName);
            obj.App.StatusLabel.FontColor = [0.9 0.6 0.2];
            obj.stopStreamingForCSV(idx);
            obj.App.DataRateLabel.Text = sprintf('📊 Rate: 0 Hz | Total: %d samples (CSV %d)', height(obj.DataTables{idx}), idx);
            obj.App.StreamingInfoLabel.Text = sprintf('Timeout: %s', fileName);
            % REMOVED: drawnow; - not needed here
        end

        function stopStreamingAll(obj)
            obj.IsRunning = false;
            for i = 1:numel(obj.StreamingTimers)
                obj.stopStreamingForCSV(i);
            end
            obj.App.StatusLabel.Text = '⏹️ Stopped';
            obj.App.StatusLabel.FontColor = [0.5 0.5 0.5];
            obj.App.DataRateLabel.Text = '📊 Final: stopped all CSVs';
            obj.App.StreamingInfoLabel.Text = 'Streaming stopped.';
            % REMOVED: drawnow; - not needed here
        end

        function stopStreamingForCSV(obj, idx)
            if numel(obj.StreamingTimers) >= idx && ~isempty(obj.StreamingTimers{idx}) && isvalid(obj.StreamingTimers{idx})
                stop(obj.StreamingTimers{idx});
                delete(obj.StreamingTimers{idx});
                obj.StreamingTimers{idx} = [];
            end
        end

        function initializeSignalMaps(obj)
            % Initialize or update signal scaling and state maps
            if isempty(obj.SignalScaling) || ~isa(obj.SignalScaling, 'containers.Map')
                obj.SignalScaling = containers.Map('KeyType', 'char', 'ValueType', 'double');
            end
            if isempty(obj.StateSignals) || ~isa(obj.StateSignals, 'containers.Map')
                obj.StateSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
            end

            % Ensure all signals are registered
            for i = 1:numel(obj.SignalNames)
                s = obj.SignalNames{i};
                if ~obj.SignalScaling.isKey(s)
                    obj.SignalScaling(s) = 1.0;
                end
                if ~obj.StateSignals.isKey(s)
                    obj.StateSignals(s) = false;
                end
            end
        end

        function fileName = getFileName(obj)
            % Get just the filename from the full path
            [~, name, ext] = fileparts(obj.CSVFilePaths{1}); % Assuming all CSVs have the same name for now
            fileName = [name, ext];
        end

        function tf = validateCSV(~, filePath)
            tf = false;
            if ~isfile(filePath)
                return;
            end

            try
                fid = fopen(filePath, 'r');
                headerLine = fgetl(fid);
                fclose(fid);
                if isempty(headerLine) || ~contains(headerLine, ',')
                    return;
                end
                tf = true;
            catch ME
                % uialert(obj.App.UIFigure, ['Error reading CSV file: ' ME.message], 'Error');
            end
        end

        % Add cleanup method
        function delete(obj)
            % Ensure all timers are properly cleaned up
            for i = 1:numel(obj.StreamingTimers)
                if ~isempty(obj.StreamingTimers{i}) && isvalid(obj.StreamingTimers{i})
                    if strcmp(obj.StreamingTimers{i}.Running, 'on')
                        stop(obj.StreamingTimers{i});
                    end
                    delete(obj.StreamingTimers{i});
                end
            end
            obj.StreamingTimers = {};
        end
    end
end