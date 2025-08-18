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

        function isValidCSV = validateCSVFormat(obj, T, filePath)
            isValidCSV = false;
            fid = -1; % Initialize file handle

            try
                if isempty(T) || ~istable(T)
                    return;
                end

                numTableCols = width(T);

                % Open file with proper error handling
                fid = fopen(filePath, 'r');
                if fid == -1
                    return;
                end

                % Read header line
                headerLine = fgetl(fid);
                if headerLine == -1
                    return;
                end

                % Count header columns
                if contains(headerLine, ',')
                    headerCols = strsplit(headerLine, ',');
                elseif contains(headerLine, ';')
                    headerCols = strsplit(headerLine, ';');
                elseif contains(headerLine, sprintf('\t'))
                    headerCols = strsplit(headerLine, sprintf('\t'));
                else
                    headerCols = strsplit(headerLine, ' ');
                end
                numHeaderCols = length(headerCols);

                % Read first data line
                dataLine = fgetl(fid);
                if dataLine == -1
                    return;
                end

                % Count data columns
                if contains(dataLine, ',')
                    dataCols = strsplit(dataLine, ',');
                elseif contains(dataLine, ';')
                    dataCols = strsplit(dataLine, ';');
                elseif contains(dataLine, sprintf('\t'))
                    dataCols = strsplit(dataLine, sprintf('\t'));
                else
                    dataCols = strsplit(dataLine, ' ');
                end
                numDataCols = length(dataCols);

                % Validate format
                if numHeaderCols == numDataCols && numTableCols == numHeaderCols
                    isValidCSV = true;
                end

            catch ME
                fprintf('Error validating CSV format: %s\n', ME.message);

                finally
                % CRITICAL: Always close file handle
                if fid ~= -1
                    fclose(fid);
                end
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

            % Validate CSV format (header vs data column count)
            if ~obj.validateCSVFormat(T, filePath)
                obj.DataTables{idx} = [];
                [~, fileName, ext] = fileparts(filePath);
                obj.App.StatusLabel.Text = sprintf('❌ CSV format error: %s%s - header/data column mismatch', fileName, ext);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
                uialert(obj.App.UIFigure, ...
                    sprintf('CSV format error in "%s%s":\n\nThe number of header columns does not match the number of data columns.\n\nThis CSV format is not supported. Please check your CSV file format.', fileName, ext), ...
                    'Unsupported CSV Format', 'Icon', 'error');
                return;
            end

            % ALWAYS treat the first column as Time, regardless of its original name
            if ~isempty(T.Properties.VariableNames)
                T.Properties.VariableNames{1} = 'Time';
            else
                obj.DataTables{idx} = [];
                return;
            end

            % Verify Time column exists (should always be true now)
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
            % Thread-safe timer creation and management
            try
                % Stop existing timer safely
                if numel(obj.StreamingTimers) >= idx && ~isempty(obj.StreamingTimers{idx})
                    if isvalid(obj.StreamingTimers{idx})
                        if strcmp(obj.StreamingTimers{idx}.Running, 'on')
                            stop(obj.StreamingTimers{idx});
                        end
                        delete(obj.StreamingTimers{idx});
                    end
                    obj.StreamingTimers{idx} = [];
                end

                % Ensure StreamingTimers cell array is large enough
                while numel(obj.StreamingTimers) < idx
                    obj.StreamingTimers{end+1} = [];
                end

                % Create new timer with error handling
                obj.StreamingTimers{idx} = timer(...
                    'ExecutionMode', 'fixedRate', ...
                    'Period', 0.01, ...
                    'TimerFcn', @(tmr,evt) obj.safeCheckForUpdates(idx), ...
                    'ErrorFcn', @(tmr,evt) obj.handleTimerError(idx, evt));

                start(obj.StreamingTimers{idx});
                obj.LastUpdateTime = datetime('now');

            catch ME
                fprintf('Error starting streaming timer for CSV %d: %s\n', idx, ME.message);
            end
        end

        function safeCheckForUpdates(obj, idx)
            % Thread-safe wrapper for checkForUpdates
            try
                if ~isprop(obj.App, 'DataManager') || ...
                        isempty(obj.App.DataManager) || ...
                        ~isvalid(obj.App.DataManager)
                    obj.stopStreamingForCSV(idx);
                    return;
                end

                obj.checkForUpdates(idx);

            catch ME
                fprintf('Error in timer callback for CSV %d: %s\n', idx, ME.message);
                obj.stopStreamingForCSV(idx);
            end
        end

        function handleTimerError(obj, idx, evt)
            % Handle timer errors gracefully
            fprintf('Timer error for CSV %d: %s\n', idx, evt.Data.message);
            obj.stopStreamingForCSV(idx);
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

                % Validate CSV format (header vs data column count) for streaming
                if ~obj.validateCSVFormat(T, filePath)
                    [~, fileName, ext] = fileparts(filePath);
                    obj.App.StatusLabel.Text = sprintf('❌ Streaming stopped: %s%s format error', fileName, ext);
                    obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
                    % Stop the streaming timer for this CSV
                    if numel(obj.StreamingTimers) >= idx && ~isempty(obj.StreamingTimers{idx})
                        stop(obj.StreamingTimers{idx});
                        delete(obj.StreamingTimers{idx});
                        obj.StreamingTimers{idx} = [];
                    end
                    return;
                end

                % ALWAYS treat the first column as Time, regardless of its original name
                if ~isempty(T.Properties.VariableNames)
                    T.Properties.VariableNames{1} = 'Time';
                else
                    return;
                end

                % Verify Time column exists (should always be true now)
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

        function mergedData = mergeNewData(obj, existingData, newData)
            try
                % Simple concatenation if column structures are identical
                if isequal(existingData.Properties.VariableNames, newData.Properties.VariableNames)
                    mergedData = [existingData; newData];
                else
                    % Use outerjoin for different column structures
                    mergedData = outerjoin(existingData, newData, ...
                        'Keys', 'Time', 'MergeKeys', true, 'Type', 'full');
                end

                % Sort by time
                mergedData = sortrows(mergedData, 'Time');

            catch ME
                % Fallback: just append new data
                fprintf('Merge error, using simple append: %s\n', ME.message);
                mergedData = [existingData; newData];
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

        % Add this method to DataManager.m in the methods section

        function clearData(obj)
            % Clear all data and reset the DataManager state

            try
                % Stop all streaming first
                obj.stopStreamingAll();

                % Clear data tables and related arrays
                obj.DataTables = {};
                obj.SignalNames = {};
                obj.CSVFilePaths = {};
                obj.LastFileModTimes = {};
                obj.LastReadRows = {};
                obj.LatestDataRates = {};

                % Reset containers.Map objects
                obj.SignalScaling = containers.Map('KeyType', 'char', 'ValueType', 'double');
                obj.StateSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');

                % Reset counters and flags
                obj.IsRunning = false;
                obj.DataCount = 0;
                obj.UpdateCounter = 0;
                obj.LastUpdateTime = datetime('now');

                % Update UI status
                if isprop(obj, 'App') && ~isempty(obj.App) && isvalid(obj.App)
                    obj.App.StatusLabel.Text = '🗑️ Data cleared';
                    obj.App.StatusLabel.FontColor = [0.5 0.5 0.5];
                    obj.App.DataRateLabel.Text = 'Data Rate: 0 Hz';
                    obj.App.StreamingInfoLabel.Text = '';
                end

            catch ME
                fprintf('Warning during data clear: %s\n', ME.message);
            end
        end

        function updateSignalNamesAfterClear(obj)
            % Update signal names after clearing some CSV data (ENHANCED VERSION)

            try
                % Rebuild signal names from remaining data tables
                allSignals = {};
                for k = 1:numel(obj.DataTables)
                    if ~isempty(obj.DataTables{k}) && istable(obj.DataTables{k})
                        tableSignals = setdiff(obj.DataTables{k}.Properties.VariableNames, {'Time'});
                        allSignals = union(allSignals, tableSignals);
                    end
                end

                % Add derived signals if they exist
                if isprop(obj.App, 'SignalOperations') && ~isempty(obj.App.SignalOperations) && ...
                        isprop(obj.App.SignalOperations, 'DerivedSignals') && ~isempty(obj.App.SignalOperations.DerivedSignals)
                    derivedNames = keys(obj.App.SignalOperations.DerivedSignals);
                    allSignals = union(allSignals, derivedNames);
                end

                obj.SignalNames = allSignals;

                % Clean up signal maps for removed signals
                obj.cleanupSignalMaps();

            catch ME
                fprintf('Warning during signal names update: %s\n', ME.message);
            end
        end

        function cleanupSignalMaps(obj)
            % Clean up signal scaling and state maps for signals that no longer exist

            try
                % Get current signal scaling keys
                if ~isempty(obj.SignalScaling) && isa(obj.SignalScaling, 'containers.Map')
                    scalingKeys = keys(obj.SignalScaling);
                    for i = 1:length(scalingKeys)
                        if ~ismember(scalingKeys{i}, obj.SignalNames)
                            obj.SignalScaling.remove(scalingKeys{i});
                        end
                    end
                end

                % Get current state signals keys
                if ~isempty(obj.StateSignals) && isa(obj.StateSignals, 'containers.Map')
                    stateKeys = keys(obj.StateSignals);
                    for i = 1:length(stateKeys)
                        if ~ismember(stateKeys{i}, obj.SignalNames)
                            obj.StateSignals.remove(stateKeys{i});
                        end
                    end
                end

            catch ME
                fprintf('Warning during signal maps cleanup: %s\n', ME.message);
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