classdef DataManager < handle
    properties
        App
        SignalNames      cell
        DataBuffer       table
        SignalScaling    containers.Map
        StateSignals     containers.Map
        Timer
        IsRunning        logical = false
        DataCount        double = 0
        UpdateCounter    double = 0
        LastUpdateTime   datetime
        FID              double = -1
        NumColumns       double = 0
    end

    methods
        function obj = DataManager(app)
            obj.App = app;
            obj.SignalNames = {};
            obj.DataBuffer = table();
            obj.SignalScaling = containers.Map();
            obj.StateSignals = containers.Map();
        end

        function startStreaming(obj)
            app = obj.App;

            [file, path] = uigetfile('*.csv', 'Select Signal CSV File');
            if isequal(file, 0)
                return;
            end
            filePath = fullfile(path, file);
            app.CSVPathField.Value = filePath;

            % Read and standardize table
            opts = detectImportOptions(filePath);
            opts = setvartype(opts, 'double');
            T = readtable(filePath, opts);
            T.Properties.VariableNames{1} = 'Time';
            T = sortrows(T, 'Time');

            if isempty(obj.DataBuffer) || height(obj.DataBuffer) == 0
                obj.DataBuffer = T;  % First time — no merging
            else
                merged = outerjoin(obj.DataBuffer, T, ...
                    'Keys', 'Time', 'MergeKeys', true, 'Type', 'full');

                % Deduplicate '_left' and '_right' columns
                vars = merged.Properties.VariableNames;
                leftCols = contains(vars, '_left');
                rightCols = contains(vars, '_right');

                for i = find(leftCols)
                    leftName = vars{i};
                    baseName = erase(leftName, '_left');
                    rightName = baseName + "_right";

                    if ismember(rightName, vars)
                        % Compare data
                        leftData = merged.(leftName);
                        rightData = merged.(rightName);

                        if isequaln(leftData, rightData)
                            merged.(baseName) = leftData;  % Use either
                        else
                            % Keep both with suffixes
                            merged.(leftName) = leftData;
                            merged.(rightName) = rightData;
                        end

                        % Remove originals
                        merged.(leftName) = [];
                        merged.(rightName) = [];
                    end
                end

                % Also remove Time_left / Time_right if created
                if ismember('Time_left', vars)
                    merged.Time = merged.Time_left;
                    merged.Time_left = [];
                    if ismember('Time_right', merged.Properties.VariableNames)
                        merged.Time_right = [];
                    end
                end

                obj.DataBuffer = sortrows(merged, 'Time');
            end

            % Signal Names = all except 'Time'
            obj.SignalNames = setdiff(obj.DataBuffer.Properties.VariableNames, {'Time'});

            % Initialize scaling/state maps - FIXED: Use obj.SignalScaling instead of app.SignalScaling
            if isempty(obj.SignalScaling) || ~isa(obj.SignalScaling, 'containers.Map')
                obj.SignalScaling = containers.Map('KeyType', 'char', 'ValueType', 'double');
            end
            if isempty(obj.StateSignals) || ~isa(obj.StateSignals, 'containers.Map')
                obj.StateSignals = containers.Map('KeyType', 'char', 'ValueType', 'logical');
            end

            % Ensure all signals are registered - FIXED: Use obj.SignalScaling instead of app.SignalScaling
            for i = 1:numel(obj.SignalNames)
                s = obj.SignalNames{i};
                if ~obj.SignalScaling.isKey(s)
                    obj.SignalScaling(s) = 1.0;
                end
                if ~obj.StateSignals.isKey(s)
                    obj.StateSignals(s) = false;
                end
            end

            app.UIController.updateSignalCheckboxes();
            app.PlotManager.refreshPlots();

            app.StatusLabel.Text = sprintf('Loaded: %s', file);
            app.DataRateLabel.Text = sprintf('Samples: %d', height(obj.DataBuffer));
        end

        function stopStreaming(obj)
            obj.IsRunning = false;
            obj.App.StartButton.Enable = true;
            obj.App.StopButton.Enable = false;
            obj.App.StatusLabel.Text = 'Stopped';
            obj.App.DataRateLabel.Text = 'Data Rate: 0 Hz';
        end

        function tf = validateCSV(obj, filePath)
            tf = false;
            if ~isfile(filePath)
                uialert(obj.App.UIFigure, 'CSV file not found.', 'Error');
                return;
            end

            try
                fid = fopen(filePath, 'r');
                headerLine = fgetl(fid);
                fclose(fid);
                if isempty(headerLine) || ~contains(headerLine, ',')
                    uialert(obj.App.UIFigure, ...
                        'Invalid CSV format. Must contain comma-separated headers.', 'Error');
                    return;
                end
                tf = true;
            catch ME
                uialert(obj.App.UIFigure, ['Error reading CSV file: ' ME.message], 'Error');
            end
        end
    end
end
