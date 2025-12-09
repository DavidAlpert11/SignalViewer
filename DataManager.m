% DataManager.m - Optimized for MATLAB 2021b
% Handles data loading with optional streaming mode
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
        UpdateRate       double = 0.1  % Check every 100ms (optimized from 0.01)
        LatestDataRates  cell   % Cell array of doubles, one per CSV
        StreamingEnabled logical = false  % NEW: Toggle for streaming mode
        % Performance optimization: Signal lookup cache
        SignalCache      containers.Map  % Cache for signal data lookups (key: 'CSVIdx_SignalName', value: data)
        CacheValid        logical = false  % Flag to indicate if cache is valid
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
            obj.SignalCache = containers.Map('KeyType', 'char', 'ValueType', 'any');
            obj.CacheValid = false;
        end

        function startStreamingAll(obj)
            % Start streaming only if enabled
            if ~obj.StreamingEnabled
                return;
            end
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
        end
        
        function loadDataOnce(obj)
            % Load all CSV data once without streaming (optimized for performance)
            app = obj.App;
            obj.stopStreamingAll();  % Ensure no streaming is active
            
            numCSVs = numel(obj.CSVFilePaths);
            if numCSVs == 0
                return;
            end
            
            % Check total file sizes before loading
            totalSizeMB = 0;
            for i = 1:numCSVs
                if isfile(obj.CSVFilePaths{i})
                    fileInfo = dir(obj.CSVFilePaths{i});
                    if ~isempty(fileInfo)
                        totalSizeMB = totalSizeMB + fileInfo(1).bytes / (1024 * 1024);
                    end
                end
            end
            
            % Warn if total size is very large
            if totalSizeMB > 500
                answer = uiconfirm(app.UIFigure, ...
                    sprintf('Total file size is %.1f MB. Loading may take time and use significant memory.\n\nContinue?', totalSizeMB), ...
                    'Large Files Warning', ...
                    'Options', {'Continue', 'Cancel'}, ...
                    'DefaultOption', 'Cancel', ...
                    'Icon', 'warning');
                if strcmp(answer, 'Cancel')
                    app.StatusLabel.Text = '❌ Loading cancelled';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    return;
                end
            end
            
            % Load all CSVs sequentially with progress updates
            successCount = 0;
            failedCount = 0;
            
            for i = 1:numCSVs
                try
                    [~, fileName, ext] = fileparts(obj.CSVFilePaths{i});
                    app.StatusLabel.Text = sprintf('📁 Loading CSV %d/%d: %s%s...', i, numCSVs, fileName, ext);
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];
                    drawnow;
                    
                    obj.readInitialData(i);
                    
                    if ~isempty(obj.DataTables{i})
                        successCount = successCount + 1;
                    else
                        failedCount = failedCount + 1;
                    end
                catch ME
                    fprintf('Error loading CSV %d: %s\n', i, ME.message);
                    failedCount = failedCount + 1;
                    obj.DataTables{i} = [];
                end
            end
            
            obj.IsRunning = false;
            totalRows = 0;
            for i = 1:numel(obj.DataTables)
                if ~isempty(obj.DataTables{i})
                    totalRows = totalRows + height(obj.DataTables{i});
                end
            end
            
            % Update status with results
            if failedCount == 0
                app.StatusLabel.Text = sprintf('✅ Loaded %d CSV(s): %d rows, %d signals', ...
                    successCount, totalRows, numel(obj.SignalNames));
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                app.StatusLabel.Text = sprintf('⚠️ Loaded %d/%d CSV(s): %d rows, %d signals (%d failed)', ...
                    successCount, numCSVs, totalRows, numel(obj.SignalNames), failedCount);
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
            app.StreamingInfoLabel.Text = sprintf('Loaded %d CSV(s) (no streaming)', successCount);
            app.DataRateLabel.Text = sprintf('📊 Total: %d samples', totalRows);
        end


        function startStreamingForCSV(obj, idx)
            % Initialize file monitoring for this CSV
            if ~obj.initializeFileMonitoring(idx)
                return;
            end
            % Read initial data for this CSV
            obj.readInitialData(idx);
            % Start streaming timer for this CSV (only if streaming enabled)
            if obj.StreamingEnabled
                obj.startStreamingTimer(idx);
            end
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
            % Optimized data reading with better error handling and large file support
            filePath = obj.CSVFilePaths{idx};
            if ~isfile(filePath)
                obj.DataTables{idx} = [];
                return;
            end
            
            % Quick file size check
            fileInfo = dir(filePath);
            if ~isstruct(fileInfo) || isempty(fileInfo) || fileInfo(1).bytes == 0
                obj.DataTables{idx} = [];
                return;
            end
            
            % Check file size and warn for very large files
            fileSizeMB = fileInfo(1).bytes / (1024 * 1024);
            if fileSizeMB > 100
                obj.App.StatusLabel.Text = sprintf('⚠️ Loading large file (%.1f MB): %s...', fileSizeMB, fileparts(filePath));
                obj.App.StatusLabel.FontColor = [0.9 0.6 0.2];
                drawnow;
            end
            
            try
                % Use optimized import options with memory-efficient settings
                opts = detectImportOptions(filePath);
                if isempty(opts.VariableNames)
                    obj.DataTables{idx} = [];
                    return;
                end
                
                % Set variable types before reading (more efficient)
                opts = setvartype(opts, 'double');
                
                % For very large files, use chunked reading
                if fileSizeMB > 200  % Lowered threshold for better performance
                    % Use chunked reading for large files
                    T = obj.readLargeCSVChunked(filePath, opts);
                else
                    % Direct read for smaller files (faster)
                    T = readtable(filePath, opts);
                end
            catch ME
                fprintf('Error reading CSV %d: %s\n', idx, ME.message);
                obj.App.StatusLabel.Text = sprintf('❌ Error loading CSV %d: %s', idx, ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
                obj.DataTables{idx} = [];
                return;
            end
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
            
            % Invalidate cache when new data is loaded
            obj.CacheValid = false;
            obj.SignalCache = containers.Map('KeyType', 'char', 'ValueType', 'any');
            
            % Update signal names (union of all signals) - optimized
            obj.updateSignalNames();
            obj.initializeSignalMaps();
            
            % Only update UI if not in batch loading mode
            if ~obj.IsRunning || idx == numel(obj.CSVFilePaths)
                obj.App.buildSignalTree();
                obj.App.PlotManager.refreshPlots();
            end
            
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
                % Optimized: Use UpdateRate (0.1s = 100ms) instead of 0.01s for better performance
                obj.StreamingTimers{idx} = timer(...
                    'ExecutionMode', 'fixedRate', ...
                    'Period', obj.UpdateRate, ...
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
        
        function updateSignalNames(obj)
            % Optimized signal name update (called once instead of multiple times)
            allSignals = {};
            for k = 1:numel(obj.DataTables)
                if ~isempty(obj.DataTables{k})
                    allSignals = union(allSignals, setdiff(obj.DataTables{k}.Properties.VariableNames, {'Time'}));
                end
            end
            obj.SignalNames = allSignals;
        end
        
        function setStreamingMode(obj, enabled)
            % Set streaming mode (true = streaming, false = one-time load)
            obj.StreamingEnabled = enabled;
            if ~enabled
                obj.stopStreamingAll();
            end
        end
        
        function T = readLargeCSVChunked(obj, filePath, opts)
            % Read large CSV files in chunks to avoid memory issues
            % Optimized for files > 500MB with better memory management
            
            try
                % Adaptive chunk size based on file size
                fileInfo = dir(filePath);
                fileSizeMB = fileInfo(1).bytes / (1024 * 1024);
                
                % Larger chunk size for very large files (better performance)
                if fileSizeMB > 1000
                    chunkSize = 500000; % 500k rows for very large files
                else
                    chunkSize = 200000; % 200k rows for large files
                end
                
                % Pre-allocate cell array for chunks (more efficient than growing table)
                chunks = {};
                rowOffset = 0;
                totalRows = 0;
                
                % First, estimate total rows by reading header and first chunk
                try
                    % Read first chunk to get structure
                    chunkOpts = opts;
                    chunkOpts.DataLines = [1, min(chunkSize, 10000)]; % Read small first chunk
                    firstChunk = readtable(filePath, chunkOpts);
                    
                    if isempty(firstChunk) || height(firstChunk) == 0
                        T = table();
                        return;
                    end
                    
                    % Set first column as Time
                    if ~isempty(firstChunk.Properties.VariableNames)
                        firstChunk.Properties.VariableNames{1} = 'Time';
                    end
                    
                    % Set variable types for all columns
                    opts = setvartype(opts, 'double');
                    
                    chunks{1} = firstChunk;
                    totalRows = height(firstChunk);
                    rowOffset = height(firstChunk);
                    
                catch ME
                    % If chunk reading fails, fall back to full read
                    opts = setvartype(opts, 'double');
                    T = readtable(filePath, opts);
                    if ~isempty(T) && ~isempty(T.Properties.VariableNames)
                        T.Properties.VariableNames{1} = 'Time';
                    end
                    return;
                end
                
                % Continue reading chunks
                chunkCount = 1;
                while true
                    try
                        % Read next chunk
                        chunkOpts = opts;
                        chunkOpts.DataLines = [rowOffset + 1, rowOffset + chunkSize];
                        chunk = readtable(filePath, chunkOpts);
                        
                        if isempty(chunk) || height(chunk) == 0
                            break;
                        end
                        
                        % Set first column as Time
                        if ~isempty(chunk.Properties.VariableNames)
                            chunk.Properties.VariableNames{1} = 'Time';
                        end
                        
                        chunkCount = chunkCount + 1;
                        chunks{chunkCount} = chunk;
                        totalRows = totalRows + height(chunk);
                        rowOffset = rowOffset + height(chunk);
                        
                        % Update progress less frequently for better performance
                        if mod(chunkCount, 10) == 0
                            obj.App.StatusLabel.Text = sprintf('📊 Loading... %d rows loaded', totalRows);
                            drawnow('limitrate'); % Limit drawnow rate
                        end
                        
                        % If we got fewer rows than requested, we're done
                        if height(chunk) < chunkSize
                            break;
                        end
                    catch
                        % If chunk reading fails, break and concatenate what we have
                        break;
                    end
                end
                
                % Concatenate all chunks at once (more efficient than incremental)
                if chunkCount == 1
                    T = chunks{1};
                else
                    T = vertcat(chunks{:});
                end
                
            catch
                % Final fallback: try normal read
                try
                    opts = setvartype(opts, 'double');
                    T = readtable(filePath, opts);
                    if ~isempty(T) && ~isempty(T.Properties.VariableNames)
                        T.Properties.VariableNames{1} = 'Time';
                    end
                catch
                    T = table();
                end
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